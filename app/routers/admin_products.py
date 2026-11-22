from decimal import Decimal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import CurrentAdmin, get_current_admin
from app.schemas.admin_product import ActiveUpdate, ProductAdminListOut, ProductAdminOut, ProductIn
from app.schemas.attribute import ProductAttributeOut
from app.services import admin_product_service, product_image_service
from app.services.admin_product_service import AdminSort, StockFilter
from app.services.image_storage import MAX_IMAGE_BYTES

router = APIRouter(
    prefix="/admin/products",
    tags=["admin: products"],
    dependencies=[Depends(get_current_admin)], # Роутер доступен только администраторам
)


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
    return await admin_product_service.list_products(
        db, search=search, category=category, is_active=is_active, brand_id=brand_id,
        without_brand=without_brand, min_price=min_price, max_price=max_price,
        has_discount=has_discount, stock=stock, sort=sort, page=page, page_size=page_size,
    )


@router.get("/{product_id}", response_model=ProductAdminOut, summary="Товар для редактирования")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    return await admin_product_service.get_product(db, product_id)


@router.get("/{product_id}/attributes", response_model=list[ProductAttributeOut], summary="Характеристики товара")
async def get_product_attributes(product_id: int, db: AsyncSession = Depends(get_db)):
    return await admin_product_service.get_product_attributes(db, product_id)


@router.post("", response_model=ProductAdminOut, status_code=201, summary="Создать товар")
async def create_product(data: ProductIn, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    return await admin_product_service.create_product(db, data, actor_id=admin.id)


@router.put("/{product_id}", response_model=ProductAdminOut, summary="Обновить товар целиком")
async def update_product(product_id: int, data: ProductIn, admin: CurrentAdmin,
                         db: AsyncSession = Depends(get_db)):
    return await admin_product_service.update_product(db, product_id, data, actor_id=admin.id)


@router.patch("/{product_id}/active", response_model=ProductAdminOut, summary="Скрыть или показать товар")
async def set_product_active(product_id: int, data: ActiveUpdate, admin: CurrentAdmin,
                             db: AsyncSession = Depends(get_db)):
    return await admin_product_service.set_product_active(db, product_id, data.is_active, actor_id=admin.id)


@router.post("/{product_id}/image", response_model=ProductAdminOut, summary="Загрузить изображение товара")
async def upload_product_image(product_id: int, admin: CurrentAdmin, file: UploadFile = File(...),
                               db: AsyncSession = Depends(get_db)):
    product = await admin_product_service.get_product(db, product_id)
    # Читаем на 1 байт больше лимита: так видно превышение, не загружая в память файл любого размера
    data = await file.read(MAX_IMAGE_BYTES + 1)
    return await product_image_service.set_image(db, product, data, actor_id=admin.id)


@router.delete("/{product_id}/image", response_model=ProductAdminOut, summary="Удалить изображение товара")
async def delete_image(product_id: int, admin: CurrentAdmin, db: AsyncSession = Depends(get_db)):
    product = await admin_product_service.get_product(db, product_id)
    return await product_image_service.clear_image(db, product, actor_id=admin.id)