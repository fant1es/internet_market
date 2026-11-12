import math
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Category, Product
from app.schemas.product import ProductListOut, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


class ProductSort(str, Enum):
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"


# Для каждой сортировки вторым параметром учитываем id, чтобы избежать дублей и ошибок
ORDER_BY = {
    ProductSort.newest: (Product.created_at.desc(), Product.id.desc()),
    ProductSort.price_asc: (Product.price.asc(), Product.id.asc()),
    ProductSort.price_desc: (Product.price.desc(), Product.id.desc()),
}


def _public_products():
    """Базовый запрос, который может обрастать дополнительными условиями"""
    return (
        # Всегда должно быть совпадение по категории и активность товара
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True), Category.is_active.is_(True))
    )


@router.get("", response_model=ProductListOut, summary="Список товаров")
async def list_products(
    category: str | None = Query(None, description="slug категории, например 'laptops'"),
    search: str | None = Query(None, max_length=100, description="поиск по названию"),
    min_price: Decimal | None = Query(None, ge=0, description="цена от (включительно)"),
    max_price: Decimal | None = Query(None, ge=0, description="цена до (включительно)"),
    sort: ProductSort = Query(ProductSort.newest, description="порядок сортировки"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=422,
            detail="Минимальная цена не может быть больше максимальной",
        )

    stmt = _public_products()

    if category:
        stmt = stmt.where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(Product.name.ilike(f"%{search.strip()}%"))
    # Фильтруем по price, чтобы учитывалась скидка
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    # Сколько всего товаров под фильтром (считаем до order_by/offset/limit)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        # Обязательно упорядочить для страниц
        stmt.order_by(*ORDER_BY[sort])
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    return {
        "items": result.all(),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


@router.get("/{product_id}", response_model=ProductOut, summary="Карточка товара")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.scalar(_public_products().where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product