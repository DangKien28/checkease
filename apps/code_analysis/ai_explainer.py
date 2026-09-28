import os
import json
from typing import List, Dict, Any

class AIExplainer:
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
                import logging
                logging.getLogger(__name__).error(f"Lỗi khởi tạo Gemini AI: {e}")
                self.model = None

    def explain(self, findings: List[Any]) -> Dict[str, str]:
        """Nhận list findings (dict hoặc Finding dataclass) và trả về dict map finding_id -> explanation."""
        if not findings or not self.model:
            return {}
            
        norm_findings = []
        for f in findings:
            if hasattr(f, "__dataclass_fields__"):
                from dataclasses import asdict
                norm_findings.append(asdict(f))
            elif isinstance(f, dict):
                norm_findings.append(f)
            else:
                norm_findings.append({
                    "finding_id": getattr(f, "finding_id", ""),
                    "rule_id": getattr(f, "rule_id", ""),
                    "message": getattr(f, "message", ""),
                    "file": getattr(f, "file", ""),
                    "line": getattr(f, "line", 0),
                    "category": getattr(f, "category", ""),
                    "final_severity": getattr(f, "final_severity", ""),
                })
        findings = norm_findings
            
        # Bước 4.1: Gom cụm (Clustering) theo rule_id
        clusters = {}
        for f in findings:
            rule_id = f.get("rule_id", "unknown")
            if rule_id not in clusters:
                clusters[rule_id] = []
            clusters[rule_id].append(f)
            
        representative_findings = [cluster[0] for cluster in clusters.values()]
        
        # Sắp xếp ưu tiên Security/Critical
        def sort_key(f):
            return (
                f.get("category") != "Security", 
                f.get("final_severity") != "Critical", 
                f.get("final_severity") != "Major"
            )
            
        findings_to_explain = sorted(representative_findings, key=sort_key)[:15]
        
        prompt_data = []
        for f in findings_to_explain:
            prompt_data.append({
                "finding_id": f.get("finding_id"),
                "rule": f.get("rule_id"),
                "message": f.get("message"),
                "occurrences": len(clusters[f.get("rule_id", "unknown")])
            })
            
        prompt_path = os.path.join(os.path.dirname(__file__), 'llm_prompts', 'source_defect_prompt.txt')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as file:
                system_prompt = file.read()
        except FileNotFoundError:
            system_prompt = "Hãy giải thích rủi ro và cách khắc phục cho các lỗi phần mềm sau. Trả về format [{'finding_id': '...', 'ai_explanation': '...'}]."
            
        try:
            response = self.model.generate_content(f"{system_prompt}\n\nDữ liệu lỗi (đã gom cụm):\n{json.dumps(prompt_data, ensure_ascii=False)}")
            result_json = json.loads(response.text)
            
            explanation_map = {}
            for item in result_json:
                finding_id = item.get("finding_id")
                explanation = item.get("ai_explanation")
                if finding_id and explanation:
                    explanation_map[finding_id] = explanation
            
            # Broadcast explanation cho toàn cụm
            final_explanations = {}
            for f in findings:
                fid = f.get("finding_id")
                rule_id = f.get("rule_id", "unknown")
                rep_id = clusters[rule_id][0].get("finding_id")
                if rep_id in explanation_map:
                    final_explanations[fid] = explanation_map[rep_id]
                    
            return final_explanations
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Lỗi AI Explainer: {e}")
            return {}
