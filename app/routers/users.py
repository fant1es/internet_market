from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.auth import UserOut, UserUpdate, ChangePasswordSchema
from app.services import user_service
from app.utils.auth_cookie import set_auth_cookie

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await user_service.update_user(db, user, data)

@router.patch("/me/password")
async def change_password(data: ChangePasswordSchema, user: CurrentUser,
                          db: Annotated[AsyncSession, Depends(get_db)], response: Response):
    await user_service.change_password(db, user, data.current_password, data.new_password)
    set_auth_cookie(response, user)   # текущее устройство получает токен с новым tv
    return {"detail": "Пароль изменён"}