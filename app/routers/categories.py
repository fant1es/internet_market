from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Attribute, AttributeOption, Category, Product, ProductOption
from app.schemas.category import CategoryOut, FilterAttributeOut

router = APIRouter(prefix="/categories", tags=["categories"])

# Роутер для получения всех категорий для фильтров
@router.get("", response_model=list[CategoryOut], summary="Список активных категорий")
async def list_categories(db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    )
    return result.all()


# noinspection PyTypeChecker
@router.get("/{slug}/filters", response_model=list[FilterAttributeOut],
            summary="Фильтры категории: характеристики и их варианты")
async def category_filters(slug: str, db: AsyncSession = Depends(get_db)):
    category = await db.scalar(
        select(Category).where(Category.slug == slug, Category.is_active.is_(True))
    )
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")

    # Только варианты, которые есть хотя бы у одного видимого товара категории,
    # чтобы в панели не было вариантов, при выборе которых ничего не находится
    used_options = (
        select(ProductOption.option_id)
        .join(Product, Product.id == ProductOption.product_id)
        .where(Product.category_id == category.id, Product.is_active.is_(True))
    )

    rows = await db.execute(
        select(Attribute, AttributeOption)
        .join(AttributeOption, AttributeOption.attribute_id == Attribute.id)
        .where(Attribute.category_id == category.id, AttributeOption.id.in_(used_options))
        .order_by(Attribute.position, Attribute.id, AttributeOption.position, AttributeOption.id)
    )

    # Строки приходят уже упорядоченными, группируем их по атрибутам
    attributes: dict[int, dict] = {}
    for attribute, option in rows:
        item = attributes.setdefault(
            attribute.id,
            {"id": attribute.id, "name": attribute.name, "slug": attribute.slug, "options": []},
        )
        item["options"].append({"id": option.id, "value": option.value})

    return list(attributes.values())