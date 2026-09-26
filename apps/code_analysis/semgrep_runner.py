"""Semgrep Runner — gọi Semgrep CLI an toàn và tái lập (checklist mục 2).

Quy tắc bắt buộc:
- subprocess.run() với danh sách đối số, shell=False (không nối chuỗi shell).
- Không dùng --config=auto; chỉ dùng rule đã pin trong rules/ (custom + vendor).
- --no-rewrite-rule-ids: mặc định Semgrep gắn tiền tố đường dẫn vào id của rule
  local (xem docs "Run rules" — rule id bị đổi theo relative path) → phá vỡ đối
  chiếu rule custom và tính tái lập, nên phải tắt.
- --error: exit code 1 khi có findings (hợp đồng 0/1/khác của checklist).
- --strict: fail sớm nếu file rule không hợp lệ (tránh im lặng bỏ qua rule).
- Ghi semgrep_version + ruleset_sha256 (băm thư mục rule) cho tính tái lập.
"""

import hashlib
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

# Cờ bắt buộc theo mục 8.2 (tài liệu hệ thống)
BASE_FLAGS = [
    "--json",
    "--metrics=off",
    "--disable-version-check",
    "--timeout=120",
    "--max-memory=2048",
    "--max-target-bytes=2000000",
    "--no-rewrite-rule-ids",
    "--strict",
    "--error",
]

EXCLUDES = ["node_modules", ".git", "vendor"]

RULES_DIR = Path(__file__).resolve().parent / "rules"

# Bảng mã thoát thật của `semgrep scan` (docs.semgrep.dev/cli-reference)
EXIT_CODE_MEANINGS = {
    2: "fatal error",
    3: "invalid target code",
    4: "invalid pattern",
    5: "unparseable YAML",
    7: "missing configuration",
    8: "invalid language",
    13: "invalid API key",
    99: "not implemented in osemgrep",
}

SUBPROCESS_TIMEOUT = 300


def semgrep_command() -> list | None:
    """Ưu tiên binary trên PATH, fallback về `python -m semgrep`."""
    exe = shutil.which("semgrep")
    if exe:
        return [exe]
    try:
        import importlib.util

        if importlib.util.find_spec("semgrep") is not None:
            return [sys.executable, "-m", "semgrep"]
    except Exception:  # pragma: no cover - phòng thủ
        pass
    return None


def rule_files(rules_dir: Path | None = None) -> list[Path]:
    rules_dir = Path(rules_dir) if rules_dir else RULES_DIR
    if not rules_dir.exists():
        return []
    return sorted(set([*rules_dir.rglob("*.yaml"), *rules_dir.rglob("*.yml")]))


def ruleset_sha256(rules_dir: Path | None = None) -> str:
    """Băm toàn bộ thư mục rule (thứ tự file ổn định) — cho tính tái lập."""
    rules_dir = Path(rules_dir) if rules_dir else RULES_DIR
    h = hashlib.sha256()
    for f in rule_files(rules_dir):
        h.update(str(f.relative_to(rules_dir)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


@lru_cache(maxsize=1)
def semgrep_version() -> str:
    base = semgrep_command()
    if base is None:
        return "unknown"
    try:
        out = subprocess.run(
            [*base, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            shell=False,
        )
        return (out.stdout or out.stderr or "").strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


@dataclass
class ScanResult:
    state: str  # CLEAN | FINDINGS | TOOL_ERROR
    state_reason: str = ""
    data: dict = field(default_factory=dict)
    tool_errors: list = field(default_factory=list)
    returncode: int = 0


def build_command(
    target_dir: str,
    rules_dir: Path | None = None,
    extra_rules: list[str] | None = None,
) -> list:
    base = semgrep_command() or ["semgrep"]
    cmd = [*base, "scan", *BASE_FLAGS]
    for ex in EXCLUDES:
        cmd.append(f"--exclude={ex}")
    cmd.append(f"--config={Path(rules_dir) if rules_dir else RULES_DIR}")
    for r in extra_rules or []:
        cmd.append(f"--config={r}")
    cmd.append(str(target_dir))
    return cmd


def run_semgrep(
    target_dir: str,
    rules_dir: Path | None = None,
    extra_rules: list[str] | None = None,
) -> ScanResult:
    """Chạy Semgrep trên thư mục target (đã giải nén an toàn từ Artifact)."""
    if not rule_files(rules_dir):
        return ScanResult(
            state="TOOL_ERROR",
            state_reason=f"Không tìm thấy rule đã pin trong {rules_dir or RULES_DIR}",
        )

    cmd = build_command(target_dir, rules_dir, extra_rules)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SUBPROCESS_TIMEOUT,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return ScanResult(
            state="TOOL_ERROR",
            state_reason=f"Semgrep timed out sau {SUBPROCESS_TIMEOUT}s",
        )
    except OSError as e:
        return ScanResult(state="TOOL_ERROR", state_reason=f"Semgrep không khởi chạy được: {e}")

    data = None
    if (proc.stdout or "").strip():
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            data = None

    if not isinstance(data, dict):
        meaning = EXIT_CODE_MEANINGS.get(proc.returncode, f"exit={proc.returncode}")
        detail = (proc.stderr or "").strip().replace("\n", " ")[:300]
        reason = f"Semgrep không trả JSON hợp lệ ({meaning})"
        if detail:
            reason += f": {detail}"
        return ScanResult(state="TOOL_ERROR", state_reason=reason, returncode=proc.returncode)

    tool_errors = []
    for err in data.get("errors") or []:
        if isinstance(err, dict):
            tool_errors.append(str(err.get("message") or err.get("type") or err))
        else:
            tool_errors.append(str(err))

    results = data.get("results") or []

    # Exit code ngoài 0/1 mà không có finding nào => lỗi công cụ thật sự
    # (không tính điểm; ghi state_reason theo mã thoát).
    if proc.returncode not in (0, 1) and not results:
        meaning = EXIT_CODE_MEANINGS.get(proc.returncode, f"exit={proc.returncode}")
        reason = f"Semgrep {meaning}"
        if tool_errors:
            reason += f": {tool_errors[0]}"
        return ScanResult(
            state="TOOL_ERROR",
            state_reason=reason,
            data=data,
            tool_errors=tool_errors,
            returncode=proc.returncode,
        )

    state = "FINDINGS" if results else "CLEAN"
    return ScanResult(
        state=state,
        data=data,
        tool_errors=tool_errors,
        returncode=proc.returncode,
    )
