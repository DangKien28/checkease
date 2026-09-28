# ==============================================================================
# TÍCH HỢP & CHUYỂN ĐỔI BỞI: Đặng Trung Kiên
# TÁC GIẢ GỐC (Logic vẽ PDF): Nguyễn Tam Trung
# CHI TIẾT: Module xuất PDF này ban đầu bị Nguyễn Tam Trung để ở một project 
# FastAPI bên ngoài. Đặng Trung Kiên đã cấu trúc lại, đưa code sinh báo cáo 
# reportlab này về đúng app `gate_engine` của dự án chính để có thể sử dụng.
# ==============================================================================
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


import os
from django.conf import settings
FONT_DIR = os.path.join(settings.BASE_DIR, 'static', 'fonts')
pdfmetrics.registerFont(TTFont('Roboto', os.path.join(FONT_DIR, 'Roboto-Regular.ttf')))
pdfmetrics.registerFont(TTFont('Roboto-Bold', os.path.join(FONT_DIR, 'Roboto-Bold.ttf')))
FONT_REGULAR = "Roboto"
FONT_BOLD = "Roboto-Bold"


PAGE_TEXT = colors.HexColor("#0f172a")
MUTED_TEXT = colors.HexColor("#64748b")
BORDER = colors.HexColor("#cbd5e1")
BRAND = colors.HexColor("#047857")
INK = colors.HexColor("#0b1220")
MINT_TEXT = colors.HexColor("#a7f3d0")
VERDICT_COLORS = {
    "PASS": (colors.HexColor("#dcfce7"), colors.HexColor("#15803d")),
    "WARNING": (colors.HexColor("#fef3c7"), colors.HexColor("#b45309")),
    "FAIL": (colors.HexColor("#fee2e2"), colors.HexColor("#b91c1c")),
    "INSUFFICIENT": (colors.HexColor("#e2e8f0"), colors.HexColor("#475569")),
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def generate_pdf_report(data: dict, output_filename: str = "release_report.pdf") -> str:
                                                             

                                                                        
                                                                            
                                                    
       
    project, version, result, run = _normalise_payload(data)
    config = result.get("config_snapshot") or {}
    testing = result.get("testing") or {}
    code = result.get("code") or {}
    verdict = str(result.get("verdict", "INSUFFICIENT")).upper()
    verdict_bg, verdict_fg = VERDICT_COLORS.get(verdict, VERDICT_COLORS["INSUFFICIENT"])

    styles = _build_styles()
    document = SimpleDocTemplate(
        output_filename,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"Checkease Report - {_value(project, 'name', 'N/A')}",
    )

    story: list[Any] = []
    story.extend(_header(run, result.get("final_score"), styles))
    story.append(_section_heading("1. Release Metadata", styles))
    story.append(_metadata_table(project, version, run, config, styles))
    story.append(_section_heading("2. Executive Summary", styles))
    story.extend(_executive_summary(result, testing, code, config, verdict, verdict_bg, verdict_fg, styles))
    story.append(_section_heading("3. Top Issues (tối đa 10, sắp theo mức nghiêm trọng)", styles))
    story.append(_top_issues_table(testing, code, styles))
    story.append(_section_heading("4. Raw Metrics", styles))
    story.append(_raw_metrics_table(testing, code, styles))
    story.append(_section_heading("5. Reasons (lý do phán quyết — truy vết được)", styles))
    story.append(_reasons_table(
        result.get("reasons") or [],
        verdict,
        testing,
        code,
        config,
        result.get("final_score"),
        styles,
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "Báo cáo là ảnh chụp bất biến của một lần phân tích (AnalysisRun), phục vụ lưu hồ sơ "
        "và nghiệm thu. Phần tóm tắt AI chỉ mang tính tham khảo; phán quyết do Gate Engine "
        "tất định đưa ra.", styles["muted"],
    ))
    document.build(story)
    return output_filename


def _normalise_payload(data: dict) -> tuple[dict, dict, dict, dict]:
    project = data.get("project") or {}
    version = data.get("version") or {}
    run = version.get("run") or data.get("run") or {}
    result = _normalise_result(run.get("result") or data.get("result") or data, project, version, run)
    return project, version, result, run


def _normalise_result(raw: dict, project: dict, version: dict, run: dict) -> dict:
                                                                               
    source = dict(raw or {})
    testing = dict(source.get("testing") or source.get("test_analysis") or {})
    test_analysis = source.get("test_analysis") or {}
    testing["passed"] = testing.get("passed", test_analysis.get("pass_count", 0))
    testing["failed"] = testing.get("failed", test_analysis.get("fail_count", 0))
    testing["unknown_count"] = testing.get("unknown_count", test_analysis.get("unknown_count", 0))
    testing["total_test_cases"] = testing.get("total_test_cases", test_analysis.get("total_cases", 0))
    testing["evaluated"] = testing.get("evaluated", testing["total_test_cases"])
    testing["pass_rate"] = testing.get("pass_rate", test_analysis.get("pass_rate", 0))
    testing["testing_score"] = testing.get("testing_score", source.get("test_score", testing["pass_rate"]))
    for key in ("critical_count", "major_count", "minor_count", "trivial_count"):
        testing[key] = testing.get(key, 0)
    testing["defects"] = testing.get("defects") or []

    code = dict(source.get("code") or source.get("code_analysis") or {})
    code_analysis = source.get("code_analysis") or {}
    breakdown = dict(code.get("breakdown") or {})
    for key in ("security", "reliability", "maintainability"):
        breakdown[key] = breakdown.get(key, code_analysis.get(key, 0))
    code["breakdown"] = breakdown
    code["code_score"] = code.get("code_score", source.get("code_score", 0))
    code["status"] = code.get("status") or ("Pass" if _number(code["code_score"]) >= 50 else "Fail")
    code["total_findings"] = code.get("total_findings", 0)
    for key in ("critical_count", "major_count", "minor_count", "trivial_count"):
        code[key] = code.get(key, 0)
    code["findings"] = code.get("findings") or []

    config = dict(source.get("config_snapshot") or {})
    config.setdefault("tier", project.get("tier", 0))
    config.setdefault("w1", project.get("w_testing", 0.5))
    config.setdefault("w2", project.get("w_code", 0.5))
    config.setdefault("hardGateCritical", project.get("hard_gate_critical_test", False))
    final_score = source.get("final_score")
    if final_score is None:
        final_score = _number(config["w1"]) * _number(testing["testing_score"]) + _number(config["w2"]) * _number(code["code_score"])
    verdict = str(source.get("verdict") or "INSUFFICIENT").upper()
    return {
        **source,
        "final_score": final_score,
        "verdict": verdict,
        "config_snapshot": config,
        "testing": testing,
        "code": code,
        "reasons": source.get("reasons") or [],
        "ai_summary": source.get("ai_summary") or {},
    }


def _build_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("ReportTitle", parent=sample["Title"], fontName=FONT_BOLD, fontSize=22, leading=26, textColor=PAGE_TEXT, spaceAfter=2),
        "muted": ParagraphStyle("Muted", parent=sample["BodyText"], fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=MUTED_TEXT),
        "body": ParagraphStyle("Body", parent=sample["BodyText"], fontName=FONT_REGULAR, fontSize=9, leading=13, textColor=PAGE_TEXT),
        "section": ParagraphStyle("Section", parent=sample["Heading2"], fontName=FONT_BOLD, fontSize=15, leading=18, textColor=PAGE_TEXT, spaceBefore=14, spaceAfter=8),
        "table": ParagraphStyle("Table", parent=sample["BodyText"], fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=PAGE_TEXT),
        "mono": ParagraphStyle("Mono", parent=sample["BodyText"], fontName=FONT_REGULAR, fontSize=8.5, leading=11, textColor=PAGE_TEXT),
        "formula": ParagraphStyle("Formula", parent=sample["BodyText"], fontName=FONT_REGULAR, fontSize=10, leading=14, textColor=MINT_TEXT),
        "verdict": ParagraphStyle("Verdict", parent=sample["BodyText"], fontName=FONT_BOLD, fontSize=20, leading=24, alignment=TA_LEFT),
        "score": ParagraphStyle("Score", parent=sample["BodyText"], fontName=FONT_BOLD, fontSize=30, leading=34, alignment=TA_RIGHT, textColor=PAGE_TEXT),
    }


