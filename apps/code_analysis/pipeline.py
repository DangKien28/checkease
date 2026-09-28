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

    # Step 1: Secret Scan
    secret_res = run_gitleaks(target_dir, secret_allowlist)
    if secret_res.triggered and secret_res.findings:
        result.hard_gate_triggered = True
        result.findings.extend(_secret_findings(secret_res))

    # Step 2: Semgrep Scan
    semgrep_res = run_semgrep(target_dir)
    if semgrep_res.state == "TOOL_ERROR":
        result.code_score = None
        result.status = "Fail"
        result.warnings.append(f"Semgrep failed: {semgrep_res.state_reason}")
        return result

    # Step 3: Parse and Map findings
    parser = SemgrepParser()
    parsed = parser.parse(semgrep_res.data)
    result.warnings.extend(parsed.warnings)

    for f in parsed.findings:
        f.category = map_category(f.category or f.rule_id, f.message, f.cwe)
        if not f.final_severity:
            f.final_severity = map_severity(f.severity, f.impact, f.confidence, f.cwe)
        if f.hard_gate:
            result.hard_gate_triggered = True
        result.findings.append(f)

    # Step 4: Compute Score
    result.scan_meta = _scan_meta(secret_res, semgrep_res, started)
    p_th = pass_threshold if pass_threshold is not None else 80.0
    w_th = warning_threshold if warning_threshold is not None else 60.0
    scoring_result = compute_code_score(
        result.findings,
        rule_penalty_cap=rule_penalty_cap,
        pass_threshold=p_th,
        warning_threshold=w_th,
    )
    result.code_score = scoring_result.code_score
    result.score_breakdown = scoring_result.breakdown
    result.counts = scoring_result.counts
    result.warnings.extend(scoring_result.warnings)

    if result.hard_gate_triggered:
        result.status = "Fail"
    else:
        result.status = scoring_result.status

    # ---- Buoc 5: AI Explanation
    try:
        from apps.code_analysis.ai_explainer import AIExplainer
        explainer = AIExplainer()
        result.ai_explanation = explainer.explain(result.findings)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Loi AIExplainer: {e}")
        result.ai_explanation = None

    return result
