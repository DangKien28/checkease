import re

# Từ điển ánh xạ cột
COLUMN_SYNONYMS = {
    "test_case_id": ["test id", "case id", "mã kịch bản", "tc id", "mã tc", "#", "no.", "id"],
    "description": ["mô tả", "test scenario", "description", "summary", "mục đích", "tên kịch bản"],
    "steps": ["các bước thực hiện", "action", "test steps", "hướng dẫn", "thao tác", "steps", "bước"],
    "expected_result": ["kết quả mong đợi", "expected", "expected behavior", "kết quả dự kiến", "mong đợi"],
    "actual_result": ["kết quả thực tế", "actual", "actual behavior", "current result", "thực tế"],
    "status": ["trạng thái", "result", "test result", "pass/fail", "kết quả đánh giá", "kết quả", "status"],
    "severity": ["mức độ nghiêm trọng", "priority", "severity", "mức độ lỗi", "độ ưu tiên", "mức độ"],
}

# Regex nhận diện Status
STATUS_PASS_REGEX = re.compile(r'^(pass|passed|success|đạt|ok|✅|true)$', re.IGNORECASE)
STATUS_FAIL_REGEX = re.compile(r'^(fail|failed|not pass|thất bại|ng|❌|false)$', re.IGNORECASE)

# Từ khóa phân loại Severity
SEVERITY_MAPPING = {
    "Critical": ["blocker", "critical", "fatal", "nghiêm trọng"],
    "Major": ["major", "high", "cao"],
    "Minor": ["minor", "medium", "trung bình", "med"],
    "Trivial": ["trivial", "low", "thấp"]
}

# Trọng số phạt
PENALTY_WEIGHTS = {
    "Critical": 25,
    "Major": 15,
    "Minor": 5,
    "Trivial": 1
}
