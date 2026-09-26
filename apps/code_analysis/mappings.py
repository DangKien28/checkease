"""Severity & Category Mapping (checklist mục 6, 7).

- Không dùng ánh xạ thô ERROR→Critical: dùng ma trận severity × impact × confidence
  + bảng ghi đè tối thiểu theo CWE (trích CWE bằng regex, tránh khớp substring
  kiểu "cwe-79" nằm trong "cwe-798").
- Bảng đặt trong config riêng để chỉnh mà không sửa logic; phiên bản bảng được
  ghi vào scan_meta qua SEVERITY_MAP_VERSION.
"""

import re

# --- Ma trận severity: (tool_severity, impact, confidence) -> final_severity
# impact/confidence: HIGH | MEDIUM | LOW; final: Critical | Major | Minor
SEVERITY_MATRIX = {
    ("ERROR", "HIGH", "HIGH"): "Critical",
    ("ERROR", "HIGH", "MEDIUM"): "Critical",
    ("ERROR", "HIGH", "LOW"): "Major",
    ("ERROR", "MEDIUM", "HIGH"): "Major",
    ("ERROR", "MEDIUM", "MEDIUM"): "Major",
    ("ERROR", "MEDIUM", "LOW"): "Minor",
    ("ERROR", "LOW", "HIGH"): "Minor",
    ("ERROR", "LOW", "MEDIUM"): "Minor",
    ("ERROR", "LOW", "LOW"): "Minor",
    ("WARNING", "HIGH", "HIGH"): "Major",
    ("WARNING", "HIGH", "MEDIUM"): "Major",
    ("WARNING", "HIGH", "LOW"): "Minor",
    ("WARNING", "MEDIUM", "HIGH"): "Major",
    ("WARNING", "MEDIUM", "MEDIUM"): "Minor",
    ("WARNING", "MEDIUM", "LOW"): "Minor",
    ("WARNING", "LOW", "HIGH"): "Minor",
    ("WARNING", "LOW", "MEDIUM"): "Minor",
    ("WARNING", "LOW", "LOW"): "Minor",
    ("INFO", "HIGH", "HIGH"): "Minor",
    ("INFO", "HIGH", "MEDIUM"): "Minor",
    ("INFO", "HIGH", "LOW"): "Minor",
    ("INFO", "MEDIUM", "HIGH"): "Minor",
    ("INFO", "MEDIUM", "MEDIUM"): "Minor",
    ("INFO", "MEDIUM", "LOW"): "Minor",
    ("INFO", "LOW", "HIGH"): "Minor",
    ("INFO", "LOW", "MEDIUM"): "Minor",
    ("INFO", "LOW", "LOW"): "Minor",
}

# Ghi đè theo CWE: các CWE nguy hiểm luôn tối thiểu Major
CWE_OVERRIDE_MIN = {
    "CWE-89": "Major",   # SQL Injection
    "CWE-78": "Major",   # OS Command Injection
    "CWE-798": "Major",  # Hardcoded credentials
    "CWE-79": "Major",   # XSS
    "CWE-502": "Major",  # Deserialization
}

# Fallback khi tổ hợp không có trong bảng
SEVERITY_FALLBACK_BY_TOOL = {"ERROR": "Major", "WARNING": "Minor", "INFO": "Minor"}
SEVERITY_FALLBACK = "Minor"

# --- Bảng ánh xạ category Semgrep -> 3 nhóm Checkease
CATEGORY_MAP = {
    "security": "Security",
    "correctness": "Reliability",
    "bug": "Reliability",
    "maintainability": "Maintainability",
    "performance": "Reliability",
    "portability": "Maintainability",
    "convention": "Maintainability",
}
CATEGORY_FALLBACK = "Maintainability"

SEVERITY_MAP_VERSION = "1.1"

_CWE_RE = re.compile(r"cwe[-_ ]?(\d+)", re.IGNORECASE)
_VALID_LEVELS = {"HIGH", "MEDIUM", "LOW"}
_RANK = {"Critical": 3, "Major": 2, "Minor": 1}


def _norm_level(value: str, default: str = "MEDIUM") -> str:
    value = (value or "").strip().upper()
    return value if value in _VALID_LEVELS else default


def _cwe_floors(cwe: str) -> list:
    floors = []
    for match in _CWE_RE.finditer(cwe or ""):
        key = f"CWE-{match.group(1)}"
        if key in CWE_OVERRIDE_MIN:
            floors.append(CWE_OVERRIDE_MIN[key])
    return floors


def map_severity(tool_severity: str, impact: str = "MEDIUM",
                 confidence: str = "MEDIUM", cwe: str = "") -> str:
    severity = (tool_severity or "").strip().upper()
    mapped = SEVERITY_MATRIX.get(
        (severity, _norm_level(impact), _norm_level(confidence))
    ) or SEVERITY_FALLBACK_BY_TOOL.get(severity, SEVERITY_FALLBACK)

    floors = _cwe_floors(cwe)
    if floors:
        highest = max(floors, key=lambda f: _RANK[f])
        if _RANK[mapped] < _RANK[highest]:
            return highest
    return mapped


def map_category(semgrep_category: str) -> str:
    key = (semgrep_category or "").strip().lower()
    if not key:
        return CATEGORY_FALLBACK
    for k, v in CATEGORY_MAP.items():
        if k in key:
            return v
    return CATEGORY_FALLBACK
