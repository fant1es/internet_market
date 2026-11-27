from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.i18n import DEFAULT, translate


class AppError(HTTPException):
    """
    HTTPException, которая хранит код ошибки вместо готового текста
    Текст подбирается в app_error_handler по языку запроса, чтобы сервисам не нужно было знать язык.
    """

    def __init__(self, status_code: int, code: str, params: dict | None = None, *,
                 field: str | None = None, extra: dict | None = None):
        super().__init__(status_code=status_code, detail=code)
        self.code = code
        self.params = params or {} # значения для подстановки в текст ({available}, {count} ...)
        self.field = field # если задано, ответ приходит в формате 422
        self.extra = extra or {} # дополнительные данные для фронтенда


def field_error(field: str, code: str, **params) -> AppError:
    """422 в формате pydantic для фронтенда с привязкой ошибки к полю по последнему элементу loc."""
    return AppError(422, code, params, field=field)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    lang = getattr(request.state, "lang", DEFAULT)
    message = translate(f"err.{exc.code}", lang, **exc.params)

    if exc.field:
        detail = [{"loc": ["body", exc.field], "msg": message, "type": "value_error"}]
    elif exc.extra:
        detail = {"code": exc.code, "message": message, **exc.extra}
    else:
        detail = message   # как и раньше: простая строка
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": jsonable_encoder(detail)},
                        headers=exc.headers)
