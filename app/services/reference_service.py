from fastapi import HTTPException
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Brand, Category, Product
from app.schemas.admin_reference import BrandIn, CategoryIn
from app.utils.admin_audit import describe_changes
from app.utils.database import commit_or_409, get_or_404

audit = logger.bind(channel="audit")

CONFLICT_MSG = "Конфликт данных: slug занят или запись используется товарами"
VALUE_FIELDS = ("name", "slug", "is_active")


# --- Вспомогательные функции ------------------------------------------------
async def _ensure_slug_free(db: AsyncSession, model, slug: str, exclude_id: int | None = None) -> None:
    stmt = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)  # свой же slug при редактировании доступен
    if await db.scalar(stmt) is not None:
        logger.debug("Slug занят | модель={} slug={}", model.__name__, slug)
        raise HTTPException(status_code=409, detail="Такой slug уже занят")


async def _products_count(db: AsyncSession, column, item_id: int) -> int:
    return await db.scalar(select(func.count(Product.id)).where(column == item_id)) or 0


# --- Бренды -----------------------------------------------------------------
def _brand_out(brand: Brand, products_count: int) -> dict:
    return {
        "id": brand.id,
        "name": brand.name,
        "slug": brand.slug,
        "is_active": brand.is_active,
        "products_count": products_count,
    }


async def list_brands(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        select(Brand, func.count(Product.id))
        .outerjoin(Product, Product.brand_id == Brand.id)
        .group_by(Brand.id)
        .order_by(Brand.name)
    )
    return [_brand_out(brand, count) for brand, count in rows.all()]


async def create_brand(db: AsyncSession, data: BrandIn, actor_id: int) -> dict:
    await _ensure_slug_free(db, Brand, data.slug)

    brand = Brand(**data.model_dump())
    db.add(brand)
    await commit_or_409(db, message=CONFLICT_MSG)
    await db.refresh(brand)

    audit.info("Бренд создан | brand_id={} название={} admin_id={}", brand.id, brand.name, actor_id)
    return _brand_out(brand, 0)


async def update_brand(db: AsyncSession, brand_id: int, data: BrandIn, actor_id: int) -> dict:
    brand = await get_or_404(db, Brand, brand_id, message="Бренд не найден")
    await _ensure_slug_free(db, Brand, data.slug, exclude_id=brand_id)

    new_values = data.model_dump()
    old_values = {field: getattr(brand, field) for field in new_values}  # до изменения
    for field, value in new_values.items():
        setattr(brand, field, value)

    await commit_or_409(db, message=CONFLICT_MSG)

    changes = describe_changes(old_values, new_values, VALUE_FIELDS)
    if changes:
        audit.info("Бренд изменён | brand_id={} изменено=[{}] admin_id={}", brand_id, changes, actor_id)
    return _brand_out(brand, await _products_count(db, Product.brand_id, brand_id))


async def set_brand_active(db: AsyncSession, brand_id: int, is_active: bool, actor_id: int) -> dict:
    brand = await get_or_404(db, Brand, brand_id, message="Бренд не найден")
    brand.is_active = is_active
    await commit_or_409(db, message=CONFLICT_MSG)

    audit.info("Бренд {} | brand_id={} admin_id={}",
               "показан" if is_active else "скрыт", brand_id, actor_id)
    return _brand_out(brand, await _products_count(db, Product.brand_id, brand_id))


async def delete_brand(db: AsyncSession, brand_id: int, actor_id: int) -> None:
    brand = await get_or_404(db, Brand, brand_id, message="Бренд не найден")

    count = await _products_count(db, Product.brand_id, brand_id)
    if count:
        logger.debug("Удаление бренда отклонено | brand_id={} товаров={}", brand_id, count)
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить: к бренду привязано товаров: {count}. Скройте бренд или смените бренд у товаров",
        )

    name = brand.name  # до удаления: после него объект уже не пригодится
    await db.delete(brand)
    await commit_or_409(db, message=CONFLICT_MSG)

    audit.info("Бренд удалён | brand_id={} название={} admin_id={}", brand_id, name, actor_id)


# --- Категории --------------------------------------------------------------
def _category_out(category: Category, products_count: int) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "products_count": products_count,
    }


async def list_categories(db: AsyncSession) -> list[dict]:
    rows = await db.execute(
        select(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    )
    return [_category_out(category, count) for category, count in rows.all()]


async def create_category(db: AsyncSession, data: CategoryIn, actor_id: int) -> dict:
    await _ensure_slug_free(db, Category, data.slug)

    category = Category(**data.model_dump())
    db.add(category)
    await commit_or_409(db, message=CONFLICT_MSG)
    await db.refresh(category)

    audit.info("Категория создана | category_id={} название={} admin_id={}",
               category.id, category.name, actor_id)
    return _category_out(category, 0)


async def update_category(db: AsyncSession, category_id: int, data: CategoryIn, actor_id: int) -> dict:
    category = await get_or_404(db, Category, category_id, message="Категория не найдена")
    await _ensure_slug_free(db, Category, data.slug, exclude_id=category_id)

    new_values = data.model_dump()
    old_values = {field: getattr(category, field) for field in new_values}  # до изменения
    for field, value in new_values.items():
        setattr(category, field, value)

    await commit_or_409(db, message=CONFLICT_MSG)

    changes = describe_changes(old_values, new_values, VALUE_FIELDS)
    if changes:
        audit.info("Категория изменена | category_id={} изменено=[{}] admin_id={}",
                   category_id, changes, actor_id)
    return _category_out(category, await _products_count(db, Product.category_id, category_id))


async def delete_category(db: AsyncSession, category_id: int, actor_id: int) -> None:
    category = await get_or_404(db, Category, category_id, message="Категория не найдена")

    count = await _products_count(db, Product.category_id, category_id)
    if count:
        logger.debug("Удаление категории отклонено | category_id={} товаров={}", category_id, count)
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить: в категории товаров: {count}. Сначала перенесите их в другую категорию",
        )

    name = category.name  # до удаления
    await db.delete(category)
    await commit_or_409(db, message=CONFLICT_MSG)

    audit.info("Категория удалена | category_id={} название={} admin_id={}", category_id, name, actor_id)