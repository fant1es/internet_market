from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import jwt, ExpiredSignatureError, JWTError

from app.config import settings


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истёк, войдите заново")
    except JWTError:
        raise HTTPException(status_code=401, detail="Невалидный токен")
    return payload
