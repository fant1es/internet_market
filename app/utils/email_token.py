import itsdangerous
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer

from app.config import settings
from app.utils.errors import AppError

_CHANGE_MAIL_SALT = "change-email"


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.secret_key, salt=salt)


def create_change_email_token(user_id: int, new_email: str, token_version: int) -> str:
    return _serializer(_CHANGE_MAIL_SALT).dumps(
        {"uid": user_id, "email": new_email, "tv": token_version}
    )


def read_change_email_token(token: str, max_age: int | None = None) -> dict:
    ttl = settings.email_token_ttl_minutes * 60 if max_age is None else max_age
    try:
        data = _serializer(_CHANGE_MAIL_SALT).loads(token, max_age=ttl)
    except itsdangerous.exc.SignatureExpired:
        raise AppError(400, "link_expired")
    except itsdangerous.exc.BadTimeSignature:
        raise AppError(400, "link_invalid")

    if not isinstance(data, dict) or not {"uid", "email", "tv"} <= data.keys():
        raise AppError(400, "link_invalid")

    return data