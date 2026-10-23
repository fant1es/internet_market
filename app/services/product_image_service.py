from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.models import Product
from app.services.image_storage import (
    MAX_IMAGE_BYTES,
    InvalidImageError,
    delete_product_image,
    save_product_image,
)


async def _store_file(data: bytes) -> str:
    """Проверяет размер, обрабатывает и сохраняет файл. Возвращает путь для БД."""
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(413, f"Файл слишком большой (максимум {MAX_IMAGE_BYTES // 1024 // 1024} МБ)")
    try:
        # Pillow блокирует поток, поэтому уводим обработку в пул потоков
        return await run_in_threadpool(save_product_image, data)
    except InvalidImageError as e:
        raise HTTPException(415, str(e))


async def _commit_path(db: AsyncSession, product: Product, path: str | None) -> None:
    """Записывает новый путь в БД. При ошибке откатывает транзакцию."""
    product.image_path = path
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise


async def set_image(db: AsyncSession, product: Product, data: bytes) -> Product:
    new_path = await _store_file(data)
    old_path = product.image_path
    try:
        await _commit_path(db, product, new_path)
    except Exception:
        delete_product_image(new_path)  # БД не приняла путь: не оставляем файл-сироту
        raise
    delete_product_image(old_path)  # старый файл удаляем только после успешного коммита
    return product


async def clear_image(db: AsyncSession, product: Product) -> Product:
    old_path = product.image_path
    await _commit_path(db, product, None)
    delete_product_image(old_path)
    return product