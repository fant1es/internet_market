from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException

from app.models import Attribute, AttributeOption, Category, ProductOption
from app.utils.database import commit_or_409, get_or_404

CONFLICT_MSG = "Конфликт данных: такая запись уже существует"


def _attribute_out(attribute: Attribute, products_count: int = 0) -> dict:
    return {
        "id": attribute.id,
        "name": attribute.name,
        "slug": attribute.slug,
        "products_count": products_count,
    }


def _option_out(option: AttributeOption, products_count: int = 0) -> dict:
    return {"id": option.id, "value": option.value, "products_count": products_count}


async def _usage(db: AsyncSession, column, item_id: int) -> int:
    """Сколько товаров используют характеристику (attribute_id) или вариант (option_id)."""
    return await db.scalar(
        select(func.count()).select_from(ProductOption).where(column == item_id)
    ) or 0


async def _ensure_slug_free(db: AsyncSession, category_id: int, slug: str, exclude_id: int | None = None) -> None:
    stmt = select(Attribute.id).where(Attribute.category_id == category_id, Attribute.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(Attribute.id != exclude_id)
    if await db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Характеристика с таким названием уже есть в категории")


async def _ensure_value_free(db: AsyncSession, attribute_id: int, value: str, exclude_id: int | None = None) -> None:
    # Сравниваем без учёта регистра. lower() с обеих сторон считает сама БД, поэтому кириллица не страдает
    stmt = select(AttributeOption.id).where(
        AttributeOption.attribute_id == attribute_id,
        func.lower(AttributeOption.value) == func.lower(value),
    )
    if exclude_id is not None:
        stmt = stmt.where(AttributeOption.id != exclude_id)
    if await db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Такой вариант уже есть у этой характеристики")


# --- Чтение -----------------------------------------------------------------

# noinspection PyTypeChecker
async def list_attributes(db: AsyncSession, category_id: int) -> list[dict]:
    """Все характеристики категории с вариантами, включая пустые и неиспользуемые."""
    await get_or_404(db, Category, category_id, message="Категория не найдена")

    attributes = (await db.scalars(
        select(Attribute).where(Attribute.category_id == category_id)
        .order_by(Attribute.position, Attribute.id)
    )).all()
    if not attributes:
        return []
    attr_ids = [a.id for a in attributes]

    options = (await db.scalars(
        select(AttributeOption).where(AttributeOption.attribute_id.in_(attr_ids))
        .order_by(AttributeOption.position, AttributeOption.id)
    )).all()

    # Две группировки вместо запроса на каждую строку
    attr_usage = dict((await db.execute(
        select(ProductOption.attribute_id, func.count())
        .where(ProductOption.attribute_id.in_(attr_ids))
        .group_by(ProductOption.attribute_id)
    )).all())
    option_usage = dict((await db.execute(
        select(ProductOption.option_id, func.count())
        .where(ProductOption.attribute_id.in_(attr_ids))
        .group_by(ProductOption.option_id)
    )).all())

    result = {a.id: {**_attribute_out(a, attr_usage.get(a.id, 0)), "options": []} for a in attributes}
    for option in options:
        result[option.attribute_id]["options"].append(_option_out(option, option_usage.get(option.id, 0)))
    return list(result.values())


# --- Характеристики ---------------------------------------------------------
async def create_attribute(db: AsyncSession, category_id: int, name: str, slug: str) -> dict:
    await get_or_404(db, Category, category_id, message="Категория не найдена")
    await _ensure_slug_free(db, category_id, slug)

    position = await db.scalar(
        select(func.coalesce(func.max(Attribute.position), -1) + 1)
        .where(Attribute.category_id == category_id)
    )
    attribute = Attribute(category_id=category_id, name=name, slug=slug, position=position)
    db.add(attribute)
    await commit_or_409(db, message=CONFLICT_MSG)  # страховка от гонки по уникальному slug
    await db.refresh(attribute)
    return _attribute_out(attribute)


async def update_attribute(db: AsyncSession, attribute_id: int, name: str, slug: str) -> dict:
    attribute = await get_or_404(db, Attribute, attribute_id, message="Характеристика не найдена")
    await _ensure_slug_free(db, attribute.category_id, slug, exclude_id=attribute_id)

    attribute.name = name
    attribute.slug = slug
    await commit_or_409(db, message=CONFLICT_MSG)
    return _attribute_out(attribute, await _usage(db, ProductOption.attribute_id, attribute_id))


async def delete_attribute(db: AsyncSession, attribute_id: int) -> None:
    """Варианты и выбранные у товаров значения удаляет сама БД (ON DELETE CASCADE)."""
    attribute = await get_or_404(db, Attribute, attribute_id, message="Характеристика не найдена")
    await db.delete(attribute)
    await commit_or_409(db, message=CONFLICT_MSG)


# --- Варианты ---------------------------------------------------------------
async def create_option(db: AsyncSession, attribute_id: int, value: str) -> dict:
    await get_or_404(db, Attribute, attribute_id, message="Характеристика не найдена")
    await _ensure_value_free(db, attribute_id, value)

    position = await db.scalar(
        select(func.coalesce(func.max(AttributeOption.position), -1) + 1)
        .where(AttributeOption.attribute_id == attribute_id)
    )
    option = AttributeOption(attribute_id=attribute_id, value=value, position=position)
    db.add(option)
    await commit_or_409(db, message=CONFLICT_MSG)
    await db.refresh(option)
    return _option_out(option)


async def update_option(db: AsyncSession, option_id: int, value: str) -> dict:
    option = await get_or_404(db, AttributeOption, option_id, message="Вариант не найден")
    await _ensure_value_free(db, option.attribute_id, value, exclude_id=option_id)

    option.value = value
    await commit_or_409(db, message=CONFLICT_MSG)
    return _option_out(option, await _usage(db, ProductOption.option_id, option_id))


async def delete_option(db: AsyncSession, option_id: int) -> None:
    """У товаров, где вариант был выбран, значение снимается каскадом в БД."""
    option = await get_or_404(db, AttributeOption, option_id, message="Вариант не найден")
    await db.delete(option)
    await commit_or_409(db, message=CONFLICT_MSG)