def _header(run: dict, final_score: Any, styles: dict) -> list[Any]:
    score = "—" if final_score is None else f"{float(final_score):.1f}"
    report_id = _value(run, "id", "N/A")
    header = Table(
        [[
            [Paragraph("Checkease — Báo cáo sẵn sàng phát hành", styles["title"]), Paragraph(
                f"Release Readiness Gateway · Report ID {_escape(report_id)} · Sinh tự động sau khi Run hoàn tất", styles["muted"]
            )],
            [Paragraph(score, styles["score"]), Paragraph("Final Score / 100", ParagraphStyle("ScoreLabel", parent=styles["muted"], fontName=FONT_REGULAR, alignment=TA_RIGHT))],
        ]],
        colWidths=[125 * mm, 48 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, -1), (-1, -1), 3, BRAND), ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ]),
    )
    return [header, Spacer(1, 7)]


def _metadata_table(project: dict, version: dict, run: dict, config: dict, styles: dict) -> Table:
    tier = config.get("tier", _value(project, "tier", "N/A"))
    threshold = config.get("thresholdOverride")
    threshold_text = f"Ghi đè: PASS ≥ {threshold.get('pass')}, WARNING ≥ {threshold.get('warning')}" if threshold else f"Theo Tier {tier}"
    rows = [
        ["Dự án", _value(project, "name", "N/A"), "Version", f"v{_value(version, 'seq', 'N/A')} — {_value(version, 'label', 'N/A')}"],
        ["Tier", f"Tier {tier}", "Thời điểm", _format_datetime(_value(run, "finished_at", datetime.now().isoformat()))],
        ["Trọng số", f"W1 = {_value(config, 'w1', _value(project, 'w_testing', 'N/A'))}, W2 = {_value(config, 'w2', _value(project, 'w_code', 'N/A'))}", "Hard Gate Critical", "Bật" if config.get("hardGateCritical", True) else "Tắt"],
        ["Ngưỡng", threshold_text, "Gate rules", "gate-1.2.0"],
        ["Bằng chứng", _file_names(version.get("source_files")), "Tài liệu test", _file_names(version.get("test_files"))],
    ]
    return _data_table(rows, [24 * mm, 62 * mm, 31 * mm, 56 * mm], styles)


