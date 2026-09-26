"""Secret scan bằng gitleaks — Hard Gate flag (checklist mục 3).

- Phát hiện secret => trả về triggered=True (pipeline set hard_gate_triggered).
  KHÔNG tự phán quyết FAIL — đó là việc của Gate Engine.
- Không lưu giá trị secret thật: chỉ giữ hash + độ dài + vị trí.
- Báo cáo gitleaks ghi vào file tạm và xoá ngay trong finally (kể cả khi lỗi).
- Lỗi công cụ PHẢI được phát hiện: nếu không, secret scan bị vô hiệu âm thầm và
  hard gate không bao giờ bật.
"""

import hashlib
import json
import logging
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Placeholder / giá trị giữ chỗ cần loại (giảm dương tính giả)
PLACEHOLDER_PATTERNS = [
    r"YOUR_API_KEY", r"xxxx", r"changeme", r"CHANGEME",
    r"EXAMPLE", r"example_key", r"<[^>]+>", r"\$\{[^}]*\}",
    r"placeholder", r"dummy", r"your[_-]",
]

# Thư mục loại trừ dương tính giả (so khớp theo path đã chuẩn hoá)
EXCLUDED_DIR_FRAGMENTS = (
    "/test/", "/tests/", "/fixtures/", "/docs/",
    "/node_modules/", "/.git/", "/venv/", "/.venv/", "/__pycache__/",
)

SUBPROCESS_TIMEOUT = 180


@dataclass
class SecretFinding:
    rule_id: str
    file: str
    line: int
    secret_sha256: str  # 16 ký tự đầu của SHA-256, KHÔNG phải secret thật
    secret_length: int


@dataclass
class SecretScanResult:
    triggered: bool = False
    findings: list = field(default_factory=list)
    suppressed: int = 0
    state_reason: str = ""


def _norm_path(p: str) -> str:
    return "/" + (p or "").replace("\\", "/").strip("/") + "/"


def _is_excluded_dir(path: str) -> bool:
    norm = _norm_path(path)
    return any(frag in norm for frag in EXCLUDED_DIR_FRAGMENTS)


def _is_placeholder(secret: str) -> bool:
    return any(re.search(p, secret, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)


def _build_commands(target_dir: str, report_path: str) -> list:
    """gitleaks >= v8.19 có `dir`; bản cũ dùng `detect --no-git` (fallback)."""
    common = ["--report-format", "json", "--report-path", report_path, "--exit-code", "0"]
    return [
        ["gitleaks", "detect", "--source", target_dir, "--no-git", *common],
        ["gitleaks", "dir", target_dir, *common],
    ]


def run_gitleaks(target_dir: str, allowlist: list[str] | None = None) -> SecretScanResult:
    """Chạy gitleaks trên thư mục target. Trả về danh sách secret đã ẩn giá trị."""
    fd, report_path = tempfile.mkstemp(prefix="checkease-gitleaks-", suffix=".json")
    os.close(fd)
    try:
        proc = None
        last_unknown_cmd = ""
        for cmd in _build_commands(target_dir, report_path):
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
                return SecretScanResult(
                    state_reason=f"gitleaks timed out sau {SUBPROCESS_TIMEOUT}s"
                )
            except OSError as e:
                return SecretScanResult(state_reason=f"gitleaks không khởi chạy được: {e}")

            stderr = (proc.stderr or "").strip()
            if proc.returncode != 0 and "unknown command" in stderr.lower():
                # Binary gitleaks phiên bản khác => thử lệnh thay thế
                last_unknown_cmd = stderr.replace("\n", " ")[:200]
                proc = None
                continue
            break

        if proc is None:
            return SecretScanResult(
                state_reason=f"gitleaks CLI không tương thích: {last_unknown_cmd}"
            )

        if proc.returncode != 0:
            detail = (proc.stderr or "").strip().replace("\n", " ")[:300]
            return SecretScanResult(
                state_reason=f"gitleaks exit={proc.returncode}: {detail}"
            )

        try:
            with open(report_path, "r", encoding="utf-8") as fh:
                raw_text = fh.read().strip()
        except OSError as e:
            return SecretScanResult(state_reason=f"Không đọc được báo cáo gitleaks: {e}")

        if not raw_text:
            raw = []
        else:
            try:
                raw = json.loads(raw_text)
            except json.JSONDecodeError:
                return SecretScanResult(state_reason="gitleaks trả về JSON không hợp lệ")
            if not isinstance(raw, list):
                return SecretScanResult(state_reason="gitleaks trả về định dạng không mong đợi")

        findings = []
        suppressed = 0
        for item in raw:
            if not isinstance(item, dict):
                continue
            secret = item.get("Secret") or ""
            file_path = item.get("File") or ""
            line = int(item.get("StartLine") or 0)
            rule_id = str(item.get("RuleID") or "unknown")

            allowlisted = bool(allowlist) and any(a in file_path for a in allowlist)
            if _is_excluded_dir(file_path) or allowlisted:
                suppressed += 1
                logger.info(
                    "secret finding bị loại (allowlist/thư mục): %s:%s rule=%s",
                    file_path, line, rule_id,
                )
                continue
            if not secret or _is_placeholder(secret):
                suppressed += 1
                continue

            findings.append(SecretFinding(
                rule_id=rule_id,
                file=file_path,
                line=line,
                secret_sha256=hashlib.sha256(
                    secret.encode("utf-8", "ignore")
                ).hexdigest()[:16],
                secret_length=len(secret),
            ))

        return SecretScanResult(
            triggered=bool(findings),
            findings=findings,
            suppressed=suppressed,
        )
    finally:
        try:
            os.remove(report_path)
        except OSError:  # pragma: no cover - best effort
            pass
