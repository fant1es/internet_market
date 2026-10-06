from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Category
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])

# Роутер для получения всех категорий для фильтров
@router.get("", response_model=list[CategoryOut], summary="Список активных категорий")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    )
    return result.all()