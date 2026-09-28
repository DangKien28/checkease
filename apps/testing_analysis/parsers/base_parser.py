from abc import ABC, abstractmethod
from typing import List
from apps.testing_analysis.schemas import TestCaseRecord
from apps.testing_analysis.constants import COLUMN_SYNONYMS

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> List[TestCaseRecord]:
        pass

    def _normalize_column_name(self, col_name: str) -> str:
        if not col_name:
            return ""
        col_name = str(col_name).strip().lower()
        for standard_field, synonyms in COLUMN_SYNONYMS.items():
            if any(syn in col_name for syn in synonyms):
                return standard_field
        return ""
