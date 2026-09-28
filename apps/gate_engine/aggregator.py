# ==============================================================================
# TÍCH HỢP & CHUYỂN ĐỔI BỞI: Đặng Trung Kiên
# NGƯỜI CODE THUẬT TOÁN: Nguyễn Tam Trung
# CƠ CHẾ THUẬT TOÁN: Đặng Trung kiên
# CHI TIẾT: Nguyễn Tam Trung được giao nhiệm vụ viết cơ chế tổng hợp điểm nhưng
# lại code độc lập bằng FastAPI (sai kiến trúc dự án). Đặng Trung Kiên đã bóc 
# tách phần thuật toán cốt lõi (class GateEngine) này và tích hợp trực tiếp vào 
# cấu trúc chuẩn của dự án Django.
# ==============================================================================

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GateResult:
                                                         

    score: float
    verdict: str


class GateEngine:
                                                                          

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"

    def __init__(self, w_test: float, w_code: float, pass_threshold: float = 80.0, warning_threshold: float = 60.0) -> None:
        if w_test < 0 or w_code < 0:
            raise ValueError("Weights must be non-negative.")
        if w_test + w_code == 0:
            raise ValueError("At least one weight must be greater than zero.")

        self.w_test = w_test
        self.w_code = w_code
        self.pass_threshold = pass_threshold
        self.warning_threshold = warning_threshold

    def calculate_score(self, test_score: float, code_score: float) -> float:
                                                                    
        self._validate_score(test_score, "test_score")
        self._validate_score(code_score, "code_score")
        return self.w_test * test_score + self.w_code * code_score

    def classify(self, score: float) -> str:
        self._validate_score(score, "score")
        if score < self.warning_threshold:
            return self.FAIL
        if score < self.pass_threshold:
            return self.WARNING
        return self.PASS

    def evaluate(
        self,
        test_score: float,
        code_score: float,
        errors: Iterable[Any] | None = None,
    ) -> GateResult:
                                                                             

                                                                           
                                                            
           
        score = self.calculate_score(test_score, code_score)
        if self._has_critical_error(errors):
            return GateResult(score=score, verdict=self.FAIL)
        return GateResult(score=score, verdict=self.classify(score))

    @staticmethod
    def _has_critical_error(errors: Iterable[Any] | None) -> bool:
        return any(GateEngine._error_severity(error).lower() == "critical" for error in errors or ())

    @staticmethod
    def _error_severity(error: Any) -> str:
        if isinstance(error, Mapping):
            severity = error.get("severity", "")
        elif isinstance(error, str):
            severity = error
        else:
            severity = getattr(error, "severity", "")
        return str(severity)

    @staticmethod
    def _validate_score(score: float, name: str) -> None:
        if not 0 <= score <= 100:
            raise ValueError(f"{name} must be between 0 and 100.")