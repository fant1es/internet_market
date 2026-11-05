from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Cart, User
from app.schemas.auth import UserUpdate
from app.utils.database import run_in_transaction
from app.utils.email_token import create_change_email_token, read_change_email_token
from app.utils.errors import field_error
from app.utils.security import hash_password, verify_password


async def _register(db: AsyncSession, name: str, email: str, password: str) -> User:
    # noinspection PyTypeChecker
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=400, detail="Такая почта уже зарегистрирована")

    user = User(name=name, email=email, password_hash=hash_password(password))
    db.add(user)
    await db.flush()
    db.add(Cart(user_id=user.id))
    return user


async def register_user(db: AsyncSession, name: str, email: str, password: str) -> User:
    try:
        user = await run_in_transaction(db, _register, name, email, password)
    except IntegrityError:
        # Гонка: два запроса с одной почтой прошли проверку одновременно
        raise HTTPException(status_code=400, detail="Такая почта уже зарегистрирована")
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, email: str, password: str) -> User:
    # noinspection PyTypeChecker
    user: User | None = await db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный пароль или почта")
    return user


async def _update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    # exclude_unset=True дает менять только то, что прислал пользователь
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    return user


async def update_user(db: AsyncSession, user: User, data: UserUpdate) -> User:
    updated_user = await run_in_transaction(db, _update_user, user, data)
    await db.refresh(updated_user)
    return updated_user


async def change_password(db: AsyncSession, user: User, current_password: str, new_password: str) -> None:
    if not verify_password(current_password, user.password_hash):
        raise field_error("current_password", "Неверный текущий пароль")
    if current_password == new_password:
        raise field_error("new_password", "Новый пароль должен отличаться от текущего")

    user.password_hash = hash_password(new_password)
    user.token_version = User.token_version + 1  # инкремент на стороне БД
    await db.commit()
    await db.refresh(user)  # получаем актуальный token_version для новой cookie


async def request_email_change(db: AsyncSession, user: User, current_password: str, new_email: str) -> str:
    """Проверяет корректность данных, создает токен для смены почты и предоставляет ссылку для подтверждения почты."""
    if not verify_password(current_password, user.password_hash):
        raise field_error("current_password", "Введен неверный пароль")
    if new_email == user.email:
        raise field_error("new_email", "Новая почта должна отличаться от текущей")
    # noinspection PyTypeChecker
    if await db.scalar(select(User.id).where(User.email == new_email)):
        raise field_error("new_email", "Такая почта уже зарегистрирована")

    token = create_change_email_token(user_id=user.id, new_email=new_email, token_version=user.token_version)

    # Ссылка для подтверждения
    return f"{settings.app_base_url}/confirm-email?token={token}"


async def _confirm_email_change(db: AsyncSession, data: dict) -> User:
    user = await db.get(User, data["uid"])
    # tv не совпадает, если после выдачи ссылки менялся пароль или почта
    if user is None or not user.is_active or data["tv"] != user.token_version:
        raise HTTPException(400, "Ссылка недействительна или уже использована")

    # Проверяем заново: за время жизни ссылки этот адрес мог быть занят
    # noinspection PyTypeChecker
    if await db.scalar(select(User.id).where(User.email == data["email"])):
        raise HTTPException(status_code=400, detail="Эта почта уже занята другим аккаунтом")

    user.email = data["email"]
    # Убивает все сессии + выданные ссылки
    user.token_version = User.token_version + 1
    return user


async def confirm_email_change(db: AsyncSession, token: str) -> User:
    data = read_change_email_token(token)
    try:
        user = await run_in_transaction(db, _confirm_email_change, data)
    except IntegrityError:
        raise HTTPException(400, "Эта почта уже занята")

    await db.refresh(user)
    return user