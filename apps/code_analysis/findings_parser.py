"""Findings Parser — chuẩn hóa JSON Semgrep sang cấu trúc nội bộ (checklist mục 5).

Nguyên lý Open-Closed: BaseFindingsParser cho phép thêm parser khác (SARIF) sau
này mà không sửa Scoring.
"""

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Finding:
    finding_id: str
    rule_id: str
    tool: str
    file: str
    line: int
    message: str
    severity: str          # severity công cụ gốc: ERROR | WARNING | INFO
    category: str          # Security | Reliability | Maintainability (điền ở bước mapping)
    cwe: str
    confidence: str
    remediation: str = ""
    fingerprint: str = ""
    hard_gate: bool = False


@dataclass
class ParsedFindings:
    findings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


class BaseFindingsParser(ABC):
    @abstractmethod
    def parse(self, raw: dict) -> ParsedFindings:
        ...


def make_fingerprint(rule_id: str, file_path: str, line_content: str) -> str:
    """Fingerprint ổn định: băm rule_id + file + nội dung dòng đã chuẩn hóa.

    Chống nhân đôi khi dòng dịch chuyển giữa các lần chạy.
    """
    normalized = " ".join(line_content.split())
    h = hashlib.sha256()
    h.update(f"{rule_id}|{file_path}|{normalized}".encode())
    return h.hexdigest()


class SemgrepParser(BaseFindingsParser):
    """Parser JSON output của Semgrep."""

    def parse(self, raw: dict) -> ParsedFindings:
        out = ParsedFindings()
        for item in raw.get("results", []):
            check = item.get("check_id", "")
            # rule_id không chứa dấu chấm (tức là rule custom trong rules/custom/)
            is_custom = "." not in check
            path = item.get("path", "")
            start = item.get("start", {})
            line = start.get("line", 0)
            extra = item.get("extra", {})
            lines_text = item.get("extra", {}).get("lines", "")
            metadata = extra.get("metadata", {})

            f = Finding(
                finding_id=f"{check}:{path}:{line}",
                rule_id=check,
                tool="semgrep",
                file=path,
                line=line,
                message=extra.get("message", ""),
                severity=extra.get("severity", "INFO").upper(),
                category=metadata.get("category", ""),
                cwe=str(metadata.get("cwe", "")),
                confidence=metadata.get("confidence", "UNKNOWN").upper(),
                remediation=extra.get("fix", ""),
                fingerprint=make_fingerprint(check, path, lines_text),
                # Chỉ rule custom (không chứa dot) mới được hưởng hard_gate
                hard_gate=is_custom and metadata.get("hard_gate", False) is True,
            )
            out.findings.append(f)
        return out
