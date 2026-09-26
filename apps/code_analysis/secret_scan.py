"""Secret scan bằng gitleaks — Hard Gate flag (checklist mục 3).

Phát hiện secret => trả về hard_gate_triggered=True trong CodeResult.
KHÔNG tự phán quyết FAIL — đó là việc của Gate Engine.
"""

import json
import re
import subprocess
from dataclasses import dataclass, field

# Placeholder / giá trị giữ chỗ cần loại (giảm dương tính giả)
PLACEHOLDER_PATTERNS = [
    r"YOUR_API_KEY", r"xxxx", r"changeme", r"CHANGEME",
    r"EXAMPLE", r"example_key", r"<[^>]+>", r"\$\{[^}]*\}",
]

# Thư mục loại trừ dương tính giả
EXCLUDED_DIRS = ["test", "tests", "fixtures", "docs", "node_modules", ".git"]


@dataclass
class SecretFinding:
    rule_id: str
    file: str
    line: int
    secret_preview: str  # đã che, chỉ giữ 4 ký tự đầu


@dataclass
class SecretScanResult:
    triggered: bool = False
    findings: list = field(default_factory=list)
    state_reason: str = ""


def _is_placeholder(secret: str) -> bool:
    return any(re.search(p, secret, re.IGNORECASE) for p in PLACEHOLDER_PATTERNS)


def run_gitleaks(target_dir: str, allowlist: list[str] | None = None) -> SecretScanResult:
    """Chạy gitleaks trên thư mục target. Trả về danh sách secret đã che."""
    cmd = [
        "gitleaks", "detect",
        "--source", target_dir,
        "--report-format", "json",
        "--report-path", "-",
        "--no-git",
        "--redact",
        "--exit-code", "0",  # luôn exit 0, tự xử lý kết quả
    ]
    for d in EXCLUDED_DIRS:
        cmd.extend(["--exclude", f"**/{d}/**"])

    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180, shell=False,
        )
    except subprocess.TimeoutExpired:
        return SecretScanResult(state_reason="gitleaks timed out after 180s")
    except OSError as e:
        return SecretScanResult(state_reason=f"gitleaks failed to start: {e}")

    try:
        raw = json.loads(proc.stdout) if proc.stdout.strip() else []
    except json.JSONDecodeError:
        return SecretScanResult(state_reason="gitleaks produced invalid JSON")

    findings = []
    for item in raw:
        secret = item.get("Secret", "") or ""
        if _is_placeholder(secret):
            continue
        file_path = item.get("File", "")
        if allowlist and any(a in file_path for a in allowlist):
            continue
        findings.append(SecretFinding(
            rule_id=item.get("RuleID", "unknown"),
            file=file_path,
            line=item.get("StartLine", 0),
            secret_preview=(secret[:4] + "***") if secret else "***",
        ))

    return SecretScanResult(triggered=bool(findings), findings=findings)
