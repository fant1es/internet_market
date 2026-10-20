from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import BalanceTransaction, User
from app.models.balance_transaction import TransactionType
from app.schemas.balance import BalanceOut, TopUpIn

router = APIRouter(prefix="/balance", tags=["balance"])

# Предел колонки DECIMAL(10, 2)
MAX_BALANCE = Decimal("99999999.99")


@router.post("/topup", response_model=BalanceOut, summary="Пополнить баланс (заглушка вместо платёжного шлюза)")
async def topup(data: TopUpIn, db: AsyncSession = Depends(get_db), current=Depends(get_current_user)):
    # Блокируем строку пользователя: два параллельных пополнения не перезатрут друг друга.
    # populate_existing заставляет перечитать balance, даже если объект уже есть в сессии.
    user = await db.scalar(
        select(User).where(User.id == current.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if user.balance + data.amount > MAX_BALANCE:
        raise HTTPException(409, "Превышен максимально допустимый баланс")

    user.balance += data.amount
    db.add(BalanceTransaction(user_id=user.id, amount=data.amount, type=TransactionType.TOPUP))
    await db.commit()  # баланс и запись в журнале фиксируются вместе
    await db.refresh(user)

    return {"balance": user.balance}