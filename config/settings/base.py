# Cấu hình chung

import os

# MinIO Configuration
MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ROOT_USER')
MINIO_SECRET_KEY = os.getenv('MINIO_ROOT_PASSWORD')
MINIO_BUCKET_NAME = os.getenv('MINIO_BUCKET_NAME')

# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']

# Task routing — nhánh Code chạy trên queue_sast riêng (mục 12.4)
CELERY_TASK_ROUTES = {
    'apps.code_analysis.tasks.start_sast_scan': {'queue': 'queue_sast'},
}

AUTH_USER_MODEL = 'accounts.User'

# === Source Code Analysis (nhánh Code — checklist mục 3, 8) ===
# TODO: đổi sang thư mục giải nén an toàn từ Artifact khi tích hợp xong
CODE_SCAN_TARGET_DIR = os.getenv('CODE_SCAN_TARGET_DIR', '.')
# Trần penalty mỗi rule (số lần lặp tối đa được tính điểm)
CODE_RULE_PENALTY_CAP = int(os.getenv('CODE_RULE_PENALTY_CAP', '3'))
# Ngưỡng Pass/Warning của CodeScore (mục 8.8)
CODE_PASS_THRESHOLD = float(os.getenv('CODE_PASS_THRESHOLD', '80'))
CODE_WARNING_THRESHOLD = float(os.getenv('CODE_WARNING_THRESHOLD', '60'))
# Allowlist secret theo project, phân tách bằng dấu phẩy (có ghi log khi dùng)
CODE_SECRET_ALLOWLIST = [
    p.strip() for p in os.getenv('CODE_SECRET_ALLOWLIST', '').split(',') if p.strip()
]
