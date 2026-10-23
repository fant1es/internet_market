from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.auth import LoginSchema, RegisterSchema, UserOut
from app.services import user_service
from app.utils.jwt import create_access_token

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=UserOut)
async def register(data: RegisterSchema, db: Annotated[AsyncSession, Depends(get_db)]):
    return await user_service.register_user(db, data.name, data.email, data.password)


@auth_router.post("/login", response_model=UserOut)
async def login(data: LoginSchema, db: Annotated[AsyncSession, Depends(get_db)], response: Response):
    user = await user_service.authenticate(db, data.email, data.password)
    response.set_cookie(key="access_token", value=create_access_token(user.id), httponly=True)
    return user


@auth_router.get("/me", response_model=UserOut)
async def get_me(user: CurrentUser):
    return user


@auth_router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"detail": "Вы вышли из аккаунта"}
