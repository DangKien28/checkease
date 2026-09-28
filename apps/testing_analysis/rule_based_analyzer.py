from typing import List, Tuple
from apps.testing_analysis.schemas import TestCaseRecord
from apps.testing_analysis.constants import STATUS_PASS_REGEX, STATUS_FAIL_REGEX, SEVERITY_MAPPING

class RuleBasedAnalyzer:
    def analyze(self, records: List[TestCaseRecord]) -> Tuple[List[TestCaseRecord], List[TestCaseRecord]]:
        """
        Phân tích dựa trên luật.
        Trả về 2 danh sách: (đã xử lý xong, cần AI xử lý)
        """
        completed_records = []
        needs_ai_records = []

        for record in records:
            # Ánh xạ Status
            if record.status:
                status_str = str(record.status).strip()
                if STATUS_PASS_REGEX.match(status_str):
                    record.status = "PASS"
                elif STATUS_FAIL_REGEX.match(status_str):
                    record.status = "FAIL"

            # Ánh xạ Severity nếu có
            if record.severity:
                sev_str = str(record.severity).strip().lower()
                mapped_sev = None
                for std_sev, keywords in SEVERITY_MAPPING.items():
                    if any(kw in sev_str for kw in keywords):
                        mapped_sev = std_sev
                        break
                if mapped_sev:
                    record.severity = mapped_sev

            # Phân loại: Cần AI nếu FAIL nhưng thiếu severity hoặc reason (nếu cần thiết)
            if record.status == "FAIL" and not record.severity:
                needs_ai_records.append(record)
            else:
                completed_records.append(record)

        return completed_records, needs_ai_records
