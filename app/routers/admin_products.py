from decimal import Decimal
from enum import Enum
import math

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models import Brand, Category, Product
from app.schemas.admin_product import ActiveUpdate, ProductAdminListOut, ProductAdminOut, ProductIn
from app.services import product_image_service
from app.services.image_storage import MAX_IMAGE_BYTES
from app.utils.database import get_or_404, commit_or_409

LOW_STOCK = 5  # порог "мало на складе" (для фронтенда синхронизировать с admin.js)


class AdminSort(str, Enum):
    id_asc = "id_asc"
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"
    stock_asc = "stock_asc"
    stock_desc = "stock_desc"
    name = "name"


class StockFilter(str, Enum):
    in_stock = "in_stock"
    low = "low"
    out = "out"


# Первым ключом основное сравнение, вторым - всегда id, чтобы порядок между страницами был стабильным.
ORDER_BY = {
    AdminSort.id_asc: (Product.id.asc(),),
    AdminSort.newest: (Product.created_at.desc(), Product.id.desc()),
    AdminSort.price_asc: (Product.price.asc(), Product.id.asc()),
    AdminSort.price_desc: (Product.price.desc(), Product.id.desc()),
    AdminSort.stock_asc: (Product.stock_quantity.asc(), Product.id.asc()),
    AdminSort.stock_desc: (Product.stock_quantity.desc(), Product.id.desc()),
    AdminSort.name: (Product.name.asc(), Product.id.asc()),
}


router = APIRouter(
    prefix="/admin/products",
    tags=["admin: products"],
    dependencies=[Depends(get_current_admin)], # Роутер доступен только администраторам
)


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


# noinspection PyTypeChecker
@router.get("", response_model=ProductAdminListOut, summary="Список товаров (включая скрытые)")
async def list_products(
        search: str | None = Query(None, max_length=100, description="поиск по названию или артикулу"),
        category: str | None = Query(None, description="slug категории"),
        is_active: bool | None = Query(None, description="true: только видимые, false: только скрытые"),
        brand_id: int | None = Query(None, description="id бренда"),
        without_brand: bool = Query(False, description="только товары без бренда (brand_id игнорируется)"),
        min_price: Decimal | None = Query(None, ge=0, description="цена от (включительно)"),
        max_price: Decimal | None = Query(None, ge=0, description="цена до (включительно)"),
        has_discount: bool = Query(False, description="только товары со скидкой"),
        stock: StockFilter | None = Query(None, description="in_stock, low (1..LOW_STOCK) или out"),
        sort: AdminSort = Query(AdminSort.id_asc, description="порядок сортировки"),
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(status_code=422, detail="Минимальная цена не может быть больше максимальной")

    stmt = select(Product)

    if category:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(or_(Product.name.ilike(f"%{search.strip()}%"),
                              Product.sku.ilike(f"%{search.strip()}%")))
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))

    # Бренд фильтруем по brand_id напрямую, JOIN не нужен
    if without_brand:
        stmt = stmt.where(Product.brand_id.is_(None))
    elif brand_id is not None:
        stmt = stmt.where(Product.brand_id == brand_id)

    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if has_discount:
        stmt = stmt.where(Product.old_price.is_not(None), Product.old_price > Product.price)

    if stock == StockFilter.in_stock:
        stmt = stmt.where(Product.stock_quantity > 0)
    elif stock == StockFilter.low:
        stmt = stmt.where(Product.stock_quantity > 0, Product.stock_quantity <= LOW_STOCK)
    elif stock == StockFilter.out:
        stmt = stmt.where(Product.stock_quantity == 0)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        stmt.order_by(*ORDER_BY[sort]).offset((page - 1) * page_size).limit(page_size)
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
    return await get_or_404(db, Product, product_id, message="Товар не найден")


@router.post("", response_model=ProductAdminOut, status_code=201, summary="Создать товар")
async def create_product(data: ProductIn, db: AsyncSession = Depends(get_db)):
    await _validate_refs(db, data)

    product = Product(**data.model_dump())
    db.add(product)
    await commit_or_409(db, message="Товар с таким артикулом уже существует")  # страховка от гонки по артикулу
    await db.refresh(product)  # подтягиваем значения, которые проставила БД (created_at)
    return product


@router.put("/{product_id}", response_model=ProductAdminOut, summary="Обновить товар целиком")
async def update_product(product_id: int, data: ProductIn, db: AsyncSession = Depends(get_db)):
    product = await get_or_404(db, Product, product_id, message="Товар не найден")
    await _validate_refs(db, data, product_id=product_id)

    for field, value in data.model_dump().items():
        setattr(product, field, value)

    await commit_or_409(db, message="Товар с таким артикулом уже существует")
    return product


@router.patch("/{product_id}/active", response_model=ProductAdminOut, summary="Скрыть или показать товар")
async def set_product_active(product_id: int, data: ActiveUpdate, db: AsyncSession = Depends(get_db)):
    # Изменение is_active работает как мягкое удаление
    product = await get_or_404(db, Product, product_id, message="Товар не найден")
    product.is_active = data.is_active
    await commit_or_409(db, message="Товар с таким артикулом уже существует")
    return product


@router.post("/{product_id}/image", response_model=ProductAdminOut, summary="Загрузить изображение товара")
async def upload_product_image(product_id: int, file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    product = await get_or_404(db, Product, product_id, message="Товар не найден")
    # Читаем на 1 байт больше лимита: так видно превышение, не загружая в память файл любого размера
    data = await file.read(MAX_IMAGE_BYTES + 1)
    return await product_image_service.set_image(db, product, data)


@router.delete("/{product_id}/image", response_model=ProductAdminOut, summary="Удалить изображение товара")
async def delete_image(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await get_or_404(db, Product, product_id, message="Товар не найден")
    return await product_image_service.clear_image(db, product)