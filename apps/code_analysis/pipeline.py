"""Pipeline nhánh Code: secret scan → semgrep → parse → map → score → CodeResult.

Bàn giao CodeResult cho Gate Engine (checklist mục 10). Bất biến:
- Secret phát hiện được => hard_gate_triggered=True (không tự FAIL).
- Finding có hard_gate=True (secret scan hoặc rule custom) đều bật cờ hard gate.
- Lỗi công cụ => KHÔNG tính điểm (code_score=None) + warnings, để Gate Engine
  quyết định thay vì gán điểm 0 oan.
- AI (nếu bật) chỉ tạo lớp hiển thị, không đụng findings[] gốc (mục 9).
"""

import time
from dataclasses import asdict, dataclass, field

from apps.code_analysis.findings_parser import Finding, SemgrepParser, make_fingerprint
from apps.code_analysis.mappings import SEVERITY_MAP_VERSION, map_category, map_severity
from apps.code_analysis.scoring import DEFAULT_RULE_PENALTY_CAP, compute_code_score
from apps.code_analysis.secret_scan import run_gitleaks
from apps.code_analysis.semgrep_runner import ruleset_sha256, run_semgrep, semgrep_version


@dataclass
class CodeResult:
    code_score: float | None = 100.0
    status: str = "Pass"  # Pass | Warning | Fail
    hard_gate_triggered: bool = False
    score_breakdown: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    findings: list = field(default_factory=list)
    scan_meta: dict = field(default_factory=dict)
    ai_explanation: dict | None = None
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _secret_findings(secret) -> list:
    """Chuyển SecretFinding -> Finding nội bộ (tool=gitleaks, hard_gate=True).

    Chỉ giữ hash + độ dài; KHÔNG lưu giá trị secret thật vào CodeResult.
    """
    out = []
    for sf in secret.findings:
        out.append(Finding(
            finding_id=f"gitleaks:{sf.rule_id}:{sf.file}:{sf.line}",
            rule_id=sf.rule_id,
            tool="gitleaks",
            file=sf.file,
            line=sf.line,
            message="Phát hiện secret/credential trong mã nguồn — cần thu hồi và luân chuyển.",
            severity="ERROR",
            category="Security",
            cwe="CWE-798",
            confidence="HIGH",
            impact="HIGH",
            remediation="Thu hồi khóa, xoay vòng credential và chuyển sang biến môi trường/secrets manager.",
            fingerprint=make_fingerprint(sf.rule_id, sf.file, f"secret:{sf.secret_sha256}"),
            hard_gate=True,
            final_severity="Critical",
        ))
    return out


def _scan_meta(secret, scan, started: float) -> dict:
    paths = (scan.data.get("paths") or {}) if isinstance(scan.data, dict) else {}
    return {
        "semgrep_version": semgrep_version(),
        "ruleset_sha256": ruleset_sha256(),
        "severity_map_version": SEVERITY_MAP_VERSION,
        "files_scanned": len(paths.get("scanned") or []),
        "files_skipped": len(paths.get("skipped") or []),
        "duration_sec": round(time.time() - started, 2),
        "secret_scan": {
            "triggered": secret.triggered,
            "findings": len(secret.findings),
            "suppressed": secret.suppressed,
            "state_reason": secret.state_reason,
        },
    }


def run_code_analysis(
    target_dir: str,
    secret_allowlist: list | None = None,
    rule_penalty_cap: int = DEFAULT_RULE_PENALTY_CAP,
    pass_threshold: float | None = None,
    warning_threshold: float | None = None,
) -> CodeResult:
    """Chạy toàn bộ pipeline SAST trên thư mục đã giải nén an toàn."""
    started = time.time()
    result = CodeResult()

    # ---- Bước 1: Secret scan (trước Semgrep) — Hard Gate
    secret = run_gitleaks(target_dir, allowlist=secret_allowlist)
    result.hard_gate_triggered = secret.triggered
    secret_findings = _secret_findings(secret)
    if secret.state_reason:
        result.warnings.append(f"secret_scan: {secret.state_reason}")

    # ---- Bước 2: Semgrep với rule đã pin
    scan = run_semgrep(target_dir)
    result.scan_meta = _scan_meta(secret, scan, started)

    if scan.state == "TOOL_ERROR":
        # Lỗi công cụ: không tính điểm; vẫn báo cáo secret đã quét được
        result.code_score = None
        result.status = "Warning"
        result.findings = [asdict(f) for f in secret_findings]
        result.warnings.append(f"semgrep: {scan.state_reason}")
        return result

    # ---- Bước 3: Parse + map severity/category
    parsed = SemgrepParser().parse(scan.data)
    result.warnings.extend(parsed.warnings)

    for f in parsed.findings:
        f.category = map_category(f.category)
        if f.final_severity:
            # Rule custom tự khai báo checkease_severity -> tôn trọng
            pass
        elif f.hard_gate:
            f.final_severity = "Critical"
        else:
            f.final_severity = map_severity(
                f.severity, impact=f.impact, confidence=f.confidence, cwe=f.cwe
            )

    # Hard gate bật nếu secret scan HOẶC bất kỳ finding hard_gate (rule custom)
    if any(f.hard_gate for f in parsed.findings):
        result.hard_gate_triggered = True

    all_findings = secret_findings + parsed.findings
    result.findings = [asdict(f) for f in all_findings]

    # ---- Bước 4: Scoring (loại trùng fingerprint, trần penalty mỗi rule)
    score = compute_code_score(
        all_findings,
        rule_penalty_cap=rule_penalty_cap,
        pass_threshold=pass_threshold,
        warning_threshold=warning_threshold,
    )
    result.code_score = score.code_score
    result.status = score.status
    result.score_breakdown = score.breakdown
    result.counts = score.counts
    result.warnings.extend(score.warnings)

    # ---- Bước 5: AI Explanation — chế độ suy giảm khi không có LLM (mục 9)
    result.ai_explanation = None

    return result
