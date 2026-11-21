from typing import Any, Awaitable, Callable, TypeVar

from fastapi import HTTPException
from loguru import logger
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.security import hash_password

T = TypeVar("T")


def _constraint_name(e: IntegrityError) -> str:
    """Имя нарушенного ограничения БД без значений из запроса."""
    # У asyncpg первичная ошибка лежит в __cause__
    cause = getattr(e.orig, "__cause__", None)
    return getattr(cause, "constraint_name", None) or type(e.orig).__name__


async def get_or_404(db: AsyncSession, model: type[T], item_id: int, message: str) -> T:
    """Достаёт объект по первичному ключу или отдаёт 404 с переданным сообщением."""
    item = await db.get(model, item_id)
    if item is None:
        # Здесь просто обычное поведение пользователя (устаревшая ссылка, чужой id), поэтому DEBUG
        logger.debug("Объект не найден | модель={} id={}", model.__name__, item_id)
        raise HTTPException(status_code=404, detail=message)
    return item


async def commit_or_409(db: AsyncSession, message: str) -> None:
    """Коммит со страховкой: нарушение уникальности/внешнего ключа превращается в 409."""
    try:
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        # Так как проверки в сервисах прошли, значит это гонка или нарушение внешнего ключа
        logger.warning(
            "Конфликт целостности данных | ограничение={} причина={}",
            _constraint_name(e), message,
        )
        raise HTTPException(status_code=409, detail=message)


async def run_in_transaction(db: AsyncSession, action: Callable[..., Awaitable[Any]],
                             *args: Any, **kwargs: Any) -> Any:
    """Выполняет функцию action и фиксирует результат одним коммитом.
    При любой ошибке откатывает транзакцию и пробрасывает исключение дальше."""
    name = getattr(action, "__name__", repr(action))
    try:
        result = await action(db, *args, **kwargs)
        await db.commit()
    except HTTPException as e:
        await db.rollback()
        # HTTPException в DEBUG, т.к. связан с бизнес-логикой
        logger.debug("Откат транзакции | действие={} статус={}", name, e.status_code)
        raise
    except Exception as e:
        # Остальное уходит в WARNING по коду 500
        await db.rollback()
        logger.warning("Откат транзакции | действие={} ошибка={}", name, type(e).__name__)
        raise
    logger.debug("Транзакция зафиксирована | действие={}", name)
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