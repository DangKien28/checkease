from typing import List
from apps.testing_analysis.schemas import TestCaseRecord, TestingResultSchema
from apps.testing_analysis.constants import PENALTY_WEIGHTS

class ScoringEngine:
    def calculate(self, records: List[TestCaseRecord]) -> TestingResultSchema:
        total = len(records)
        passed = 0
        failed = 0
        critical = 0
        major = 0
        minor = 0
        trivial = 0
        
        defects = []
        
        for r in records:
            if r.status == "PASS":
                passed += 1
            else:
                failed += 1
                
                sev = str(r.severity).title() if r.severity else "Minor"
                if sev == "Critical": critical += 1
                elif sev == "Major": major += 1
                elif sev == "Minor": minor += 1
                elif sev == "Trivial": trivial += 1
                else: minor += 1 # Default fallback
                
                defects.append({
                    "test_case_id": r.test_case_id,
                    "description": r.description,
                    "expected_result": r.expected_result,
                    "actual_result": r.actual_result,
                    "severity": sev,
                    "reason": r.reason
                })
                
        pass_rate = round((passed / total * 100) if total > 0 else 0.0, 2)
        
        penalty = (
            critical * PENALTY_WEIGHTS["Critical"] +
            major * PENALTY_WEIGHTS["Major"] +
            minor * PENALTY_WEIGHTS["Minor"] +
            trivial * PENALTY_WEIGHTS["Trivial"]
        )
        
        testing_score = max(0.0, 100.0 - penalty)
        
        return TestingResultSchema(
            total_test_cases=total,
            passed=passed,
            failed=failed,
            pass_rate=pass_rate,
            critical_count=critical,
            major_count=major,
            minor_count=minor,
            trivial_count=trivial,
            testing_score=float(testing_score),
            defects=defects
        )
