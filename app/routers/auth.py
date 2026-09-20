from fastapi import APIRouter, HTTPException
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from app.database import get_db
from app.models import User, Cart
from app.schemas.auth import RegisterSchema, UserOut
from app.utils.database import create_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut)
async def register(data: RegisterSchema,
                   db: Annotated[AsyncSession, Depends(get_db)]):
    # Уникальность почты
    # noinspection PyTypeChecker
    if await db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=400, detail="Такая почта уже зарегистрирована")

    # Возврат данных пользователя
    user = await create_user(data.name, data.email, data.password, db)
    # Сразу корзину для каждого пользователя
    db.add(Cart(user_id=user.id))
    await db.commit()
    await db.refresh(user)

    return {"id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role
            }