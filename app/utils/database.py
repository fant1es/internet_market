from app.models import User
from app.utils.security import hash_password

from typing import Any, Awaitable, Callable, TypeVar

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_or_404(db: AsyncSession, model: type[T], item_id: int, message: str) -> T:
    """Достаёт объект по первичному ключу или отдаёт 404 с переданным сообщением."""
    item = await db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=message)
    return item


async def commit_or_409(db: AsyncSession, message: str) -> None:
    """Коммит со страховкой: нарушение уникальности/внешнего ключа превращается в 409."""
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail=message)


async def run_in_transaction(db: AsyncSession, action: Callable[..., Awaitable[Any]],
                             *args: Any, **kwargs: Any) -> Any:
    """Выполняет функцию action и фиксирует результат одним коммитом.
    При любой ошибке откатывает транзакцию и пробрасывает исключение дальше."""
    try:
        result = await action(db, *args, **kwargs)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return result


async def create_user(name: str, email: str, password: str, db: AsyncSession):
    password_hash = hash_password(password)
    user = User(name=name, email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user

async def get_user(user_id: int, db: AsyncSession):
    user = await db.get(User, user_id)
    return user