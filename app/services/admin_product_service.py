import math
from decimal import Decimal
from enum import Enum

from loguru import logger
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Attribute, AttributeOption, Brand, Category, Product, ProductOption
from app.schemas.admin_product import ProductIn
from app.services.product_attributes_service import fetch_product_attributes
from app.utils.admin_audit import describe_changes
from app.utils.database import commit_or_409, get_or_404
from app.utils.errors import AppError

audit = logger.bind(channel="audit")

LOW_STOCK = 5  # порог "мало на складе"
CONFLICT_CODE = "sku_taken"
# Поля, у которых в аудите показываются изменения
VALUE_FIELDS = ("price", "old_price", "stock_quantity", "is_active", "sku", "category_id", "brand_id")


class AdminSort(str, Enum):
    id_asc = "id_asc"
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"
    stock_asc = "stock_asc"
    stock_desc = "stock_desc"
    name = "name"


class StockFilter(str, Enum):
    in_stock = "in_stock"
    low = "low"
    out = "out"


# Первым ключом основное сравнение, вторым - всегда id, чтобы порядок между страницами был стабильным.
ORDER_BY = {
    AdminSort.id_asc: (Product.id.asc(),),
    AdminSort.newest: (Product.created_at.desc(), Product.id.desc()),
    AdminSort.price_asc: (Product.price.asc(), Product.id.asc()),
    AdminSort.price_desc: (Product.price.desc(), Product.id.desc()),
    AdminSort.stock_asc: (Product.stock_quantity.asc(), Product.id.asc()),
    AdminSort.stock_desc: (Product.stock_quantity.desc(), Product.id.desc()),
    AdminSort.name: (Product.name.asc(), Product.id.asc()),
}


async def _load_options(db: AsyncSession, data: ProductIn) -> list[AttributeOption]:
    if not data.option_ids:
        return []

    ids = set(data.option_ids)
    rows = (await db.scalars(
        select(AttributeOption)
        .join(Attribute, AttributeOption.attribute_id == Attribute.id)
        .where(AttributeOption.id.in_(ids), Attribute.category_id == data.category_id)
    )).all()

    if len(rows) != len(ids):
        logger.debug("Характеристики отклонены | причина=не относятся к категории category_id={}",
                     data.category_id)
        raise AppError(422, "options_invalid_for_category")
    if len({o.attribute_id for o in rows}) != len(rows):
        logger.debug("Характеристики отклонены | причина=несколько вариантов одной характеристики")
        raise AppError(422, "option_duplicate_attribute")
    return list(rows)


def _apply_options(product: Product, options: list[AttributeOption]) -> None:
    # attribute_id к option_id
    wanted = {o.attribute_id: o.id for o in options}
    current = {po.attribute_id: po for po in product.selected_options}

    for attr_id, po in current.items():
        # Сняли характеристику
        if attr_id not in wanted:
            product.selected_options.remove(po)
        # Выбрали другой вариант
        elif po.option_id != wanted[attr_id]:
            po.option_id = wanted[attr_id]

    for attr_id, option_id in wanted.items():
        if attr_id not in current:
            product.selected_options.append(ProductOption(attribute_id=attr_id, option_id=option_id))


# noinspection PyTypeChecker
async def _validate_refs(db: AsyncSession, data: ProductIn, product_id: int | None = None) -> None:
    """Проверяет, что категория и бренд существуют, а артикул не занят другим товаром."""
    if await db.scalar(select(Category.id).where(Category.id == data.category_id)) is None:
        logger.debug("Товар отклонён | причина=категория не найдена category_id={}", data.category_id)
        raise AppError(422, "category_not_found")

    if data.brand_id is not None:
        if await db.scalar(select(Brand.id).where(Brand.id == data.brand_id)) is None:
            logger.debug("Товар отклонён | причина=бренд не найден brand_id={}", data.brand_id)
            raise AppError(422, "brand_not_found")

    sku_stmt = select(Product.id).where(Product.sku == data.sku)
    if product_id is not None:
        sku_stmt = sku_stmt.where(Product.id != product_id)  # Свой же артикул при редактировании доступен
    if await db.scalar(sku_stmt) is not None:
        logger.debug("Товар отклонён | причина=артикул занят sku={}", data.sku)
        raise AppError(409, CONFLICT_CODE)


