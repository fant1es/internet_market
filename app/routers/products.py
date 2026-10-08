import math

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Category, Product
from app.schemas.product import ProductListOut, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


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
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = _public_products()

    if category:
        stmt = stmt.where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(Product.name.ilike(f"%{search.strip()}%"))

    # Сколько всего товаров под фильтром
    # Подзапрос
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        # Обязательно упорядочить для страниц
        stmt.order_by(Product.id)
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


