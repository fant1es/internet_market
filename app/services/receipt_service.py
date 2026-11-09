import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.order import OrderStatus
from app.database import async_session
from app.models import Order, User
from app.services.email_service import send_email
from app.services.email_templates import build_receipt_email, render_receipt_html

logger = logging.getLogger(__name__)


def _to_pdf(html: str) -> bytes:
    return HTML(string=html).write_pdf()


async def build_receipt_pdf(order) -> bytes:
    html = render_receipt_html(order) # Быстрый рендер в основном потоке
    return await asyncio.to_thread(_to_pdf, html) # Тяжёлая часть в отдельном потоке


# noinspection PyTypeChecker
async def send_receipt_for_order(order_id: int) -> None:
    async with async_session() as db:
        order = await db.scalar(
            select(Order).where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        if (not order or order.receipt_sent
                or order.status not in (OrderStatus.PAID, OrderStatus.COMPLETED)):
            return
        user = await db.get(User, order.user_id)

        try:
            pdf = await build_receipt_pdf(order)
        except Exception:
            logger.exception("Не удалось собрать PDF чека для заказа %s", order_id)
            return

        content = build_receipt_email(order, user.name)
        ok = await send_email(
            user.email, content.subject, content.text, content.html,
            attachments=[(f"receipt_{order.id}.pdf", pdf, "application/pdf")],
        )
        if ok:
            order.receipt_sent = True
            await db.commit()
            logger.info("Чек по заказу %s отправлен на %s", order_id, user.email)