def _executive_summary(result: dict, testing: dict, code: dict, config: dict, verdict: str, bg: Any, fg: Any, styles: dict) -> list[Any]:
    summary = Table(
        [[Paragraph(verdict, ParagraphStyle("VerdictText", parent=styles["verdict"], fontName=FONT_BOLD, textColor=fg)), Paragraph(
            f"<b>Testing Score:</b> {_escape(testing.get('testing_score', '—'))} · <b>Code Score:</b> {_escape(code.get('code_score', '—'))}<br/>"
            f"<font color=\"#64748b\">Pass rate: {_escape(testing.get('pass_rate', '—'))}% · Findings: {_escape(code.get('total_findings', '—'))} · Critical defects: {_escape(testing.get('critical_count', '—'))}</font>", styles["body"])]],
        colWidths=[45 * mm, 128 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), bg), ("BOX", (0, 0), (0, 0), 0.8, fg),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 12),
            ("RIGHTPADDING", (0, 0), (0, 0), 12), ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]),
    )
    w1, w2 = config.get("w1", 0.5), config.get("w2", 0.5)
    score = "—" if result.get("final_score") is None else f"{float(result['final_score']):.1f}"
    formula = Table([[Paragraph(f"{_escape(w1)} × {_escape(testing.get('testing_score', '—'))} + {_escape(w2)} × {_escape(code.get('code_score', '—'))} = <b>{score}</b>", styles["formula"])]], colWidths=[173 * mm], style=TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    ai_summary = ((result.get("ai_summary") or {}).get("testing") or {}).get("summary", "")
    return [summary, Spacer(1, 7), formula, Spacer(1, 7), Paragraph(_escape(ai_summary), styles["body"])]


def _top_issues_table(testing: dict, code: dict, styles: dict) -> Table:
    defects, findings, issues = testing.get("defects") or [], code.get("findings") or [], []
    issues.extend([["Test", d.get("test_case_id", "—"), "—", d.get("description", "—"), d.get("severity", "—")] for d in defects if d.get("severity") == "Critical"])
    issues.extend([["Code", f.get("rule", "—"), f"{f.get('file', '—')}:{f.get('line', '—')}", f.get("message", "—"), f.get("severity", "—")] for f in findings if f.get("severity") == "Critical" or f.get("hard_gate")])
    issues.extend([["Code", f.get("rule", "—"), f"{f.get('file', '—')}:{f.get('line', '—')}", f.get("message", "—"), f.get("severity", "—")] for f in findings if f.get("severity") == "Major"])
    issues.extend([["Test", d.get("test_case_id", "—"), "—", d.get("description", "—"), d.get("severity", "—")] for d in defects if d.get("severity") != "Critical"])
    rows = [["#", "Nguồn", "Vị trí", "Mô tả", "Mức"]] + [[str(i), *issue] for i, issue in enumerate(issues[:10], 1)]
    return _data_table(rows, [9 * mm, 20 * mm, 35 * mm, 80 * mm, 29 * mm], styles, header=True)


def _raw_metrics_table(testing: dict, code: dict, styles: dict) -> Table:
    test_rows = [["Tổng case", testing.get("total_test_cases", "—")], ["Đã đánh giá", testing.get("evaluated", "—")], ["PASS", testing.get("passed", "—")], ["FAIL", testing.get("failed", "—")], ["UNKNOWN", testing.get("unknown_count", "—")], ["Critical / Major", f"{testing.get('critical_count', '—')} / {testing.get('major_count', '—')}"], ["Minor / Trivial", f"{testing.get('minor_count', '—')} / {testing.get('trivial_count', '—')}"], ["Testing Score", testing.get("testing_score", "—")]]
    code_rows = [["Tổng findings", code.get("total_findings", "—")], ["Trạng thái nhánh", code.get("status", "—")], ["Security / Reliability / Maintainability", _breakdown(code)], ["Critical / Major", f"{code.get('critical_count', '—')} / {code.get('major_count', '—')}"], ["Minor / Trivial", f"{code.get('minor_count', '—')} / {code.get('trivial_count', '—')}"], ["Hard Gate (secret)", "KÍCH HOẠT" if code.get("hard_gate_triggered") else "Không"], ["Code Score", code.get("code_score", "—")]]
    nested = Table([[ [Paragraph("<b>Nhánh Testing</b>", styles["body"]), _data_table(test_rows, [50 * mm, 35 * mm], styles)], [Paragraph("<b>Nhánh Source Code</b>", styles["body"]), _data_table(code_rows, [50 * mm, 35 * mm], styles)] ]], colWidths=[85 * mm, 85 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 8)]))
    return nested


