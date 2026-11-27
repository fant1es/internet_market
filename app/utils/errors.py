from decimal import Decimal

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.i18n import DEFAULT, translate


class AppError(HTTPException):
    """
    HTTPException, которая хранит код ошибки вместо готового текста.
    Текст подбирается в app_error_handler по языку запроса, чтобы сервисам не нужно было знать язык.
    """

    def __init__(self, status_code: int, code: str, params: dict | None = None, *,
                 field: str | None = None, extra: dict | None = None):
        super().__init__(status_code=status_code, detail=code)
        self.code = code
        self.params = params or {}
        self.field = field
        self.extra = extra or {}


class ValidationCode(ValueError):
    """Ошибка валидатора схемы с кодом вместо текста.
    Pydantic кладёт исключение в ctx["error"], validation_error_handler берёт из него код и параметры.
    Текст ищется в словаре по ключу err.validation.<код>."""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


def field_error(field: str, code: str, **params) -> AppError:
    """422 в формате pydantic для фронтенда с привязкой ошибки к полю по последнему элементу loc."""
    return AppError(422, code, params, field=field)


def _lang(request: Request) -> str:
    return getattr(request.state, "lang", DEFAULT)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    message = translate(f"err.{exc.code}", _lang(request), **exc.params)

    if exc.field:
        detail = [{"loc": ["body", exc.field], "msg": message, "type": "value_error"}]
    elif exc.extra:
        detail = {"code": exc.code, "message": message, **exc.extra}
    else:
        detail = message   # как и раньше: простая строка
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": jsonable_encoder(detail)},
                        headers=exc.headers)


_SCALARS = (str, int, float, Decimal)


def _validation_message(error: dict, lang: str) -> str:
    """Текст одной ошибки Pydantic на языке запроса."""
    ctx = error.get("ctx") or {}

    # Custom для своих валидаторов типа ValidationCode("код", параметры)
    custom = ctx.get("error")
    if isinstance(custom, ValidationCode):
        return translate(f"err.validation.{custom.code}", lang, **custom.params)

    # Стандартные ошибки Pydantic, тип ошибки превращаем в ключ словаря
    code = error["type"]
    # EmailStr сообщает причину в ctx["reason"]
    if code == "value_error" and "reason" in ctx:
        code = "invalid_email"
    # null в обязательном поле это то же, что и пропущенное поле
    elif code.endswith("_type") and error.get("input") is None:
        code = "missing"
    # Пустая строка там, где min_length=1 означает, что поле не заполнено
    elif code == "string_too_short" and ctx.get("min_length") == 1:
        code = "missing"

    params = {k: v for k, v in ctx.items() if isinstance(v, _SCALARS)}
    key = f"err.validation.{code}"
    try:
        text = translate(key, lang, **params)
    # Если в тексте есть параметр, которого нет в ctx
    except (KeyError, IndexError):
        text = key
    # Если перевода для такого типа нет
    if text == key:
        text = translate("err.validation.invalid", lang)
    return text


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 в прежнем формате, но с переведёнными сообщениями.
    Поле input в ответ не попадает (в нём могут быть пароли)."""
    lang = _lang(request)
    errors = [{"loc": list(e["loc"]), "msg": _validation_message(e, lang), "type": e["type"]}
              for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": jsonable_encoder(errors)})
