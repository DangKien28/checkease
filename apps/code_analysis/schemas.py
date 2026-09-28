from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Finding:
    finding_id: str
    file: str
    line: int
    message: str
    rule_id: str
    severity: str # Critical, Major, Minor, Trivial
    category: str # Security, Reliability, Maintainability
    hard_gate: bool
    code_snippet: Optional[str] = None
    ai_explanation: Optional[str] = None

@dataclass
class ScoreBreakdown:
    security_score: float
    reliability_score: float
    maintainability_score: float

@dataclass
class CodeResultSchema:
    code_score: float
    status: str
    hard_gate_triggered: bool
    findings: List[Finding] = field(default_factory=list)
    score_breakdown: Optional[ScoreBreakdown] = None
    ai_summary: Optional[dict] = None
