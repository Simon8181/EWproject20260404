"""第一版《使用守则》PDF（ReportLab + 内置 CID 宋体，无需外置字体文件）。"""

from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

# 正文：与产品行为一致；更新时请同步改版本号与页脚日期。
USAGE_GUIDE_V1_TITLE = "EW 数据工作台 · 使用守则（第一版）"

USAGE_GUIDE_V1_SECTIONS: list[tuple[str, list[str]]] = [
    (
        "1. 适用范围",
        [
            "本守则适用于通过本服务访问 Google Sheet 同步数据、浏览在途订单（ew_orders）及关联功能的用户。",
            "具体权限以账号角色（开发者 / Boss / Broker）及环境配置为准。",
        ],
    ),
    (
        "2. 账号与安全",
        [
            "使用 config/ew_users.yaml 中的账号登录；会话依赖 EW_SESSION_SECRET 或 EW_ADMIN_TOKEN 签名。",
            "书签式访问可使用 URL 参数 token=（与 EW_ADMIN_TOKEN 一致）；请勿将令牌提交到公开仓库或截图外传。",
        ],
    ),
    (
        "3. 数据与订单列表",
        [
            "订单列表默认来自数据库表 ew_orders，主键为 ew_quote_no；若数据库不可用，可能回退为 Sheet 直连并提示。",
            "从 Sheet 刷新、格式化数据（邮编 / 距离等）等操作需具备相应权限（通常为开发者或有效令牌）。",
        ],
    ),
    (
        "4. 报价与「差价」展示",
        [
            "折叠行中的差价定义为：客户报价 − 司机价（与 A 列「待找车 / 已经安排」状态无关）。",
            "系统会对单元格内的金额、区间、备注式符号等做启发式解析；若首次算出的差价整体为负，会尝试优先依据「$」金额再算一次。",
            "若规范化后仍无法得到合理的非负结果，差价显示为「-」（不代表数值为零）。",
            "解析规则可能随版本调整；请以业务确认金额为准。",
        ],
    ),
    (
        "5. 配置与集成",
        [
            "Maps、数据库连接、同步规则等依赖 config 与环境变量；修改后通常需重启服务。",
            "配置页、集成页的可见范围因角色而异（Boss 多为只读）。",
        ],
    ),
    (
        "6. 免责与变更",
        [
            "本守则旨在说明常见用法与界面含义，不构成法律或商务承诺。",
            "第一版内容随产品迭代更新；更新日期见 PDF 页脚。",
        ],
    ),
]


def usage_guide_v1_json_payload() -> dict[str, Any]:
    """与 PDF 同源；供 ``GET /docs/ew-usage-guide-v1.json`` 使用。"""
    return {
        "version": 1,
        "title": USAGE_GUIDE_V1_TITLE,
        "sections": [
            {"heading": h, "paragraphs": list(lines)}
            for h, lines in USAGE_GUIDE_V1_SECTIONS
        ],
        "related": {
            "pdf_open_url": "/docs/ew-usage-guide-v1.pdf",
            "pdf_download_url": "/docs/ew-usage-guide-v1.pdf?download=1",
            "pdf_filename_ascii": "EW_usage_guide_v1.pdf",
        },
    }


def _paragraph_xml(lines: list[str]) -> str:
    parts = []
    for line in lines:
        parts.append(escape(line.strip()))
    return "<br/>".join(parts)


def build_usage_guide_v1_pdf_bytes() -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading1"],
        fontName="STSong-Light",
        fontSize=16,
        leading=22,
        spaceAfter=14,
    )
    h_style = ParagraphStyle(
        "H",
        parent=styles["Heading2"],
        fontName="STSong-Light",
        fontSize=12,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=10.5,
        leading=16,
        spaceAfter=10,
    )
    foot_style = ParagraphStyle(
        "Foot",
        parent=styles["Normal"],
        fontName="STSong-Light",
        fontSize=9,
        leading=14,
        textColor=colors.HexColor("#64748b"),
    )

    story: list = []
    story.append(Paragraph(escape(USAGE_GUIDE_V1_TITLE), title_style))
    story.append(Spacer(1, 0.3 * cm))

    for heading, lines in USAGE_GUIDE_V1_SECTIONS:
        story.append(Paragraph(escape(heading), h_style))
        story.append(Paragraph(_paragraph_xml(lines), body_style))

    story.append(Spacer(1, 0.8 * cm))
    story.append(
        Paragraph(
            escape("— 文档版本：v1 · 生成方式：EW 服务内置 PDF —"),
            foot_style,
        )
    )

    doc.build(story)
    return buf.getvalue()
