import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models import Brand, Category, Product
from app.schemas.admin_product import ActiveUpdate, ProductAdminListOut, ProductAdminOut, ProductIn
from app.services.image_service import MAX_IMAGE_BYTES, InvalidImageError, delete_product_image, save_product_image


router = APIRouter(
    prefix="/admin/products",
    tags=["admin: products"],
    dependencies=[Depends(get_current_admin)], # Роутер доступен только администраторам
)


async def _get_or_404(db: AsyncSession, product_id: int) -> Product:
    # Админ получает любые товары, в том числе и скрытые
    product = await db.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


# noinspection PyTypeChecker
async def _validate_refs(db: AsyncSession, data: ProductIn, product_id: int | None = None) -> None:
    """Проверяет, что категория и бренд существуют, а артикул не занят другим товаром."""
    if await db.scalar(select(Category.id).where(Category.id == data.category_id)) is None:
        raise HTTPException(status_code=422, detail="Категория не найдена")

    if data.brand_id is not None:
        if await db.scalar(select(Brand.id).where(Brand.id == data.brand_id)) is None:
            raise HTTPException(status_code=422, detail="Бренд не найден")

    sku_stmt = select(Product.id).where(Product.sku == data.sku)
    if product_id is not None:
        sku_stmt = sku_stmt.where(Product.id != product_id)  # Свой же артикул при редактировании доступен
    if await db.scalar(sku_stmt) is not None:
        raise HTTPException(status_code=409, detail="Товар с таким артикулом уже существует")


async def _commit(db: AsyncSession) -> None:
    # Страховка на случай гонки: два запроса с одним артикулом прошли проверку одновременно
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Товар с таким артикулом уже существует")


# noinspection PyTypeChecker
@router.get("", response_model=ProductAdminListOut, summary="Список товаров (включая скрытые)")
async def list_products(
    search: str | None = Query(None, max_length=100, description="поиск по названию или артикулу"),
    category: str | None = Query(None, description="slug категории"),
    is_active: bool | None = Query(None, description="true: только видимые, false: только скрытые"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product)

    if category:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(or_(Product.name.ilike(f"%{search.strip()}%"),
                              Product.sku.ilike(f"%{search.strip()}%")))
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        stmt.order_by(Product.id).offset((page - 1) * page_size).limit(page_size)
    )

    return {
        "items": result.all(),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


@router.get("/{product_id}", response_model=ProductAdminOut, summary="Товар для редактирования")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_or_404(db, product_id)


@router.post("", response_model=ProductAdminOut, status_code=201, summary="Создать товар")
async def create_product(data: ProductIn, db: AsyncSession = Depends(get_db)):
    await _validate_refs(db, data)

    product = Product(**data.model_dump())
    db.add(product)
    await _commit(db)
    await db.refresh(product)  # подтягиваем значения, которые проставила БД (created_at)
    return product


@router.put("/{product_id}", response_model=ProductAdminOut, summary="Обновить товар целиком")
async def update_product(product_id: int, data: ProductIn, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)
    await _validate_refs(db, data, product_id=product_id)

    for field, value in data.model_dump().items():
        setattr(product, field, value)

    await _commit(db)
    return product


@router.patch("/{product_id}/active", response_model=ProductAdminOut, summary="Скрыть или показать товар")
async def set_product_active(product_id: int, data: ActiveUpdate, db: AsyncSession = Depends(get_db)):
    # Изменение is_active работает как мягкое удаление
    product = await _get_or_404(db, product_id)
    product.is_active = data.is_active
    await _commit(db)
    return product


@router.post("/{product_id}/image", response_model=ProductAdminOut, summary="Загрузить изображение товара")
async def upload_product_image(product_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)

    # Читаем на 1 байт больше лимита: так видно превышение, не загружая в память файл любого размера
    data = await file.read(MAX_IMAGE_BYTES + 1)
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"Файл слишком большой (максимум {MAX_IMAGE_BYTES // 1024 // 1024} МБ)")

    try:
        # Pillow блокирует поток, поэтому уводим обработку в пул потоков, чтобы не тормозить остальные запросы
        new_path = await run_in_threadpool(save_product_image, data)
    except InvalidImageError as e:
        raise HTTPException(status_code=415, detail=str(e))

    old_path = product.image_path
    product.image_path = new_path
    try:
        await _commit(db)
    except Exception:
        delete_product_image(new_path)  # БД не приняла изменение: не оставляем файл-сироту
        raise

    delete_product_image(old_path)  # старую картинку удаляем только после успешного коммита
    return product


@router.delete("/{product_id}/image", response_model=ProductAdminOut, summary="Удалить изображение товара")
async def delete_image(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await _get_or_404(db, product_id)

    old_path = product.image_path
    product.image_path = None
    await _commit(db)

    delete_product_image(old_path)
    return product