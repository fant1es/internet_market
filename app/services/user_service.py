from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cart, User
from app.schemas.auth import UserUpdate
from app.utils.database import run_in_transaction
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
    user.token_version = User.token_version + 1   # инкремент на стороне БД
    await db.commit()
    await db.refresh(user)   # получаем актуальный token_version для новой cookie