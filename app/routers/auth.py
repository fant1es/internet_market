import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.auth import LoginSchema, RegisterSchema, UserOut, ConfirmEmailSchema
from app.services import user_service
from app.utils.auth_cookie import set_auth_cookie

logger = logging.getLogger(__name__)

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserOut)
async def register(data: RegisterSchema, db: Annotated[AsyncSession, Depends(get_db)]):
    return await user_service.register_user(db, data.name, data.email, data.password)


@auth_router.post("/login", response_model=UserOut)
async def login(data: LoginSchema, db: Annotated[AsyncSession, Depends(get_db)], response: Response):
    user = await user_service.authenticate(db, data.email, data.password)
    set_auth_cookie(response, user)
    return user


@auth_router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser):
    return user


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"detail": "Вы вышли из аккаунта"}


@auth_router.post("/confirm-email", response_model=UserOut)
async def confirm_email_change(data: ConfirmEmailSchema, db: Annotated[AsyncSession, Depends(get_db)],
                               response: Response):
    user = await user_service.confirm_email_change(db, data.token)

    # Удаляем куки, т.к. после подтверждения сессия будет убита
    response.delete_cookie(key="access_token")
    logger.info("Почта изменена: user_id=%s", user.id)
    return {"detail": "Почта изменена. Войдите с новым адресом"}