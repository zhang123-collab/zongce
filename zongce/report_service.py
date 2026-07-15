import io
import os

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _font_name() -> str:
    candidates = [
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\msyh.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        if os.path.isfile(path):
            try:
                pdfmetrics.registerFont(TTFont("ZongceCJK", path))
                return "ZongceCJK"
            except Exception:
                continue
    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light"
    except Exception:
        return "Helvetica"


def build_student_report(result: dict) -> io.BytesIO:
    output = io.BytesIO()
    font = _font_name()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="本科生综合测评个人报告",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("ZTitle", parent=styles["Title"], fontName=font, fontSize=18, leading=25, alignment=TA_CENTER)
    normal = ParagraphStyle("ZNormal", parent=styles["BodyText"], fontName=font, fontSize=10, leading=16)
    story = [Paragraph("本科生综合测评个人报告", title), Spacer(1, 8 * mm)]
    summary = [
        ["姓名", result.get("studentName", ""), "学号", result.get("studentId", "")],
        ["班级", result.get("className", ""), "测评年度", result.get("assessmentYear", "")],
        ["班级排名", result.get("classRank", "-"), "年级排名", result.get("gradeRank", "-")],
    ]
    table = Table(summary, colWidths=[26 * mm, 55 * mm, 26 * mm, 55 * mm])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8EEF9")),
        ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8EEF9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 7 * mm), Paragraph("成绩构成", normal)])
    scores = [
        ["思想品德", "学业成绩", "学术创新", "学生工作", "扣分", "总分"],
        [result.get("moralScore", 0), result.get("academicScore", 0), result.get("innovationScore", 0), result.get("workScore", 0), result.get("deductionScore", 0), result.get("totalScore", 0)],
    ]
    score_table = Table(scores, colWidths=[27 * mm] * 6)
    score_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A8A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([score_table, Spacer(1, 7 * mm), Paragraph("加分明细", normal)])
    bonus_rows = [["类别", "子类", "计分策略", "计入分"]]
    for item in result.get("bonusDetails", []):
        bonus_rows.append([item.get("category", ""), item.get("subCategory", ""), "取最高" if item.get("policy") == 1 else "累加", item.get("countedScore", 0)])
    if len(bonus_rows) == 1:
        bonus_rows.append(["暂无", "", "", 0])
    bonus_table = Table(bonus_rows, colWidths=[45 * mm, 55 * mm, 30 * mm, 30 * mm], repeatRows=1)
    bonus_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF9")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([bonus_table, Spacer(1, 8 * mm), Paragraph("说明：本报告由系统根据已审核申请和当前规则自动生成，最终结果以学院正式公示为准。", normal)])
    document.build(story)
    output.seek(0)
    return output
