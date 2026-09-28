import os
import json
from typing import List
from apps.testing_analysis.schemas import TestCaseRecord

class AISemanticAnalyzer:
    def __init__(self):
        self.model = None
        self.api_key = None
        
        try:
            from apps.core.models import SystemSetting
            setting = SystemSetting.objects.filter(key="api_key_gemini").first()
            if setting and setting.value:
                self.api_key = setting.value
        except Exception:
            self.api_key = os.environ.get("GEMINI_API_KEY")
            
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY")

        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-3.8-flash', generation_config={"response_mime_type": "application/json"})
            except Exception as e:
                print(f"Lỗi khởi tạo Gemini AI: {e}")
                self.model = None

    def analyze_defects(self, records: List[TestCaseRecord]) -> List[TestCaseRecord]:
        if not records:
            return records
            
        if not self.model:
            # Fallback nếu chưa cấu hình AI
            for r in records:
                r.severity = "Minor"
                r.reason = "Fallback: AI chưa được cấu hình."
            return records
            
        # Gom nhóm records để prompt
        prompt_data = []
        for i, r in enumerate(records):
            prompt_data.append({
                "index": i,
                "description": r.description or "",
                "expected": r.expected_result or "",
                "actual": r.actual_result or ""
            })
            
        # Load system prompt từ file
        prompt_path = os.path.join(os.path.dirname(__file__), 'llm_prompts', 'defect_analysis_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = "Bạn là chuyên gia kiểm thử. Phân tích lỗi và trả về mảng JSON: [{'index': int, 'severity_label': str, 'reason': str}]"
        
        try:
            response = self.model.generate_content(f"{system_prompt}\n\nDữ liệu lỗi:\n{json.dumps(prompt_data, ensure_ascii=False)}")
            result_json = json.loads(response.text)
            
            for item in result_json:
                idx = item.get("index")
                if idx is not None and 0 <= idx < len(records):
                    records[idx].severity = item.get("severity_label", "Minor")
                    records[idx].reason = item.get("reason", "")
        except Exception as e:
            print(f"Lỗi gọi AI: {e}")
            for r in records:
                r.severity = "Minor"
                r.reason = "Lỗi kết nối AI."
                
        return records

    def generate_executive_summary(self, stats_data: dict) -> dict:
        if not self.model:
            return {
                "summary": f"Dự án đạt điểm {stats_data.get('testing_score')} với tỷ lệ Pass {stats_data.get('pass_rate')}%.",
                "recommendation": "Cần cấu hình AI để xem khuyến nghị chi tiết."
            }
            
        # Load system prompt từ file
        prompt_path = os.path.join(os.path.dirname(__file__), 'llm_prompts', 'executive_summary_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()
        except FileNotFoundError:
            system_prompt = "Bạn là chuyên gia QA. Tóm tắt tình trạng. Trả về JSON: {'summary': '...', 'recommendation': '...'}"
        
        try:
            response = self.model.generate_content(f"{system_prompt}\n\nThống kê:\n{json.dumps(stats_data, ensure_ascii=False)}")
            result_json = json.loads(response.text)
            return {
                "summary": result_json.get("summary", ""),
                "recommendation": result_json.get("recommendation", "")
            }
        except Exception as e:
            print(f"Lỗi gọi AI summary: {e}")
            return {
                "summary": "Lỗi kết nối AI.",
                "recommendation": ""
            }
