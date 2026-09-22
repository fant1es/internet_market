from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.jwt import decode_access_token
from app.utils.database import get_user
from app.models import User


async def get_current_user(request: Request, db: AsyncSession) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Не авторизован")

    payload = decode_access_token(token)
    user_id = int(payload.get("sub"))

    user = await get_user(user_id, db)
    if not user:
        raise HTTPException(status_code=401, detail="Пользователь не найден")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]