def _reasons_table(
    reasons: list[dict],
    verdict: str,
    testing: dict,
    code: dict,
    config: dict,
    final_score: Any,
    styles: dict,
) -> Table:
    rows = []
    for reason in reasons:
        kind = str(reason.get("kind", "info"))
        code_color = {"cap": colors.HexColor("#78350f"), "block": colors.HexColor("#7f1d1d"), "info": colors.HexColor("#1e3a5f")}.get(kind, INK)
        rows.append([Paragraph(_escape(reason.get("code", "—")), ParagraphStyle(f"ReasonCode{len(rows)}", parent=styles["mono"], fontName=FONT_BOLD, textColor=MINT_TEXT, backColor=code_color, borderPadding=3)), Paragraph(f"{_escape(reason.get('message', '—'))}<br/><font color=\"#64748b\">Lớp {_escape(reason.get('layer', '—'))} · kind={_escape(kind)} · {_escape(reason.get('rule_version', '—'))}</font>", styles["table"])])
    if not rows:
        reason_code = "SCORE_EVALUATED"
        message = (
            f"FinalScore = {_display_number(config.get('w1', 0.5))} × "
            f"{_display_number(testing.get('testing_score', 0))} + "
            f"{_display_number(config.get('w2', 0.5))} × "
            f"{_display_number(code.get('code_score', 0))} = "
            f"{_display_number(final_score)} → {verdict}"
        )
        reason_style = ParagraphStyle(
            "ReasonFallbackCode",
            parent=styles["mono"],
            fontName=FONT_BOLD,
            textColor=MINT_TEXT,
            backColor=colors.HexColor("#1e3a5f"),
            borderPadding=3,
        )
        rows = [[
            Paragraph(reason_code, reason_style),
            Paragraph(
                f"{_escape(message)}<br/><font color=\"#64748b\">Lớp L2 · kind=info · gate-1.2.0</font>",
                styles["table"],
            ),
        ]]
    return Table(rows, colWidths=[42 * mm, 131 * mm], style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))


