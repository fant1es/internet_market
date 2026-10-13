import io
import uuid
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# Папка app/static считается от файла сервиса
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
PRODUCTS_DIR = STATIC_DIR / "img" / "products"

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_SIDE = 1200 # Длинная сторона после обработки в px


class InvalidImageError(Exception):
    """Файл не является допустимым изображением."""


def save_product_image(data: bytes) -> str:
    """Проверяет изображение, приводит к единому виду и сохраняет на диск.
    Возвращает путь относительно /static, который будет в Product.image_path."""
    try:
        img = Image.open(io.BytesIO(data))
        # Формат на основе содержимого
        fmt = img.format
        # Само декодирование файла
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise InvalidImageError("Файл не является корректным изображением") from e

    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError("Допустимы только JPEG, PNG и WebP")

    # Учитываем поворот из EXIF (фото с телефона)
    img = ImageOps.exif_transpose(img)
    # Уменьшаем, если больше лимита с сохранением пропорций
    img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    PRODUCTS_DIR.mkdir(parents=True, exist_ok=True)
    # Генерируем имя для файла
    filename = f"{uuid.uuid4().hex}.webp"
    # Перекодирование + убираем EXIF и другие метаданные
    img.save(PRODUCTS_DIR / filename, "WEBP", quality=85)

    return f"img/products/{filename}"


def delete_product_image(rel_path: str | None) -> None:
    """Удаляет файл картинки, если он лежит внутри папки картинок товаров."""
    if not rel_path:
        return
    path = (STATIC_DIR / rel_path).resolve()
    # Проверка на то, что путь остается внутри нашей папки
    if PRODUCTS_DIR.resolve() in path.parents:
        path.unlink(missing_ok=True)