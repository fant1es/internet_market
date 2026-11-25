import time
import uuid

from fastapi import Request
from loguru import logger

from app.i18n import detect_lang


async def request_id_middleware(request: Request, call_next):
    # Убираем access строки по static и health
    if request.url.path.startswith(("/static", "/health")):
        return await call_next(request)

    # Берём id от клиента/прокси, если есть, иначе генерируем свой
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    request_id = request_id[:64]  # защита от слишком длинных значений

    with logger.contextualize(request_id=request_id):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Необработанная ошибка: логируем здесь, пока request_id ещё в контексте
            logger.exception(f"{request.method} {request.url.path} -> unhandled error")
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} "
            f"({duration_ms:.0f} ms)"
        )

    response.headers["X-Request-ID"] = request_id
    return response


async def lang_middleware(request: Request, call_next):
    request.state.lang = detect_lang(request)
    return await call_next(request)