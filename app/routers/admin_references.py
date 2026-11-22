from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentAdmin, get_current_admin
from app.schemas.admin_product import ActiveUpdate
from app.schemas.admin_reference import BrandAdminOut, BrandIn, CategoryAdminOut, CategoryIn
from app.schemas.category import FilterAttributeOut
from app.services import attribute_service, reference_service


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


# region --- Бренды ----------------------------------------------------------------
@brands_admin.get("", response_model=list[BrandAdminOut], summary="Все бренды (включая скрытые)")
async def list_brands(db: AsyncSession = Depends(get_db)):
    return await reference_service.list_brands(db)


@brands_admin.post("", response_model=BrandAdminOut, status_code=201, summary="Создать бренд")
async def create_brand(data: BrandIn, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    return await reference_service.create_brand(db, data, actor_id=admin.id)


@brands_admin.put("/{brand_id}", response_model=BrandAdminOut, summary="Обновить бренд")
async def update_brand(brand_id: int, data: BrandIn, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    return await reference_service.update_brand(db, brand_id, data, actor_id=admin.id)


@brands_admin.patch("/{brand_id}/active", response_model=BrandAdminOut, summary="Скрыть или показать бренд")
async def set_brand_active(brand_id: int, data: ActiveUpdate, admin: CurrentAdmin,
                           db: AsyncSession = Depends(get_db)):
    return await reference_service.set_brand_active(db, brand_id, data.is_active, actor_id=admin.id)


@brands_admin.delete("/{brand_id}", status_code=204, summary="Удалить бренд (только если нет товаров)")
async def delete_brand(brand_id: int, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    await reference_service.delete_brand(db, brand_id, actor_id=admin.id)
# endregion


# region --- Категории -------------------------------------------------------------
@categories_admin.get("", response_model=list[CategoryAdminOut], summary="Все категории с числом товаров")
async def list_categories(db: AsyncSession = Depends(get_db)):
    return await reference_service.list_categories(db)


@categories_admin.post("", response_model=CategoryAdminOut, status_code=201, summary="Создать категорию")
async def create_category(data: CategoryIn, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    return await reference_service.create_category(db, data, actor_id=admin.id)


@categories_admin.put("/{category_id}", response_model=CategoryAdminOut, summary="Обновить категорию")
async def update_category(category_id: int, data: CategoryIn, admin: CurrentAdmin,
                          db: AsyncSession = Depends(get_db)):
    return await reference_service.update_category(db, category_id, data, actor_id=admin.id)


@categories_admin.delete("/{category_id}", status_code=204, summary="Удалить категорию (только если нет товаров)")
async def delete_category(category_id: int, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    await reference_service.delete_category(db, category_id, actor_id=admin.id)


# noinspection PyTypeChecker
@categories_admin.get("/{category_id}/attributes", response_model=list[FilterAttributeOut],
                      summary="Характеристики категории с вариантами (для формы товара)")
async def category_attributes(category_id: int, db: AsyncSession = Depends(get_db)):
    attributes = await attribute_service.list_attributes(db, category_id)
    # Если характеристика без вариантов, то выбирать нечем
    return [a for a in attributes if a["options"]]
# endregion