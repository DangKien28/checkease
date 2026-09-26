"""Scoring Engine — công thức tính CodeScore (checklist mục 8).

CodeScore = 0.5*S_security + 0.3*S_reliability + 0.2*S_maintainability

- Bảng phạt điểm 3 nhóm × 3 mức severity (Critical/Major/Minor).
- Loại trùng lặp theo fingerprint trước khi tính.
- Trần penalty mỗi rule (rule_penalty_cap) — mặc định 3 lần lặp.
- Chỉ set CodeResult.status, không tự phán quyết final verdict.
"""

from dataclasses import dataclass, field

from apps.code_analysis.mappings import map_severity

WEIGHTS = {"Security": 0.5, "Reliability": 0.3, "Maintainability": 0.2}

# Bảng phạt: (category, severity) -> điểm trừ mỗi lần xuất hiện
# Maintainability không có Critical — Critical xử lý như Major
PENALTY_TABLE = {
    ("Security", "Critical"): 20.0,
    ("Security", "Major"): 8.0,
    ("Security", "Minor"): 2.0,
    ("Reliability", "Critical"): 15.0,
    ("Reliability", "Major"): 6.0,
    ("Reliability", "Minor"): 1.5,
    # Critical của Maintainability xử lý như Major
    ("Maintainability", "Critical"): 4.0,
    ("Maintainability", "Major"): 4.0,
    ("Maintainability", "Minor"): 1.0,
}

# Trần penalty mỗi rule: tối đa N lần lặp của 1 rule được tính điểm
DEFAULT_RULE_PENALTY_CAP = 3

# Ngưỡng Pass/Warning/Fail (mục 8.8)
PASS_THRESHOLD = 80.0
WARNING_THRESHOLD = 60.0

SEVERITY_RANK = {"Critical": 3, "Major": 2, "Minor": 1}


@dataclass
class CategoryScore:
    category: str
    raw_penalty: float = 0.0
    score: float = 100.0
    counts: dict = field(default_factory=dict)


@dataclass
class CodeScoreResult:
    code_score: float = 100.0
    status: str = "Pass"  # Pass | Warning | Fail
    breakdown: dict = field(default_factory=dict)
    counts: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)


def _clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))


def compute_code_score(findings: list, rule_penalty_cap: int = DEFAULT_RULE_PENALTY_CAP) -> CodeScoreResult:
    """Tính CodeScore từ list Finding (đã qua parser)."""
    # Bước 1: loại trùng lặp theo fingerprint
    seen = set()
    unique = []
    for f in findings:
        if f.fingerprint in seen:
            continue
        seen.add(f.fingerprint)
        unique.append(f)

    # Bước 2: đếm số lần mỗi rule xuất hiện trong mỗi (category, severity)
    rule_occurrences = {}  # (rule_id, category, severity) -> count
    for f in unique:
        # Tôn trọng final_severity đã set bởi pipeline (đã qua mapping + hard_gate);
        # chỉ tự map khi caller đưa Finding thô chưa qua pipeline.
        final_sev = getattr(f, "final_severity", None) or (
            "Critical" if f.hard_gate else map_severity(f.severity, cwe=f.cwe)
        )
        key = (f.rule_id, f.category, final_sev)
        rule_occurrences[key] = rule_occurrences.get(key, 0) + 1

    # Bước 3: tính penalty theo (category, severity), có trần mỗi rule
    cat_state = {c: CategoryScore(category=c) for c in WEIGHTS}
    for (rule_id, category, severity), count in sorted(rule_occurrences.items()):
        eff_count = min(count, rule_penalty_cap)
        penalty_per = PENALTY_TABLE.get((category, severity), 1.0)
        penalty = penalty_per * eff_count
        if category in cat_state:
            cat_state[category].raw_penalty += penalty
            cat_state[category].counts[severity] = (
                cat_state[category].counts.get(severity, 0) + count
            )

    # Bước 4: tính điểm từng nhóm và điểm tổng
    total = 0.0
    breakdown = {}
    for category, weight in WEIGHTS.items():
        cs = cat_state[category]
        cs.score = _clamp(100.0 - cs.raw_penalty)
        breakdown[category] = round(cs.score, 2)
        total += weight * cs.score
    code_score = round(_clamp(total), 2)

    # Bước 5: xác định status (chỉ set, không phán quyết verdict)
    if code_score >= PASS_THRESHOLD:
        status = "Pass"
    elif code_score >= WARNING_THRESHOLD:
        status = "Warning"
    else:
        status = "Fail"

    counts = {
        c: dict(cat_state[c].counts) for c in WEIGHTS
    }

    # Ghi warning nếu có rule bị chặn bởi trần penalty
    warnings = []
    for (rule_id, _cat, _sev), count in rule_occurrences.items():
        if count > rule_penalty_cap:
            warnings.append(
                f"Rule {rule_id} xuất hiện {count} lần, chỉ tính {rule_penalty_cap} lần (trần penalty)."
            )

    return CodeScoreResult(
        code_score=code_score,
        status=status,
        breakdown=breakdown,
        counts=counts,
        warnings=warnings,
    )
