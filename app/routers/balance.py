from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.balance import BalanceOut, TopUpIn
from app.services import balance_service

router = APIRouter(prefix="/balance", tags=["balance"])


@router.post("/topup", response_model=BalanceOut, summary="Пополнить баланс (заглушка вместо платёжного шлюза)")
async def topup(data: TopUpIn, db: AsyncSession = Depends(get_db), current=Depends(get_current_user)):
    return {"balance": await balance_service.topup(db, current.id, data.amount)}