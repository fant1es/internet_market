from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BalanceTransaction, User
from app.models.balance_transaction import TransactionType
from app.utils.database import run_in_transaction

# Предел колонки DECIMAL(10, 2)
MAX_BALANCE = Decimal("99999999.99")


# noinspection PyTypeChecker
async def lock_user(db: AsyncSession, user_id: int) -> User:
    """Блокирует строку пользователя до конца транзакции
    с пересчетом баланса из БД с помощью populate_existing."""
    return await db.scalar(
        select(User).where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


async def apply_balance_change(
    db: AsyncSession,
    user_id: int,
    amount: Decimal,
    type_: TransactionType,
    order_id: int | None = None,
) -> User:
    """Функция для изменения баланса с записью в журнал транзакций"""
    user = await lock_user(db, user_id)
    new_balance = user.balance + amount

    if new_balance < 0:
        raise HTTPException(402, "Недостаточно средств на балансе")
    # Лимит проверяем только для пополнения, чтобы не падало из-за возврата оплаченного заказа
    if type_ == TransactionType.TOPUP and new_balance > MAX_BALANCE:
        raise HTTPException(409, "Превышен максимально допустимый баланс")

    user.balance = new_balance
    db.add(BalanceTransaction(user_id=user_id, order_id=order_id, amount=amount, type=type_))
    return user


async def _topup(db: AsyncSession, user_id: int, amount: Decimal) -> None:
    await apply_balance_change(db, user_id, amount, TransactionType.TOPUP)


async def topup(db: AsyncSession, user_id: int, amount: Decimal) -> Decimal:
    """Пополнение баланса (заглушка вместо платёжного шлюза). Возвращает новый баланс."""
    await run_in_transaction(db, _topup, user_id, amount)
    user = await db.get(User, user_id)
    await db.refresh(user)
    return user.balance
