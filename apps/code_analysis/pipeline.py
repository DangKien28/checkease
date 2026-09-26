"""Pipeline chính của nhánh Code: secret scan → semgrep → parse → map → score → CodeResult.

Bàn giao CodeResult cho Gate Engine (checklist mục 10). Bất biến:
- Secret phát hiện được => hard_gate_triggered=True (không tự FAIL).
- AI (nếu bật) chỉ tạo lớp hiển thị, không đụng findings[] gốc (checklist mục 9 — Phase sau).
"""

import time
from dataclasses import asdict, dataclass, field

from apps.code_analysis.findings_parser import SemgrepParser
from apps.code_analysis.mappings import SEVERITY_MAP_VERSION, map_category, map_severity
from apps.code_analysis.semgrep_runner import run_semgrep, ruleset_sha256, semgrep_version
from apps.code_analysis.scoring import compute_code_score
from apps.code_analysis.secret_scan import run_gitleaks


@dataclass
class CodeResult:
    code_score: float = 100.0
    status: str = "Pass"
    hard_gate_triggered: bool = False
    score_breakdown: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    scan_meta: dict = field(default_factory=dict)
    ai_explanation: dict | None = None
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def run_code_analysis(target_dir: str, secret_allowlist: list[str] | None = None) -> CodeResult:
    """Chạy toàn bộ pipeline SAST trên thư mục đã giải nén an toàn."""
    started = time.time()
    result = CodeResult()

    # ---- Bước 1: Secret scan (trước Semgrep) — Hard Gate
    secret = run_gitleaks(target_dir, allowlist=secret_allowlist)
    result.hard_gate_triggered = secret.triggered
    if secret.state_reason:
        result.warnings.append(f"secret_scan: {secret.state_reason}")

    # ---- Bước 2: Semgrep với rule pin
    scan = run_semgrep(target_dir)
    scan_meta = {
        "semgrep_version": semgrep_version(),
        "ruleset_sha256": ruleset_sha256(),
        "files_scanned": len(scan.data.get("paths", {}).get("scanned", [])) if scan.data else 0,
        "files_skipped": len(scan.data.get("paths", {}).get("skipped", [])) if scan.data else 0,
        "duration_sec": round(time.time() - started, 2),
    }
    result.scan_meta = scan_meta

    if scan.state == "TOOL_ERROR":
        # Lỗi công cụ → không tính điểm, ghi lý do
        result.warnings.append(f"semgrep: {scan.state_reason}")
        result.status = "Warning"
        result.code_score = 0.0
        return result

    # ---- Bước 3: Parse + map severity/category
    parser = SemgrepParser()
    parsed = parser.parse(scan.data)
    for f in parsed.findings:
        f.category = map_category(f.category)
        if not f.hard_gate:
            f.final_severity = map_severity(f.severity, cwe=f.cwe)
        else:
            f.final_severity = "Critical"
    result.findings = [asdict(f) for f in parsed.findings]

    # ---- Bước 4: Scoring
    score = compute_code_score(parsed.findings)
    result.code_score = score.code_score
    result.status = score.status
    result.score_breakdown = score.breakdown
    result.counts = score.counts
    result.warnings.extend(score.warnings)

    # ---- Bước 5 (mục 9 — suy giảm): không có LLM thì vẫn trả đầy đủ điểm số
    result.ai_explanation = None

    return result
