"""Unit tests cho pipeline nhánh Code (mock hai công cụ, không cần cài gì)."""

import json

from apps.code_analysis import pipeline
from apps.code_analysis.secret_scan import SecretFinding, SecretScanResult
from apps.code_analysis.semgrep_runner import ScanResult


def _scan(results, errors=None, scanned=None):
    return ScanResult(
        state="FINDINGS" if results else "CLEAN",
        data={"results": results, "errors": errors or [],
              "paths": {"scanned": scanned or ["a.py"], "skipped": []}},
        returncode=1 if results else 0,
    )


def _patch(monkeypatch, secret=None, scan=None):
    monkeypatch.setattr(pipeline, "run_gitleaks",
                        lambda *a, **k: secret or SecretScanResult())
    monkeypatch.setattr(pipeline, "run_semgrep",
                        lambda *a, **k: scan or _scan([]))


def _secret_result(file="app/x.py"):
    return SecretScanResult(
        triggered=True,
        findings=[SecretFinding(rule_id="aws-access-token", file=file, line=2,
                                secret_sha256="deadbeefdeadbeef", secret_length=20)],
    )


def test_pipeline_clean_project(monkeypatch):
    _patch(monkeypatch)
    res = pipeline.run_code_analysis(".")
    assert res.code_score == 100.0
    assert res.status == "Pass"
    assert res.hard_gate_triggered is False
    assert res.findings == []
    assert res.ai_explanation is None
    assert res.scan_meta["semgrep_version"]
    assert res.scan_meta["ruleset_sha256"]
    assert res.scan_meta["files_scanned"] == 1
    assert "severity_map_version" in res.scan_meta


def test_pipeline_secret_sets_hard_gate_and_appears_in_findings(monkeypatch):
    _patch(monkeypatch, secret=_secret_result())
    res = pipeline.run_code_analysis(".")
    assert res.hard_gate_triggered is True
    gitleaks_findings = [f for f in res.findings if f["tool"] == "gitleaks"]
    assert len(gitleaks_findings) == 1
    assert gitleaks_findings[0]["hard_gate"] is True
    assert gitleaks_findings[0]["final_severity"] == "Critical"
    assert res.code_score < 100
    assert res.scan_meta["secret_scan"]["triggered"] is True
    # Secret thật không bao giờ nằm trong output
    assert "REALKEY" not in json.dumps(res.to_dict())


def test_pipeline_custom_hard_gate_rule_sets_flag(monkeypatch):
    results = [{
        "check_id": "checkease-hardcoded-secret",
        "path": "app/x.py", "start": {"line": 1},
        "extra": {"severity": "ERROR", "message": "m",
                  "metadata": {"category": "security", "hard_gate": True,
                               "checkease_severity": "Critical", "cwe": "CWE-798",
                               "impact": "HIGH", "confidence": "MEDIUM"},
                  "lines": 'password = "hunter2"'},
    }]
    _patch(monkeypatch, scan=_scan(results))
    res = pipeline.run_code_analysis(".")
    assert res.hard_gate_triggered is True
    assert res.findings[0]["hard_gate"] is True
    assert res.findings[0]["final_severity"] == "Critical"


def test_pipeline_tool_error_does_not_compute_score(monkeypatch):
    _patch(monkeypatch, scan=ScanResult(state="TOOL_ERROR",
                                        state_reason="Semgrep fatal error", returncode=2))
    res = pipeline.run_code_analysis(".")
    assert res.code_score is None          # KHÔNG gán điểm 0 oan
    assert res.status == "Warning"
    assert any("Semgrep fatal error" in w for w in res.warnings)


def test_pipeline_tool_error_still_reports_secrets(monkeypatch):
    _patch(monkeypatch, secret=_secret_result(),
           scan=ScanResult(state="TOOL_ERROR", state_reason="boom"))
    res = pipeline.run_code_analysis(".")
    assert res.hard_gate_triggered is True   # secret đã quét được vẫn báo
    assert res.code_score is None
    assert res.findings and res.findings[0]["tool"] == "gitleaks"


def test_pipeline_warns_when_secret_scan_fails(monkeypatch):
    secret = SecretScanResult(state_reason="gitleaks exit=1: invalid flag")
    _patch(monkeypatch, secret=secret)
    res = pipeline.run_code_analysis(".")
    assert any("secret_scan" in w for w in res.warnings)
    assert res.scan_meta["secret_scan"]["state_reason"]


def test_pipeline_semgrep_warnings_are_propagated(monkeypatch):
    _patch(monkeypatch, scan=_scan([], errors=[{"message": "some file failed to parse"}]))
    res = pipeline.run_code_analysis(".")
    assert any("failed to parse" in w for w in res.warnings)


def test_pipeline_serializes_to_dict(monkeypatch):
    _patch(monkeypatch)
    res = pipeline.run_code_analysis(".")
    as_dict = res.to_dict()
    assert set(as_dict) >= {
        "code_score", "status", "hard_gate_triggered", "score_breakdown",
        "counts", "findings", "scan_meta", "ai_explanation", "warnings",
    }
    json.dumps(as_dict)  # phải serialize được để lưu JSONField
