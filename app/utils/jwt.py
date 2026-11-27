from datetime import datetime, timedelta, timezone

from jose import jwt, ExpiredSignatureError, JWTError
from loguru import logger

from app.config import settings
from app.utils.errors import AppError


def create_access_token(user_id: int, user_token_version: int) -> str:
    payload = {
        "sub": str(user_id),
        "tv": user_token_version, # Здесь можно и число: строка обязательна для sub по стандартам
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except ExpiredSignatureError:
        logger.debug("Токен отклонён | причина=истёк срок действия")
        raise AppError(401, "token_expired")
    except JWTError as e:
        # Неверная подпись или повреждённый токен сам не получается, поэтому WARNING
        # Токен в лог не пишем
        logger.warning("Токен отклонён | причина=невалидный токен ({})", e)
        raise AppError(401, "invalid_token")
    return payload
