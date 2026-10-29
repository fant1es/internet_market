from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.auth import UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserOut)
async def update_me(data: UserUpdate, user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    return await user_service.update_user(db, user, data)
