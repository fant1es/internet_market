from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.jwt import decode_access_token
from app.utils.database import get_user
from app.models import User


async def _user_from_token(token: str, db: AsyncSession) -> User:
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Невалидный токен")

    user = await get_user(user_id, db)
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Аккаунт заблокирован")
    # Токены, выданные до миграции, не содержат tv: считаем их версией 0
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(status_code=401, detail="Сессия устарела, войдите заново")
    return user


async def get_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")

    return await _user_from_token(token, db)


async def get_current_admin(user: User = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Forbidden")
    return user

# Нужен там, где пользователь заходит как гость (для показания страниц регистрации/входа)
async def get_current_user_optional(request: Request,
                                    db: Annotated[AsyncSession, Depends(get_db)]) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return await _user_from_token(token, db)
    except HTTPException:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]