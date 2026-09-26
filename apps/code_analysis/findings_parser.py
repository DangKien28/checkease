"""Findings Parser — chuẩn hóa JSON Semgrep sang cấu trúc nội bộ (checklist mục 5).

- Nguyên lý Open-Closed: BaseFindingsParser cho phép thêm parser khác (SARIF)
  sau này mà không sửa Scoring.
- Ràng buộc bảo mật: chỉ rule nằm trong rules/custom/ (do Checkease viết) mới
  được đọc field `hard_gate`. Đối chiếu bằng danh sách id đọc trực tiếp từ thư
  mục rule — KHÔNG dùng heuristic kiểu "id không có dấu chấm".
"""

import hashlib
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path

CUSTOM_RULES_DIR = Path(__file__).resolve().parent / "rules" / "custom"

_VALID_SEVERITIES = {"Critical", "Major", "Minor"}
_ID_LINE_RE = re.compile(r"""(?m)^\s*(?:-\s*)?id:\s*["']?([A-Za-z0-9_.\-]+)""")


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
    impact: str = "MEDIUM"
    final_severity: str = ""  # do rule custom khai báo hoặc pipeline tự map


@dataclass
class ParsedFindings:
    findings: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def load_custom_rule_ids(custom_dir: Path | None = None) -> set:
    """Đọc id của các rule trong rules/custom/ (nguồn duy nhất được tin cậy).

    Dùng PyYAML nếu có; nếu không thì fallback regex để vẫn hoạt động.
    """
    directory = Path(custom_dir) if custom_dir else CUSTOM_RULES_DIR
    ids = set()
    if not directory.exists():
        return ids
    for path in sorted(set([*directory.rglob("*.yaml"), *directory.rglob("*.yml")])):
        text = path.read_text(encoding="utf-8", errors="ignore")
        parsed = None
        try:
            import yaml

            data = yaml.safe_load(text)
            if isinstance(data, dict):
                if isinstance(data.get("rules"), list):
                    parsed = {
                        str(r.get("id"))
                        for r in data["rules"]
                        if isinstance(r, dict) and r.get("id")
                    }
                elif data.get("id"):
                    parsed = {str(data["id"])}
        except Exception:
            parsed = None
        if parsed is None:
            parsed = set(_ID_LINE_RE.findall(text))
        ids.update(parsed)
    return ids


def make_fingerprint(rule_id: str, file_path: str, line_content: str) -> str:
    """Fingerprint ổn định: băm rule_id + file + nội dung dòng đã chuẩn hóa.

    Chống nhân đôi khi dòng dịch chuyển giữa các lần chạy.
    """
    normalized = " ".join(line_content.split())
    h = hashlib.sha256()
    h.update(f"{rule_id}|{file_path}|{normalized}".encode())
    return h.hexdigest()


class BaseFindingsParser(ABC):
    @abstractmethod
    def parse(self, raw: dict) -> ParsedFindings:  # pragma: no cover - interface
        ...


class SemgrepParser(BaseFindingsParser):
    """Parser JSON output của Semgrep."""

    def __init__(self, custom_rule_ids: set | None = None):
        # Cho phép inject để test; mặc định đọc từ rules/custom/ (fail-closed:
        # thư mục rỗng => không rule nào được hưởng hard_gate).
        self.custom_rule_ids = (
            set(custom_rule_ids) if custom_rule_ids is not None else load_custom_rule_ids()
        )

    def _is_custom(self, check_id: str) -> bool:
        # Đối chiếu CHÍNH XÁC: runner đã truyền --no-rewrite-rule-ids nên check_id
        # phải trùng id khai báo; không chấp nhận biến thể có tiền tố (chống giả mạo).
        return check_id in self.custom_rule_ids

    def parse(self, raw: dict) -> ParsedFindings:
        out = ParsedFindings()
        # Lỗi (warnings) mà Semgrep trả trong JSON — không được bỏ qua âm thầm
        for err in (raw or {}).get("errors") or []:
            if isinstance(err, dict):
                msg = err.get("message") or err.get("type") or str(err)
            else:
                msg = str(err)
            out.warnings.append(f"semgrep: {msg}")

        for item in (raw or {}).get("results") or []:
            check = item.get("check_id", "")
            path = item.get("path", "")
            start = item.get("start") or {}
            line = start.get("line", 0)
            extra = item.get("extra") or {}
            metadata = extra.get("metadata") or {}
            lines_text = extra.get("lines", "")
            is_custom = self._is_custom(check)

            declared = str(metadata.get("checkease_severity", "") or "").strip().title()
            final_severity = declared if declared in _VALID_SEVERITIES else ""

            out.findings.append(Finding(
                finding_id=f"{check}:{path}:{line}",
                rule_id=check,
                tool="semgrep",
                file=path,
                line=line,
                message=extra.get("message", ""),
                severity=str(extra.get("severity", "INFO")).upper(),
                category=str(metadata.get("category", "") or ""),
                cwe=str(metadata.get("cwe", "") or ""),
                confidence=str(metadata.get("confidence", "UNKNOWN") or "UNKNOWN").upper(),
                impact=str(metadata.get("impact", "MEDIUM") or "MEDIUM").upper(),
                remediation=extra.get("fix", ""),
                fingerprint=make_fingerprint(check, path, lines_text),
                # Chỉ rule custom (đối chiếu theo id trong rules/custom/) mới được
                # đọc hard_gate; rule cộng đồng/vendor khai báo field này bị bỏ qua.
                hard_gate=bool(is_custom and metadata.get("hard_gate") is True),
                final_severity=final_severity,
            ))
        return out
