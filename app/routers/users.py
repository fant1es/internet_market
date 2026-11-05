import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.background import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentUser
from app.schemas.auth import UserOut, UserUpdate, ChangePasswordSchema, ChangeEmailSchema
from app.services import user_service, email_templates, email_service
from app.utils.auth_cookie import set_auth_cookie

logger = logging.getLogger(__name__)

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


@router.post("/me/email", response_model=UserOut)
async def request_email_change(data: ChangeEmailSchema, user: CurrentUser,
                               db: Annotated[AsyncSession, Depends(get_db)], response: Response,
                               background_tasks: BackgroundTasks):
    link = await user_service.request_email_change(db, user,
                                                   data.current_password, data.new_email)

    confirm = email_templates.build_confirm_new_email(user.name, link)
    notice = email_templates.build_old_email_notice(user.name, data.new_email)

    background_tasks.add_task(email_service.send_email, data.new_email, confirm.subject,
                              confirm.text, confirm.html)
    background_tasks.add_task(email_service.send_email, user.email, notice.subject,
                              notice.text, notice.html)

    logger.info("Запрошена смена почты: user_id=%s", user.id)
    return {"detail": "Письмо cо ссылкой отправлено на новый адрес"}