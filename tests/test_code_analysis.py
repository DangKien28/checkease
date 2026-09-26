"""Unit tests cho luồng phân tích mã nguồn (checklist mục 5, 6, 7, 8)."""

from apps.code_analysis.findings_parser import Finding, SemgrepParser, make_fingerprint
from apps.code_analysis.mappings import map_category, map_severity
from apps.code_analysis.scoring import compute_code_score


def _f(rule_id="r1", category="Security", severity="WARNING", cwe="",
       file="a.py", line=1, fp=None, hard_gate=False):
    f = Finding(
        finding_id=f"{rule_id}:{file}:{line}",
        rule_id=rule_id, tool="semgrep", file=file, line=line,
        message="m", severity=severity, category=category, cwe=cwe,
        confidence="HIGH",
        fingerprint=fp or f"{rule_id}|{file}|{line}",
        hard_gate=hard_gate,
    )
    f.final_severity = "Critical" if hard_gate else map_severity(severity, cwe=cwe)
    return f


# ---------- Findings Parser ----------

def test_parser_extracts_basic_fields():
    raw = {"results": [{
        "check_id": "python.lang.security.dummy",
        "path": "app/x.py",
        "start": {"line": 10},
        "extra": {"message": "msg", "severity": "WARNING",
                  "metadata": {"cwe": "CWE-79"}, "lines": "bad()"},
    }]}
    out = SemgrepParser().parse(raw)
    assert len(out.findings) == 1
    f = out.findings[0]
    assert f.rule_id == "python.lang.security.dummy"
    assert f.file == "app/x.py" and f.line == 10
    assert f.severity == "WARNING" and f.cwe == "CWE-79"


def test_parser_hard_gate_only_for_custom_rules():
    """Rule cộng đồng có hard_gate=true vẫn phải bị bỏ qua (ràng buộc mục 4)."""
    raw = {"results": [
        {"check_id": "community.rule.x", "path": "a.py", "start": {"line": 1},
         "extra": {"severity": "ERROR", "metadata": {"hard_gate": True}, "lines": "x"}},
        {"check_id": "checkease-hardcoded-secret", "path": "a.py", "start": {"line": 2},
         "extra": {"severity": "ERROR", "metadata": {"hard_gate": True}, "lines": "y"}},
    ]}
    out = SemgrepParser().parse(raw)
    assert out.findings[0].hard_gate is False   # cộng đồng -> bỏ qua
    assert out.findings[1].hard_gate is True    # custom -> chấp nhận


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
    """CWE-89 (SQLi) luôn tối thiểu Major kể cả khi tool chỉ báo INFO."""
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-89") == "Major"
    assert map_severity("INFO", "LOW", "LOW", cwe="CWE-798") == "Major"


def test_severity_fallback_unknown_combo():
    assert map_severity("WEIRD", "HIGH", "HIGH") == "Minor"


def test_category_mapping_and_fallback():
    assert map_category("security") == "Security"
    assert map_category("correctness") == "Reliability"
    assert map_category("maintainability") == "Maintainability"
    assert map_category("blah-blah-unknown") == "Maintainability"  # fallback
    assert map_category("") == "Maintainability"


# ---------- Scoring Engine ----------

def _one(rule="r1", cat="Security", sev="WARNING", cwe="", hard_gate=False):
    return _f(rule_id=rule, category=cat, severity=sev, cwe=cwe, hard_gate=hard_gate)


def test_score_clean_project():
    r = compute_code_score([])
    assert r.code_score == 100.0 and r.status == "Pass"


def test_score_single_security_minor():
    f = _one(sev="INFO"); f.final_severity = "Minor"
    r = compute_code_score([f])
    assert r.breakdown["Security"] == 98.0            # 100 - 2
    assert r.code_score == round(0.5*98 + 0.3*100 + 0.2*100, 2)  # 99.0
    assert r.status == "Pass"


def test_score_formula_full_mix():
    f1 = _one(rule="s1", cat="Security", sev="ERROR"); f1.final_severity = "Critical"
    f2 = _one(rule="r1", cat="Reliability", sev="WARNING"); f2.final_severity = "Major"
    f3 = _one(rule="m1", cat="Maintainability", sev="INFO"); f3.final_severity = "Minor"
    r = compute_code_score([f1, f2, f3])
    # Security 100-20=80, Reliability 100-6=94, Maintainability 100-1=99
    assert r.breakdown == {"Security": 80.0, "Reliability": 94.0, "Maintainability": 99.0}
    assert r.code_score == round(0.5*80 + 0.3*94 + 0.2*99, 2)  # 89.0
    assert r.status == "Pass"


def test_score_maintainability_critical_treated_as_major():
    f = _one(cat="Maintainability", sev="ERROR", hard_gate=True)
    f.final_severity = "Critical"
    r = compute_code_score([f])
    # Critical của Maintainability xử lý như Major: phạt 4, không 15
    assert r.breakdown["Maintainability"] == 96.0


def test_score_hard_gate_finding_is_critical():
    f = _one(cat="Security", sev="WARNING", hard_gate=True)
    r = compute_code_score([f])
    assert r.breakdown["Security"] == 80.0  # phạt Critical (20)


def test_score_dedup_by_fingerprint():
    f = _one()
    g = _f(rule_id="r1", file="a.py", line=1, fp=f.fingerprint)  # trùng fingerprint
    g.final_severity = f.final_severity
    r = compute_code_score([f, g])
    r_single = compute_code_score([f])
    # chỉ tính 1 lần — kết quả giống khi chỉ có 1 finding
    assert r.breakdown == r_single.breakdown


def test_score_penalty_cap_limits_repeats():
    fs = [_f(rule_id="dup", file=f"f{i}.py", line=1, fp=f"fp{i}") for i in range(200)]
    for f in fs:
        f.final_severity = "Minor"
    r = compute_code_score(fs, rule_penalty_cap=3)
    # Chỉ 3 lần được tính: 2*3 = 6 phạt
    assert r.breakdown["Security"] == 94.0
    assert any("trần penalty" in w for w in r.warnings)


def test_score_without_cap_score_collapses():
    fs = [_f(rule_id="dup", file=f"f{i}.py", line=1, fp=f"fp{i}") for i in range(200)]
    for f in fs:
        f.final_severity = "Minor"
    r = compute_code_score(fs, rule_penalty_cap=10**9)
    assert r.breakdown["Security"] == 0.0  # 200*2 phạt => sụp 0


def test_score_status_thresholds():
    f = _one(rule="s1", sev="ERROR"); f.final_severity = "Critical"
    r = compute_code_score([f] * 3 if False else [f])
    assert r.status == "Pass"
    # 6 Critical security: Security=0, total=0.5*0+0.3*100+0.2*100=50 => Fail
    fs = [_f(rule_id=f"c{i}", file=f"f{i}.py", line=1, fp=f"fp{i}") for i in range(6)]
    for x in fs:
        x.final_severity = "Critical"
    r2 = compute_code_score(fs)
    assert r2.status == "Fail" and r2.code_score == 50.0
