from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import BalanceTransaction, Brand, Cart, CartItem, Order, OrderItem, Product, User
from app.models.balance_transaction import TransactionType
from app.models.order import OrderStatus
from app.utils.database import run_in_transaction

async def _create(db: AsyncSession, user_id: int, shipping_address: str) -> int:
    # Блокируем корзину с помощью with_for_update() для защиты от двух одновременных запросов
    cart = await db.scalar(select(Cart).where(Cart.user_id == user_id).with_for_update())
    if cart is None:
        raise HTTPException(400, "Корзина пуста")

    # Сортировка по product_id нужна для единого порядка блокировок
    # (Взаимодействие с предметами корзины должно быть по порядку)
    items = (await db.scalars(
        select(CartItem).where(CartItem.cart_id == cart.id).order_by(CartItem.product_id)
    )).all()
    if not items:
        raise HTTPException(400, "Корзина пуста")

    # Товары тоже блокируем и обновляем их состояние в SQLAlchemy
    products = {
        p.id: p for p in (await db.scalars(
            select(Product)
            .where(Product.id.in_([i.product_id for i in items]))
            .order_by(Product.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )).all()
    }

    # Бренды собираются для выявления неактивных брендов и вследствие недоступных товаров
    brand_ids = {p.brand_id for p in products.values() if p.brand_id is not None}
    hidden_brands = set()
    if brand_ids:
        hidden_brands = set((await db.scalars(
            select(Brand.id).where(Brand.id.in_(brand_ids), Brand.is_active.is_(False))
        )).all())

    # Собираем все проблемы для отображения
    problems = []
    for i in items:
        p = products[i.product_id]

        # Неактивный продукт или бренд
        if not p.is_active or p.brand_id in hidden_brands:
            problems.append({"product_id": p.id, "name": p.name, "reason": "inactive"})
        # Превышение количества допустимого товара
        elif i.quantity > p.stock_quantity:
            problems.append({"product_id": p.id, "name": p.name,
                             "reason": "insufficient_stock", "available": p.stock_quantity})
    if problems:
        raise HTTPException(409, detail={
            "code": "cart_unavailable",
            "message": "Некоторые товары недоступны",
            "items": problems,
        })

    # Создание заказа
    total = sum((products[i.product_id].price * i.quantity for i in items), Decimal("0"))
    order = Order(user_id=user_id, total_amount=total, shipping_address=shipping_address)
    db.add(order)
    await db.flush()

    # Создание OrderItemов и списание остатка товара
    for i in items:
        p = products[i.product_id]
        db.add(OrderItem(order_id=order.id, product_id=p.id, product_name=p.name,
                         product_price=p.price, quantity=i.quantity))
        await db.execute(
            update(Product).where(Product.id == p.id)
            .values(stock_quantity=Product.stock_quantity - i.quantity)
        )

    # Очищаем корзину
    await db.execute(delete(CartItem).where(CartItem.cart_id == cart.id))
    return order.id


async def create_order(db: AsyncSession, user_id: int, shipping_address: str) -> int:
    """Функция для создания заказа с возможностью rollback"""
    try:
        order_id = await _create(db, user_id, shipping_address)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return order_id


# noinspection PyTypeChecker
async def get_order(db: AsyncSession, order_id: int) -> Any:
    return await db.scalar(
        select(Order).where(Order.id == order_id)
        .options(selectinload(Order.items))
        .execution_options(populate_existing=True)
    )


# noinspection PyTypeChecker
async def list_orders(db: AsyncSession, user_id: int) -> list[Order]:
    return (await db.scalars(
        select(Order).where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.id.desc())
        .execution_options(populate_existing=True)
    )).all()


# noinspection PyTypeChecker
async def _lock_order(db: AsyncSession, order_id: int, user_id: int) -> Order:
    # Фильтр по user_id обязателен: иначе можно оплатить или отменить чужой заказ по id
    order = await db.scalar(
        select(Order).where(Order.id == order_id, Order.user_id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if order is None:
        raise HTTPException(404, "Заказ не найден")
    return order


# noinspection PyTypeChecker
async def _lock_user(db: AsyncSession, user_id: int) -> User:
    return await db.scalar(
        select(User).where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def _pay(db: AsyncSession, order_id: int, user_id: int) -> None:
    order = await _lock_order(db, order_id, user_id)
    # Статус проверяем уже под блокировкой: двойной клик не спишет деньги дважды
    if order.status != OrderStatus.PENDING:
        raise HTTPException(409, "Заказ нельзя оплатить: он уже не в ожидании оплаты")

    user = await _lock_user(db, user_id)
    if user.balance < order.total_amount:
        raise HTTPException(402, "Недостаточно средств на балансе")

    user.balance -= order.total_amount
    order.status = OrderStatus.PAID
    db.add(BalanceTransaction(user_id=user_id, order_id=order.id,
                              amount=-order.total_amount, type=TransactionType.PAYMENT))


async def _cancel(db: AsyncSession, order_id: int, user_id: int) -> None:
    order = await _lock_order(db, order_id, user_id)
    if order.status not in (OrderStatus.PENDING, OrderStatus.PAID):
        raise HTTPException(409, "Этот заказ нельзя отменить")

    # Оплаченный заказ: возвращаем деньги на баланс
    if order.status == OrderStatus.PAID:
        user = await _lock_user(db, user_id)
        user.balance += order.total_amount
        db.add(BalanceTransaction(user_id=user_id, order_id=order.id,
                                  amount=order.total_amount, type=TransactionType.REFUND))

    # Возвращаем остатки: один атомарный UPDATE на позицию, порядок по product_id
    items = (await db.scalars(
        select(OrderItem).where(OrderItem.order_id == order.id).order_by(OrderItem.product_id)
    )).all()
    for i in items:
        await db.execute(
            update(Product).where(Product.id == i.product_id)
            .values(stock_quantity=Product.stock_quantity + i.quantity)
        )

    order.status = OrderStatus.CANCELLED


async def pay_order(db: AsyncSession, order_id: int, user_id: int) -> int:
    return await run_in_transaction(db, _pay, order_id, user_id)


async def cancel_order(db: AsyncSession, order_id: int, user_id: int) -> int:
    return await run_in_transaction(db, _cancel, order_id, user_id)