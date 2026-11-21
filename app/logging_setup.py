import logging
import sys
from pathlib import Path

from loguru import logger

LOG_DIR = Path("logs")

CONSOLE_FORMAT = (
    "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
    "<cyan>{extra[request_id]}</cyan> | {message}"
)
FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[channel]} | "
    "{extra[request_id]} | {name}:{function}:{line} | {message}"
)


def setup_logging(level: str = "INFO") -> None:
    # Убираем дефолтный sink
    logger.remove()
    # Значения по умолчанию, чтобы формат не падал, когда поля не заданы
    logger.configure(extra={"channel": "app", "request_id": "-"})

    # Логи консоли (docker compose logs)
    logger.add(sys.stderr, level=level, format=CONSOLE_FORMAT)

    # Общий лог, 14 дней
    logger.add(LOG_DIR / "app" / "app_{time:YYYY-MM-DD}.log",
               level="INFO", format=FILE_FORMAT, encoding="utf-8",
               rotation="00:00", diagnose=False, retention="14 days", compression="zip",
               enqueue=True) # запись идёт через очередь, поэтому логирование не блокирует async-код

    # Ошибки, 30 дней
    logger.add(LOG_DIR / "error" / "error_{time:YYYY-MM-DD}.log",
               level="ERROR", format=FILE_FORMAT, encoding="utf-8",
               backtrace=True, diagnose=False,
               rotation="00:00", retention="30 days", compression="zip",
               enqueue=True)

    # Аудит, 180 дней
    logger.add(LOG_DIR / "audit" / "audit_{time:YYYY-MM-DD}.log",
               level="INFO", format=FILE_FORMAT, encoding="utf-8",
               filter=lambda r: r["extra"].get("channel") == "audit",
               rotation="00:00", diagnose=False, retention="180 days", compression="zip",
               enqueue=True)

    _intercept_standard_logging()


class InterceptHandler(logging.Handler):
    """Перенаправляет стандартный logging от uvicorn и sqlalchemy в loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame, depth = frame.f_back, depth + 1
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def _intercept_standard_logging() -> None:
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers = [InterceptHandler()]
        lg.propagate = False