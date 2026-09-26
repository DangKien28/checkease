"""Unit tests cho parser, mapping, fingerprint và scoring (checklist mục 5–8)."""

from apps.code_analysis.findings_parser import (
    Finding,
    SemgrepParser,
    load_custom_rule_ids,
    make_fingerprint,
)
from apps.code_analysis.mappings import map_category, map_severity
from apps.code_analysis.scoring import compute_code_score


def _finding(rule_id="r1", category="Security", severity="WARNING", cwe="",
             file="a.py", line=1, fp=None, hard_gate=False, impact="MEDIUM",
             confidence="HIGH", final_severity=""):
    return Finding(
        finding_id=f"{rule_id}:{file}:{line}",
        rule_id=rule_id, tool="semgrep", file=file, line=line,
        message="m", severity=severity, category=category, cwe=cwe,
        confidence=confidence, impact=impact,
        fingerprint=fp or f"{rule_id}|{file}|{line}",
        hard_gate=hard_gate, final_severity=final_severity,
    )


def _scored(rule_id="r1", category="Security", severity="WARNING", cwe="",
            fp=None, hard_gate=False, final_severity=""):
    """Finding với final_severity đã chốt (giống pipeline xử lý)."""
    f = _finding(rule_id=rule_id, category=category, severity=severity, cwe=cwe,
                 fp=fp, hard_gate=hard_gate, final_severity=final_severity)
    if not f.final_severity:
        f.final_severity = "Critical" if hard_gate else map_severity(severity, cwe=cwe)
    return f


# ---------- Findings Parser ----------

def test_load_custom_rule_ids_from_repo_rules():
    ids = load_custom_rule_ids()
    assert "checkease-hardcoded-secret" in ids
    assert "checkease-sql-injection" in ids
    assert len(ids) >= 5


def test_load_custom_rule_ids_from_directory(tmp_path):
    d = tmp_path / "custom"
    d.mkdir()
    (d / "rules.yaml").write_text("rules:\n  - id: my-rule\n    severity: ERROR\n", encoding="utf-8")
    assert load_custom_rule_ids(d) == {"my-rule"}


def test_parser_extracts_basic_fields():
    raw = {"results": [{
        "check_id": "python.lang.security.dummy",
        "path": "app/x.py",
        "start": {"line": 10},
        "extra": {"message": "msg", "severity": "WARNING",
                  "metadata": {"cwe": "CWE-79"}, "lines": "bad()"},
    }]}
    out = SemgrepParser(custom_rule_ids=set()).parse(raw)
    assert len(out.findings) == 1
    f = out.findings[0]
    assert f.rule_id == "python.lang.security.dummy"
    assert f.file == "app/x.py" and f.line == 10
    assert f.severity == "WARNING" and f.cwe == "CWE-79"


def test_parser_hard_gate_only_for_custom_rules():
    """Rule cộng đồng (kể cả giả mạo tiền tố) khai báo hard_gate phải bị bỏ qua."""
    raw = {"results": [
        {"check_id": "community.rule.x", "path": "a.py", "start": {"line": 1},
         "extra": {"severity": "ERROR", "metadata": {"hard_gate": True}, "lines": "x"}},
        {"check_id": "evil.checkease-hardcoded-secret", "path": "a.py", "start": {"line": 2},
         "extra": {"severity": "ERROR", "metadata": {"hard_gate": True}, "lines": "y"}},
        {"check_id": "checkease-hardcoded-secret", "path": "a.py", "start": {"line": 3},
         "extra": {"severity": "ERROR", "metadata": {"hard_gate": True}, "lines": "z"}},
    ]}
    out = SemgrepParser(custom_rule_ids={"checkease-hardcoded-secret"}).parse(raw)
    assert out.findings[0].hard_gate is False
    assert out.findings[1].hard_gate is False   # tiền tố giả mạo -> không tính
    assert out.findings[2].hard_gate is True    # custom thật -> chấp nhận


def test_parser_reads_custom_metadata():
    raw = {"results": [{
        "check_id": "checkease-sql-injection", "path": "a.py", "start": {"line": 1},
        "extra": {"severity": "ERROR", "metadata": {
            "category": "security", "checkease_severity": "Critical",
            "hard_gate": True, "cwe": "CWE-89",
            "impact": "HIGH", "confidence": "HIGH",
        }, "lines": "q"},
    }]}
    out = SemgrepParser(custom_rule_ids={"checkease-sql-injection"}).parse(raw)
    f = out.findings[0]
    assert f.final_severity == "Critical"
    assert f.impact == "HIGH" and f.confidence == "HIGH"
    assert f.hard_gate is True


def test_parser_surfaces_semgrep_errors_as_warnings():
    raw = {"errors": [{"message": "Timeout while scanning file"}], "results": []}
    out = SemgrepParser(custom_rule_ids=set()).parse(raw)
    assert out.findings == []
    assert any("Timeout" in w for w in out.warnings)


def test_fingerprint_stable_and_distinct():
    a1 = make_fingerprint("r", "a.py", "  x   =  1  ")  # whitespace khác
    a2 = make_fingerprint("r", "a.py", "x = 1")
    b = make_fingerprint("r", "a.py", "x = 2")
    assert a1 == a2          # chuẩn hóa whitespace => ổn định
    assert a1 != b


# ---------- Severity & Category Mapping ----------

