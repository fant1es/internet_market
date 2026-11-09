from typing import Annotated

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.order import OrderStatus
from app.schemas.order import CheckoutIn, OrderOut
from app.services import order_service
from app.services.receipt_service import send_receipt_for_order

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