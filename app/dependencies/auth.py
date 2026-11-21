from typing import Annotated

from fastapi import Depends, HTTPException, Request
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.utils.jwt import decode_access_token
from app.utils.database import get_user
from app.models import User
from app.models.user import UserRole


async def _user_from_token(token: str, db: AsyncSession, strict: bool = True) -> User:
    # strict=True для защищённых роутов: отказ пишем как WARNING.
    # strict=False для гостевых страниц (get_current_user_optional): там отказ штатный, поэтому только DEBUG
    reject_level = "WARNING" if strict else "DEBUG"

    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        logger.log(reject_level, "Отказ в доступе | причина=некорректное содержимое токена")
        raise HTTPException(status_code=401, detail="Невалидный токен")

    user = await get_user(user_id, db)
    if not user:
        logger.log(reject_level, "Отказ в доступе | причина=пользователь из токена не найден user_id={}", user_id)
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    if not user.is_active:
        logger.log(reject_level, "Отказ в доступе | причина=аккаунт заблокирован user_id={}", user_id)
        raise HTTPException(status_code=401, detail="Аккаунт заблокирован")
    # Токены, выданные до миграции, не содержат tv: считаем их версией 0
    if payload.get("tv", 0) != user.token_version:
        # Изменение пароля или почты, поэтому в DEBUG
        logger.debug("Отказ в доступе | причина=сессия устарела (tv) user_id={}", user_id)
        raise HTTPException(status_code=401, detail="Сессия устарела, войдите заново")
    return user


async def get_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]) -> User:
    token = request.cookies.get("access_token")
    if not token:
        logger.debug("Нет токена авторизации | {} {}", request.method, request.url.path)
        raise HTTPException(status_code=401, detail="Не авторизован")

    return await _user_from_token(token, db)


async def get_current_admin(request: Request, user: User = Depends(get_current_user)):
    if user.role != UserRole.ADMIN:
        logger.warning("Отказ в доступе к админке | user_id={} {} {}",
                       user.id, request.method, request.url.path)
        raise HTTPException(403, "Forbidden")
    return user

# Нужен там, где пользователь заходит как гость (для показания страниц регистрации/входа)
async def get_current_user_optional(request: Request,
                                    db: Annotated[AsyncSession, Depends(get_db)]) -> User | None:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        return await _user_from_token(token, db, strict=False)
    except HTTPException:
        return None


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]
CurrentUserOptional = Annotated[User | None, Depends(get_current_user_optional)]