def test_severity_matrix_warning_high_impact():
    """Case bắt buộc theo mục 8.4: WARNING×HIGH×HIGH -> Major."""
    assert map_severity("WARNING", "HIGH", "HIGH") == "Major"


def test_severity_cwe_override_floor():
    """CWE-89/CWE-798 luôn tối thiểu Major kể cả khi tool chỉ báo INFO."""
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-89") == "Major"
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-798") == "Major"


def test_severity_cwe_not_substring_matched():
    """CWE-780 KHÔNG được hưởng floor của CWE-78 (sửa lỗi khớp substring)."""
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-780") == "Minor"
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-7800") == "Minor"


def test_severity_levels_normalized():
    """impact/confidence lạ -> MEDIUM; ERROR×MEDIUM×LOW = Minor."""
    assert map_severity("ERROR", "banana", "LOW") == "Minor"


def test_severity_fallback_unknown_tool_severity():
    assert map_severity("WEIRD", "HIGH", "HIGH") == "Minor"


def test_category_mapping_and_fallback():
    assert map_category("security") == "Security"
    assert map_category("correctness") == "Reliability"
    assert map_category("maintainability") == "Maintainability"
    assert map_category("blah-blah-unknown") == "Maintainability"  # fallback
    assert map_category("") == "Maintainability"


# ---------- Scoring Engine ----------

def test_score_clean_project():
    r = compute_code_score([])
    assert r.code_score == 100.0 and r.status == "Pass"


def test_score_single_security_minor():
    f = _scored(severity="INFO")
    assert f.final_severity == "Minor"
    r = compute_code_score([f])
    assert r.breakdown["Security"] == 98.0                      # 100 - 2
    assert r.code_score == round(0.5 * 98 + 0.3 * 100 + 0.2 * 100, 2)  # 99.0
    assert r.status == "Pass"


def test_score_formula_full_mix():
    f1 = _scored(rule_id="s1", category="Security", severity="ERROR")
    f1.final_severity = "Critical"
    f2 = _scored(rule_id="r1", category="Reliability", severity="WARNING")
    f2.final_severity = "Major"
    f3 = _scored(rule_id="m1", category="Maintainability", severity="INFO")
    f3.final_severity = "Minor"
    r = compute_code_score([f1, f2, f3])
    # Security 100-20=80, Reliability 100-6=94, Maintainability 100-1=99
    assert r.breakdown == {"Security": 80.0, "Reliability": 94.0, "Maintainability": 99.0}
    assert r.code_score == round(0.5 * 80 + 0.3 * 94 + 0.2 * 99, 2)  # 89.0
    assert r.status == "Pass"


def test_score_maintainability_critical_treated_as_major():
    f = _scored(category="Maintainability", severity="ERROR", final_severity="Critical")
    r = compute_code_score([f])
    # Critical của Maintainability xử lý như Major: phạt 4, không 15
    assert r.breakdown["Maintainability"] == 96.0


def test_score_hard_gate_finding_is_critical():
    f = _scored(category="Security", severity="WARNING", hard_gate=True)
    r = compute_code_score([f])
    assert r.breakdown["Security"] == 80.0  # phạt Critical (20)


def test_score_dedup_by_fingerprint():
    f = _scored()
    g = _finding(rule_id="r1", file="a.py", line=1, fp=f.fingerprint, final_severity=f.final_severity)
    r = compute_code_score([f, g])
    r_single = compute_code_score([f])
    assert r.breakdown == r_single.breakdown  # chỉ tính 1 lần


def test_score_penalty_cap_limits_repeats():
    fs = [_finding(rule_id="dup", file=f"f{i}.py", line=1, fp=f"fp{i}",
                   final_severity="Minor") for i in range(200)]
    r = compute_code_score(fs, rule_penalty_cap=3)
    assert r.breakdown["Security"] == 94.0          # chỉ 3 lần được tính: 2*3 = 6
    assert r.counts["Security"]["Minor"] == 200     # counts vẫn phản ánh đủ 200
    assert any("trần penalty" in w for w in r.warnings)


def test_score_without_cap_score_collapses():
    fs = [_finding(rule_id="dup", file=f"f{i}.py", line=1, fp=f"fp{i}",
                   final_severity="Minor") for i in range(200)]
    r = compute_code_score(fs, rule_penalty_cap=10**9)
    assert r.breakdown["Security"] == 0.0  # 200*2 phạt => sụp 0


def test_score_status_thresholds():
    # 6 Critical security: Security=0 => 0.5*0+0.3*100+0.2*100 = 50 => Fail
    fs = [_finding(rule_id=f"c{i}", file=f"f{i}.py", line=1, fp=f"fp{i}",
                   final_severity="Critical") for i in range(6)]
    assert compute_code_score(fs).status == "Fail"
    assert compute_code_score(fs).code_score == 50.0

    # 3 Critical security: Security=40 => 0.5*40+30+20 = 70 => Warning
    assert compute_code_score(fs[:3]).status == "Warning"


def test_score_thresholds_are_configurable():
    f = _scored(severity="INFO")  # score 99
    assert compute_code_score([f]).status == "Pass"
    assert compute_code_score([f], pass_threshold=99.5).status == "Warning"


def test_score_unknown_category_goes_to_maintainability():
    """Category lạ không được làm finding biến mất khỏi điểm và counts."""
    f = _finding(category="", severity="INFO", final_severity="Minor")
    r = compute_code_score([f])
    assert r.breakdown["Maintainability"] == 99.0
    assert r.counts["Maintainability"]["Minor"] == 1
