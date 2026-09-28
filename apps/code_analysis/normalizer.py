import uuid
from typing import List, Dict, Any
from apps.code_analysis.schemas import Finding

class SemgrepNormalizer:
    def normalize(self, semgrep_json: Dict[str, Any]) -> List[Finding]:
        findings = []
        raw_results = semgrep_json.get("results", [])
        
        for item in raw_results:
            # 1. Ánh xạ Severity
            raw_severity = item.get("extra", {}).get("severity", "").upper()
            severity = "Minor"
            if raw_severity == "ERROR":
                severity = "Critical"
            elif raw_severity == "WARNING":
                severity = "Major"
            elif raw_severity == "INFO":
                severity = "Minor"
                
            # 2. Ánh xạ Category từ tags/metadata
            metadata = item.get("extra", {}).get("metadata", {})
            category = "Maintainability" # Default
            tags = metadata.get("category", "").lower()
            
            if "security" in tags:
                category = "Security"
            elif "correctness" in tags or "reliability" in tags:
                category = "Reliability"
                
            # 3. Bắt cờ hard_gate
            hard_gate = metadata.get("hard_gate", False)
            
            # 4. Tạo Object
            finding = Finding(
                finding_id=str(uuid.uuid4()),
                file=item.get("path", ""),
                line=item.get("start", {}).get("line", 0),
                message=item.get("extra", {}).get("message", ""),
                rule_id=item.get("check_id", ""),
                severity=severity,
                category=category,
                hard_gate=hard_gate,
                code_snippet=item.get("extra", {}).get("lines", "")
            )
            findings.append(finding)
            
        return findings
