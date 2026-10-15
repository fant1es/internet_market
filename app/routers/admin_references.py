from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_admin
from app.models import Brand, Category, Product
from app.schemas.admin_product import ActiveUpdate
from app.schemas.admin_reference import BrandAdminOut, BrandIn, CategoryAdminOut, CategoryIn


# Отдельные админские пути
brands_admin = APIRouter(
    prefix="/admin/brands",
    tags=["admin: brands"],
    dependencies=[Depends(get_current_admin)],
)
categories_admin = APIRouter(
    prefix="/admin/categories",
    tags=["admin: categories"],
    dependencies=[Depends(get_current_admin)],
)


# Вспомогательные функции
async def _get_or_404(db: AsyncSession, model, item_id: int, message: str):
    item = await db.get(model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=message)
    return item


async def _ensure_slug_free(db: AsyncSession, model, slug: str, exclude_id: int | None = None) -> None:
    stmt = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        stmt = stmt.where(model.id != exclude_id)  # свой же slug при редактировании доступен
    if await db.scalar(stmt) is not None:
        raise HTTPException(status_code=409, detail="Такой slug уже занят")


async def _commit(db: AsyncSession) -> None:
    # Страховка на случай гонки или нарушения внешнего ключа
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Конфликт данных: slug занят или запись используется товарами")


async def _products_count(db: AsyncSession, column, item_id: int) -> int:
    return await db.scalar(select(func.count(Product.id)).where(column == item_id)) or 0


# region --- Бренды ----------------------------------------------------------------
def _brand_out(brand: Brand, products_count: int) -> dict:
    return {
        "id": brand.id,
        "name": brand.name,
        "slug": brand.slug,
        "is_active": brand.is_active,
        "products_count": products_count,
    }


@brands_admin.get("", response_model=list[BrandAdminOut], summary="Все бренды (включая скрытые)")
async def list_brands(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(Brand, func.count(Product.id))
        .outerjoin(Product, Product.brand_id == Brand.id)
        .group_by(Brand.id)
        .order_by(Brand.name)
    )
    return [_brand_out(brand, count) for brand, count in rows.all()]


@brands_admin.post("", response_model=BrandAdminOut, status_code=201, summary="Создать бренд")
async def create_brand(data: BrandIn, db: AsyncSession = Depends(get_db)):
    await _ensure_slug_free(db, Brand, data.slug)

    brand = Brand(**data.model_dump())
    db.add(brand)
    await _commit(db)
    await db.refresh(brand)
    return _brand_out(brand, 0)


@brands_admin.put("/{brand_id}", response_model=BrandAdminOut, summary="Обновить бренд")
async def update_brand(brand_id: int, data: BrandIn, db: AsyncSession = Depends(get_db)):
    brand = await _get_or_404(db, Brand, brand_id, "Бренд не найден")
    await _ensure_slug_free(db, Brand, data.slug, exclude_id=brand_id)

    for field, value in data.model_dump().items():
        setattr(brand, field, value)

    await _commit(db)
    return _brand_out(brand, await _products_count(db, Product.brand_id, brand_id))


@brands_admin.patch("/{brand_id}/active", response_model=BrandAdminOut, summary="Скрыть или показать бренд")
async def set_brand_active(brand_id: int, data: ActiveUpdate, db: AsyncSession = Depends(get_db)):
    brand = await _get_or_404(db, Brand, brand_id, "Бренд не найден")
    brand.is_active = data.is_active
    await _commit(db)
    return _brand_out(brand, await _products_count(db, Product.brand_id, brand_id))


@brands_admin.delete("/{brand_id}", status_code=204, summary="Удалить бренд (только если нет товаров)")
async def delete_brand(brand_id: int, db: AsyncSession = Depends(get_db)):
    brand = await _get_or_404(db, Brand, brand_id, "Бренд не найден")

    count = await _products_count(db, Product.brand_id, brand_id)
    if count:
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить: к бренду привязано товаров: {count}. Скройте бренд или смените бренд у товаров",
        )

    await db.delete(brand)
    await _commit(db)
# endregion


# region --- Категории -------------------------------------------------------------
def _category_out(category: Category, products_count: int) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "products_count": products_count,
    }


@categories_admin.get("", response_model=list[CategoryAdminOut], summary="Все категории с числом товаров")
async def list_categories(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(Category, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .group_by(Category.id)
        .order_by(Category.name)
    )
    return [_category_out(category, count) for category, count in rows.all()]


@categories_admin.post("", response_model=CategoryAdminOut, status_code=201, summary="Создать категорию")
async def create_category(data: CategoryIn, db: AsyncSession = Depends(get_db)):
    await _ensure_slug_free(db, Category, data.slug)

    category = Category(**data.model_dump())
    db.add(category)
    await _commit(db)
    await db.refresh(category)
    return _category_out(category, 0)


@categories_admin.put("/{category_id}", response_model=CategoryAdminOut, summary="Обновить категорию")
async def update_category(category_id: int, data: CategoryIn, db: AsyncSession = Depends(get_db)):
    category = await _get_or_404(db, Category, category_id, "Категория не найдена")
    await _ensure_slug_free(db, Category, data.slug, exclude_id=category_id)

    for field, value in data.model_dump().items():
        setattr(category, field, value)

    await _commit(db)
    return _category_out(category, await _products_count(db, Product.category_id, category_id))


@categories_admin.delete("/{category_id}", status_code=204, summary="Удалить категорию (только если нет товаров)")
async def delete_category(category_id: int, db: AsyncSession = Depends(get_db)):
    category = await _get_or_404(db, Category, category_id, "Категория не найдена")

    count = await _products_count(db, Product.category_id, category_id)
    if count:
        raise HTTPException(
            status_code=409,
            detail=f"Нельзя удалить: в категории товаров: {count}. Сначала перенесите их в другую категорию",
        )

    await db.delete(category)
    await _commit(db)
# endregion