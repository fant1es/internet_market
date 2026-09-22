from fastapi import APIRouter, HTTPException
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

from starlette.responses import Response

from app.database import get_db
from app.models import User, Cart
from app.schemas.auth import RegisterSchema, UserOut, LoginSchema
from app.utils.database import create_user
from app.utils.jwt import create_access_token
from app.utils.security import verify_password

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


@router.post("/login", response_model=UserOut)
async def login(data: LoginSchema,
                db: Annotated[AsyncSession, Depends(get_db)], response: Response):
    # noinspection PyTypeChecker
    user: User = await db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный пароль или почта")

    response.set_cookie(key="access_token", value=create_access_token(user.id), httponly=True)

    return user