def _data_table(rows: list[list[Any]], widths: list[float], styles: dict, header: bool = False) -> Table:
    converted = [[Paragraph(_escape(cell), styles["table"]) for cell in row] for row in rows]
    commands = [("GRID", (0, 0), (-1, -1), 0.5, BORDER), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]
    if header:
        commands.extend([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")), ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD)])
    else:
        commands.append(("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]))
    return Table(converted, colWidths=widths, repeatRows=1 if header else 0, style=TableStyle(commands))


def _section_heading(text: str, styles: dict) -> Table:
    return Table([[Paragraph(text, styles["section"])]], colWidths=[173 * mm], style=TableStyle([("LINEBELOW", (0, 0), (-1, -1), 2, PAGE_TEXT), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))


def _value(mapping: dict, key: str, default: Any) -> Any:
    return mapping.get(key, default)


def _escape(value: Any) -> str:
    return escape(str(value), quote=True)


def _display_number(value: Any) -> str:
    number = _number(value)
    return f"{number:.1f}".rstrip("0").rstrip(".")


def _file_names(files: Any) -> str:
    if not files:
        return "—"
    return ", ".join(str(item.get("name", "—")) if isinstance(item, dict) else str(item) for item in files)


def _format_datetime(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return str(value or "—")


def _breakdown(code: dict) -> str:
    breakdown = code.get("breakdown") or {}
    return f"{breakdown.get('security', '—')} / {breakdown.get('reliability', '—')} / {breakdown.get('maintainability', '—')}"


if __name__ == "__main__":
    sample_data = {
        "project": {"name": "Checkease Demo", "tier": 2, "w_testing": 0.5, "w_code": 0.5},
        "version": {"seq": 3, "label": "release-candidate", "source_files": [{"name": "source.zip"}], "test_files": [{"name": "test-results.xml"}], "run": {"id": "run-demo-001", "finished_at": datetime.now().isoformat(), "result": {"verdict": "PASS", "final_score": 85.0, "config_snapshot": {"tier": 2, "w1": 0.5, "w2": 0.5, "hardGateCritical": True}, "testing": {"testing_score": 88, "pass_rate": 92, "total_test_cases": 50, "evaluated": 50, "passed": 46, "failed": 2, "unknown_count": 2, "critical_count": 0, "major_count": 1, "minor_count": 1, "trivial_count": 0, "defects": []}, "code": {"code_score": 82, "total_findings": 3, "status": "Pass", "breakdown": {"security": 85, "reliability": 80, "maintainability": 82}, "critical_count": 0, "major_count": 1, "minor_count": 2, "trivial_count": 0, "hard_gate_triggered": False, "findings": []}, "reasons": [{"code": "ALL_CHECKS_PASSED", "layer": "L2", "kind": "info", "message": "Tất cả kiểm tra đều đạt.", "rule_version": "gate-1.2.0"}], "ai_summary": {"testing": {"summary": "Testing evidence is consistent and release-ready."}}}}},
    }
    print(f"PDF report generated: {generate_pdf_report(sample_data)}")