from fastapi import Response
from app.models import User
from app.utils.jwt import create_access_token

from app.config import settings


def set_auth_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key='access_token',
        value=create_access_token(user.id, user.token_version),
        httponly=True,
        secure=settings.cookie_secure,
        samesite='lax',
        max_age=settings.access_token_expire_minutes * 60
    )