# --- Чтение -----------------------------------------------------------------

# noinspection PyTypeChecker
async def list_products(db: AsyncSession, *,
        search: str | None = None,
        category: str | None = None,
        is_active: bool | None = None,
        brand_id: int | None = None,
        without_brand: bool = False,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        has_discount: bool = False,
        stock: StockFilter | None = None,
        sort: AdminSort = AdminSort.id_asc,
        page: int = 1,
        page_size: int = 20,
) -> dict:
    if min_price is not None and max_price is not None and min_price > max_price:
        raise AppError(422, "price_range_invalid")

    stmt = select(Product)

    if category:
        stmt = stmt.join(Category, Product.category_id == Category.id).where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(or_(Product.name.ilike(f"%{search.strip()}%"),
                              Product.sku.ilike(f"%{search.strip()}%")))
    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))

    # Бренд фильтруем по brand_id напрямую, JOIN не нужен
    if without_brand:
        stmt = stmt.where(Product.brand_id.is_(None))
    elif brand_id is not None:
        stmt = stmt.where(Product.brand_id == brand_id)

    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if has_discount:
        stmt = stmt.where(Product.old_price.is_not(None), Product.old_price > Product.price)

    if stock == StockFilter.in_stock:
        stmt = stmt.where(Product.stock_quantity > 0)
    elif stock == StockFilter.low:
        stmt = stmt.where(Product.stock_quantity > 0, Product.stock_quantity <= LOW_STOCK)
    elif stock == StockFilter.out:
        stmt = stmt.where(Product.stock_quantity == 0)

    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        stmt.order_by(*ORDER_BY[sort]).offset((page - 1) * page_size).limit(page_size)
    )

    return {
        "items": result.all(),
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
    }


async def get_product(db: AsyncSession, product_id: int) -> Product:
    return await get_or_404(db, Product, product_id, code="product_not_found")


async def get_product_attributes(db: AsyncSession, product_id: int) -> list[dict]:
    await get_or_404(db, Product, product_id, code="product_not_found")
    return await fetch_product_attributes(db, product_id)


# --- Изменение --------------------------------------------------------------

async def create_product(db: AsyncSession, data: ProductIn, actor_id: int) -> Product:
    await _validate_refs(db, data)
    options = await _load_options(db, data)

    product = Product(**data.model_dump(exclude={"option_ids"}))
    _apply_options(product, options)
    db.add(product)
    await commit_or_409(db, code=CONFLICT_CODE)
    await db.refresh(product)
    await db.refresh(product, ["selected_options"])  # новые ProductOption нужно подтянуть заново

    audit.info("Товар создан | product_id={} sku={} цена={} остаток={} admin_id={}",
               product.id, product.sku, product.price, product.stock_quantity, actor_id)
    return product


async def update_product(db: AsyncSession, product_id: int, data: ProductIn, actor_id: int) -> Product:
    product = await get_or_404(db, Product, product_id, code="product_not_found")
    await _validate_refs(db, data, product_id=product_id)
    options = await _load_options(db, data)

    new_values = data.model_dump(exclude={"option_ids"})
    # Старые значения запоминаем до изменения: после него сравнивать будет уже не с чем
    old_values = {field: getattr(product, field) for field in new_values}
    old_values["option_ids"] = sorted(po.option_id for po in product.selected_options)

    for field, value in new_values.items():
        setattr(product, field, value)
    _apply_options(product, options)

    await commit_or_409(db, code=CONFLICT_CODE)
    await db.refresh(product, ["selected_options"])

    changes = describe_changes(
        old_values, {**new_values, "option_ids": sorted(o.id for o in options)}, VALUE_FIELDS
    )
    if changes:  # PUT без реальных изменений в аудит не пишем
        audit.info("Товар изменён | product_id={} изменено=[{}] admin_id={}", product_id, changes, actor_id)
    return product


async def set_product_active(db: AsyncSession, product_id: int, is_active: bool, actor_id: int) -> Product:
    # Изменение is_active работает как мягкое удаление
    product = await get_or_404(db, Product, product_id, code="product_not_found")
    product.is_active = is_active
    await commit_or_409(db, code=CONFLICT_CODE)

    audit.info("Товар {} | product_id={} admin_id={}",
               "показан" if is_active else "скрыт", product_id, actor_id)
    return product