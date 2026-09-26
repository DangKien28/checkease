"""Severity & Category Mapping (checklist mục 6, 7).

Không dùng ánh xạ thô ERROR→Critical. Dùng bảng ma trận severity × impact ×
confidence + bảng ghi đè theo CWE. Bảng đặt trong config riêng để chỉnh sửa
mà không đụng logic.
"""

# --- Bảng ánh xạ severity: (tool_severity, impact, confidence) -> final_severity
# impact/confidence: HIGH | MEDIUM | LOW
# Final: Critical | Major | Minor
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

# Fallback nếu tổ hợp không có trong bảng (an toàn: coi là Minor)
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


SEVERITY_MAP_VERSION = "1.0"


def map_category(semgrep_category: str) -> str:
    key = (semgrep_category or "").strip().lower()
    if not key:
        return CATEGORY_FALLBACK
    for k, v in CATEGORY_MAP.items():
        if k in key:
            return v
    return CATEGORY_FALLBACK


def map_severity(tool_severity: str, impact: str = "MEDIUM",
                 confidence: str = "MEDIUM", cwe: str = "") -> str:
    # Bước 1: ghi đè theo CWE
    if cwe:
        for cwe_key, floor in CWE_OVERRIDE_MIN.items():
            if cwe and cwe_key.lower() in cwe.lower():
                mapped = SEVERITY_MATRIX.get(
                    (tool_severity.upper(), impact.upper(), confidence.upper()),
                    SEVERITY_FALLBACK,
                )
                rank = {"Critical": 3, "Major": 2, "Minor": 1}
                return floor if rank.get(mapped, 0) < rank[floor] else mapped
    # Bước 2: tra bảng ma trận
    return SEVERITY_MATRIX.get(
        (tool_severity.upper(), impact.upper(), confidence.upper()),
        SEVERITY_FALLBACK,
    )
