from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class TestCaseRecord:
    test_case_id: str
    description: Optional[str] = None
    steps: Optional[str] = None
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None
    status: Optional[str] = None
    severity: Optional[str] = None
    reason: Optional[str] = None

@dataclass
class AISummary:
    summary: str
    recommendation: str

@dataclass
class TestingResultSchema:
    total_test_cases: int
    passed: int
    failed: int
    pass_rate: float
    critical_count: int
    major_count: int
    minor_count: int
    trivial_count: int
    testing_score: float
    defects: List[dict] = field(default_factory=list)
    ai_summary: Optional[dict] = None
