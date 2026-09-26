"""Semgrep Runner — gọi Semgrep CLI an toàn và tái lập (checklist mục 2).

Quy tắc bắt buộc:
- subprocess.run() với danh sách đối số, shell=False (không nối chuỗi shell).
- Không dùng --config=auto; chỉ dùng rule đã vendor trong rules/ (pin ruleset).
- Ghi semgrep_version và ruleset_sha256 cho tính tái lập.
"""

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Cờ bắt buộc theo mục 8.2 (tài liệu hệ thống)
BASE_FLAGS = [
    "--metrics=off",
    "--disable-version-check",
    "--timeout=120",
    "--max-memory=2048",
    "--max-target-bytes=2000000",
]

EXCLUDES = ["node_modules", ".git", "vendor"]

RULES_DIR = Path(__file__).resolve().parent / "rules"


def ruleset_sha256(rules_dir: Path = RULES_DIR) -> str:
    """Băm toàn bộ thư mục rule (theo thứ tự file ổn định) — cho tái lập."""
    h = hashlib.sha256()
    for f in sorted(rules_dir.rglob("*.y*ml")):
        h.update(str(f.relative_to(rules_dir)).encode())
        h.update(f.read_bytes())
    return h.hexdigest()


def semgrep_version() -> str:
    try:
        out = subprocess.run(
            ["semgrep", "--version"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
        return out.stdout.strip() or out.stderr.strip()
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


@dataclass
class ScanResult:
    state: str  # CLEAN | FINDINGS | TOOL_ERROR
    state_reason: str = ""
    data: dict = field(default_factory=dict)


def run_semgrep(target_dir: str, extra_rules: list[str] | None = None) -> ScanResult:
    """Chạy Semgrep trên thư mục target (đã giải nén an toàn từ Artifact)."""
    if not RULES_DIR.exists() or not any(RULES_DIR.rglob("*.y*ml")):
        return ScanResult(
            state="TOOL_ERROR",
            state_reason=f"No pinned rules found in {RULES_DIR}",
        )

    cmd = ["semgrep", "scan", "--json", *BASE_FLAGS]
    for ex in EXCLUDES:
        cmd.append(f"--exclude={ex}")
    for r in extra_rules or []:
        cmd.append(f"--config={r}")
    cmd.append(f"--config={RULES_DIR}")
    cmd.append(target_dir)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300, shell=False,
        )
    except subprocess.TimeoutExpired:
        return ScanResult(state="TOOL_ERROR", state_reason="Semgrep timed out after 300s")
    except OSError as e:
        return ScanResult(state="TOOL_ERROR", state_reason=f"Semgrep failed to start: {e}")

    # 0 = sạch, 1 = có findings, khác = lỗi công cụ
    if proc.returncode not in (0, 1):
        return ScanResult(
            state="TOOL_ERROR",
            state_reason=f"semgrep exit={proc.returncode}: {proc.stderr[:500]}",
        )

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ScanResult(state="TOOL_ERROR", state_reason="Semgrep produced invalid JSON")

    state = "FINDINGS" if data.get("results") else "CLEAN"
    return ScanResult(state=state, data=data)
