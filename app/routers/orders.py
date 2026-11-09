from typing import Annotated

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi import HTTPException, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.order import CheckoutIn, OrderOut
from app.services import order_service
from app.services.order_service import get_order
from app.services.receipt_service import send_receipt_for_order
from app.models.order import OrderStatus
from app.services.receipt_service import build_receipt_pdf
from app.services.email_templates import render_receipt_html

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut, status_code=201, summary="Оформить заказ из корзины")
async def checkout(data: CheckoutIn,
                   db: AsyncSession = Depends(get_db),
                   user=Depends(get_current_user)):
    order_id = await order_service.create_order(db, user.id, data.shipping_address, data.contact_phone)
    return await order_service.get_order(db, order_id)


@router.get("", response_model=list[OrderOut], summary="История заказов")
async def my_orders(
        status: Annotated[list[OrderStatus] | None, Query(description="Фильтр по статусам")] = None,
        limit: Annotated[int | None, Query(description="Максимум отображаемых заказов")] = None,
        db: AsyncSession = Depends(get_db),
        user=Depends(get_current_user)):
    return await order_service.list_orders(db, user.id, status, limit)


@router.post("/{order_id}/pay", response_model=OrderOut, summary="Оплатить заказ с баланса")
async def pay(order_id: int, background_tasks: BackgroundTasks,
              db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await order_service.pay_order(db, order_id, user.id)
    background_tasks.add_task(send_receipt_for_order, order_id)
    return await order_service.get_order(db, order_id)


@router.post("/{order_id}/cancel", response_model=OrderOut, summary="Отменить заказ")
async def cancel(order_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    await order_service.cancel_order(db, order_id, user.id)
    return await order_service.get_order(db, order_id)

# --- Раздел с роутами для чеков ----------------------------------------------------------------------------
async def _get_receipt_order(db, order_id: int, user):
    is_admin = user.role == "admin"          # поправь под свою модель роли
    order = await get_order(db, order_id, None if is_admin else user.id)
    if order is None or order.status not in (OrderStatus.PAID, OrderStatus.COMPLETED):
        raise HTTPException(404, "Чек не найден")
    return order


@router.get("/{order_id}/receipt", response_class=HTMLResponse)
async def receipt_page(order_id: int, db: AsyncSession = Depends(get_db),
                       user=Depends(get_current_user)):
    return render_receipt_html(await _get_receipt_order(db, order_id, user))


@router.get("/{order_id}/receipt.pdf")
async def receipt_pdf(order_id: int, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    pdf = await build_receipt_pdf(await _get_receipt_order(db, order_id, user))
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="receipt_{order_id}.pdf"',
        "Cache-Control": "private, no-store",
    })