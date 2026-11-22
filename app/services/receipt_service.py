import asyncio

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from weasyprint import HTML

from app.models.order import OrderStatus
from app.database import async_session
from app.models import Order, User
from app.services.email_service import send_email
from app.services.email_templates import build_receipt_email, render_receipt_html


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
        if order is None:
            logger.warning("Чек не отправлен | причина=заказ не найден order_id={}", order_id)
            return
        if order.receipt_sent:
            logger.debug("Чек пропущен | причина=уже отправлен order_id={}", order_id)
            return
        if order.status not in (OrderStatus.PAID, OrderStatus.COMPLETED):
            logger.debug("Чек пропущен | причина=статус заказа {} order_id={}",
                         getattr(order.status, "value", order.status), order_id)
            return
        user = await db.get(User, order.user_id)
        user_id = order.user_id  # запоминаем до commit для логов

        try:
            pdf = await build_receipt_pdf(order)
        except Exception:
            # Ошибка проглочена (return), нужен traceback
            logger.exception("Не удалось собрать PDF чека | order_id={} user_id={}", order_id, user_id)
            return

        content = build_receipt_email(order, user.name)
        ok = await send_email(
            user.email, content.subject, content.text, content.html,
            attachments=[(f"receipt_{order.id}.pdf", pdf, "application/pdf")],
        )
        if ok:
            order.receipt_sent = True
            await db.commit()
            logger.info("Чек отправлен | order_id={} user_id={}", order_id, user_id)
        else:
            # Причина с traceback записана в email_service, здесь её связь с заказом
            logger.warning("Чек не отправлен | причина=ошибка отправки письма order_id={} user_id={}",
                           order_id, user_id)