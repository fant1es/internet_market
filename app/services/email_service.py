import logging
import smtplib
from email.message import EmailMessage

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)

# Имя содержимого, само содержимое в байтах и MIME-тип (application/pdf например)
Attachment = tuple[str, bytes, str]

async def send_email(to: str, subject: str, text: str,
                     html: str, attachments: list[Attachment] | None = None) -> bool:
    """Отправляет письмо. Возвращает True при успехе, ошибки только логируются.
    Для их обработки идет работа с True/False"""
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text) # обязательно текстовая версия письма

    if html:
        msg.add_alternative(html, subtype="html")
    for filename, data, mime in attachments or []:
        maintype, subtype = mime.split("/", 1)
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            start_tls=settings.smtp_starttls,
            timeout=10
        )
    except (aiosmtplib.SMTPException, OSError):
        logger.exception("Не удалось отправить письмо на %s (тема: %s)", to, subject)
        return False

    return True