from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Cart, User
from app.utils.database import run_in_transaction
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