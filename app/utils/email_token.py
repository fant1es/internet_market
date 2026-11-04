from urllib.error import URLError

import itsdangerous
from fastapi import HTTPException
from itsdangerous import URLSafeTimedSerializer

from app.config import settings

_CHANGE_MAIL_SALT = "change-email"


def _serializer(salt: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt=salt)


def create_change_email_token(user_id: int, new_email: str, token_version: int) -> str:
    return _serializer(_CHANGE_MAIL_SALT).dumps(
        {"uid": user_id, "email": new_email, "tv": token_version}
    )


def read_change_email_token(token: str, max_age: int | None = None) -> dict:
    ttl = settings.email_token_ttl_minutes * 60 if max_age is None else max_age
    try:
        data = _serializer(_CHANGE_MAIL_SALT).loads(token, max_age=ttl)
    except itsdangerous.exc.SignatureExpired:
        raise HTTPException(400, "Ссылка устарела, повторите запрос на смену почты")
    except itsdangerous.exc.BadTimeSignature:
        raise HTTPException(400, "Недействительная ссылка")

    if not isinstance(data, dict) or not {"uid", "email", "tv"} <= data.keys():
        raise HTTPException(400, "Недействительная ссылка")

    return data