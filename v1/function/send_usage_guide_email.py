"""将第一版使用守则 PDF 作为附件发送到用户邮箱（SMTP，见 api_config.ew_smtp_settings）。"""

from __future__ import annotations

import re
import smtplib
from email.message import EmailMessage

from function.api_config import ew_smtp_settings
from function.usage_guide_pdf import build_usage_guide_v1_pdf_bytes

_EMAIL_RE = re.compile(r"^[^@\s\r\n]+@[^@\s\r\n]+\.[^@\s\r\n]+$")


def validate_usage_guide_email(addr: str) -> str:
    addr = addr.strip()
    if "\r" in addr or "\n" in addr:
        raise ValueError("邮箱格式无效")
    if not _EMAIL_RE.match(addr) or len(addr) > 254:
        raise ValueError("邮箱格式无效")
    return addr


def send_usage_guide_pdf_email(to_addr: str) -> None:
    cfg = ew_smtp_settings()
    if not cfg:
        raise RuntimeError(
            "发信未配置：请设置 EW_SMTP_HOST、EW_SMTP_FROM（或 EW_SMTP_USER）等环境变量"
        )
    to_addr = validate_usage_guide_email(to_addr)
    pdf = build_usage_guide_v1_pdf_bytes()

    msg = EmailMessage()
    msg["Subject"] = "EW 数据工作台 · 使用守则（第一版）"
    msg["From"] = cfg["from_addr"]
    msg["To"] = to_addr
    msg.set_content(
        "您好，\n\n请查收附件：EW 第一版使用守则（PDF）。\n\n— EW 数据工作台\n",
        charset="utf-8",
    )
    msg.add_attachment(
        pdf,
        maintype="application",
        subtype="pdf",
        filename="EW_usage_guide_v1.pdf",
    )

    if cfg["use_ssl"]:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"])
    else:
        server = smtplib.SMTP(cfg["host"], cfg["port"])
    try:
        if cfg["use_starttls"]:
            server.starttls()
        if cfg["user"]:
            server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass
