from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Category, Order, Product, User
from app.models.balance_transaction import BalanceTransaction
from app.models.order import OrderStatus
from app.services.excel_service import DATETIME, MONEY, Column, Sheet, build_xlsx, to_local

STATUS_RU = {
    OrderStatus.PENDING: "Ожидает оплаты",
    OrderStatus.PAID: "Оплачен",
    OrderStatus.COMPLETED: "Выполнен",
    OrderStatus.CANCELLED: "Отменён",
}


async def stock_report(db: AsyncSession) -> bytes:
    """Создание таблицы с данными о товарах на складе."""
    result = await db.execute(
        select(Product.sku, Product.name, Brand.name, Category.name,
               Product.price, Product.stock_quantity, Product.is_active)
        .outerjoin(Brand, Product.brand_id == Brand.id)
        .outerjoin(Category, Product.category_id == Category.id)
        .order_by(Product.name)
    )
    rows = [(sku, name, brand, cat, price, qty, price * qty, "Да" if active else "Нет")
            for sku, name, brand, cat, price, qty, active in result.all()]
    return await build_xlsx([Sheet("Доступные товары", [
        Column("Артикул"), Column("Название"), Column("Бренд"), Column("Категория"),
        Column("Цена", MONEY), Column("Остаток", "0", highlight_lt=5),
        Column("Стоимость остатка", MONEY, total=True), Column("Активен"),
    ], rows)])


async def users_report(db: AsyncSession) -> bytes:
    """Создание таблицы с информацией о пользователях и их суммах покупок."""
    agg = (select(Order.user_id.label("uid"),
                  func.count().label("cnt"), func.sum(Order.total_amount).label("total"))
           .where(Order.status.in_([OrderStatus.PAID, OrderStatus.COMPLETED]))
           .group_by(Order.user_id).subquery())
    result = await db.execute(
        select(User.id, User.email, User.name, User.created_at, User.balance,
               func.coalesce(agg.c.cnt, 0), func.coalesce(agg.c.total, 0))
        .outerjoin(agg, agg.c.uid == User.id).order_by(User.id)
    )
    rows = [(i, email, name, to_local(created), balance, cnt, total)
            for i, email, name, created, balance, cnt, total in result.all()]
    return await build_xlsx([Sheet("Пользователи", [
        Column("ID"), Column("Email"), Column("Имя"), Column("Регистрация", DATETIME),
        Column("Баланс", MONEY, total=True), Column("Оплаченных заказов", "0", total=True),
        Column("Сумма покупок", MONEY, total=True),
    ], rows)])


async def user_report(db: AsyncSession, user_id: int) -> tuple[bytes, str] | None:
    """Создание таблицы с данным конкретного пользователя о его заказах и транзакциях"""
    user = await db.get(User, user_id)
    if user is None:
        return None
    orders = (await db.execute(
        select(Order.id, Order.created_at, Order.status, Order.total_amount,
               Order.shipping_address, Order.contact_phone)
        .where(Order.user_id == user_id).order_by(Order.id.desc()))).all()
    txs = (await db.execute(
        select(BalanceTransaction.created_at, BalanceTransaction.type,
               BalanceTransaction.amount, BalanceTransaction.order_id)
        .where(BalanceTransaction.user_id == user_id)
        .order_by(BalanceTransaction.created_at.desc()))).all()

    order_rows = [(i, to_local(c), STATUS_RU.get(s, str(s)), t, a, p)
                  for i, c, s, t, a, p in orders]
    tx_rows = [(to_local(c), getattr(t, "value", str(t)), amt, oid) for c, t, amt, oid in txs]

    data = await build_xlsx([
        Sheet("Заказы", [Column("№"), Column("Дата", DATETIME), Column("Статус"),
                         Column("Сумма", MONEY), Column("Адрес"), Column("Телефон")], order_rows,
              heading=f"Заказы пользователя {user.name}"),
        Sheet("Транзакции", [Column("Дата", DATETIME), Column("Тип"),
                         Column("Сумма", MONEY), Column("Заказ №")], tx_rows,
              heading=f"Движение баланса: {user.name}"),

    ])
    return data, f"user_{user_id}.xlsx"