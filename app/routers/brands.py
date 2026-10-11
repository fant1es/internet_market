from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Brand, Category, Product
from app.schemas.brand import BrandOut

router = APIRouter(prefix="/brands", tags=["brands"])


# noinspection PyTypeChecker
@router.get("", response_model=list[BrandOut], summary="Список брендов")
async def list_brands(category: str | None =
                      Query(None, description="slug категории: вернуть только бренды, у которых есть товары в ней"),
                      db: AsyncSession = Depends(get_db)):
    # Если выбрана категория, то бренды только из нее берем
    if category:
        stmt = (
            select(Brand)
            .join(Product, Product.brand_id == Brand.id)
            .join(Category, Product.category_id == Category.id)
            .where(
                Brand.is_active.is_(True),
                Product.is_active.is_(True), # Должен быть активен хотя бы 1 товар
                Category.is_active.is_(True), # Переданная категория должна быть активна
                Category.slug == category,
            )
            .distinct()  # Убираем дубликаты
        )
    # Без категории получаем все активные бренды
    else:
        stmt = select(Brand).where(Brand.is_active.is_(True))

    result = await db.scalars(stmt.order_by(Brand.name))
    return result.all()