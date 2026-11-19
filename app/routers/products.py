import math
from collections import defaultdict
from decimal import Decimal
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Attribute, AttributeOption, Brand, Category, Product, ProductOption
from app.schemas.attribute import ProductAttributeOut
from app.schemas.product import ProductListOut, ProductOut, PriceRangeOut
from app.services.product_attributes_service import fetch_product_attributes

router = APIRouter(prefix="/products", tags=["products"])


class ProductSort(str, Enum):
    newest = "newest"
    price_asc = "price_asc"
    price_desc = "price_desc"


# Для каждой сортировки вторым параметром учитываем id, чтобы избежать дублей и ошибок
ORDER_BY = {
    ProductSort.newest: (Product.created_at.desc(), Product.id.desc()),
    ProductSort.price_asc: (Product.price.asc(), Product.id.asc()),
    ProductSort.price_desc: (Product.price.desc(), Product.id.desc()),
}


def _public_products():
    """Базовый запрос, который может обрастать дополнительными условиями"""
    return (
        # Всегда должно быть совпадение по категории и активность товара
        select(Product)
        .join(Category, Product.category_id == Category.id)
        .where(Product.is_active.is_(True), Category.is_active.is_(True))
    )


# noinspection PyTypeChecker
async def _filter_by_options(db: AsyncSession, stmt, option_ids: list[int], category_slug: str | None):
    """Фильтр по вариантам характеристик: внутри одного атрибута 'или', между атрибутами 'и'"""
    ids = set(option_ids)

    found = select(AttributeOption.id, AttributeOption.attribute_id).where(AttributeOption.id.in_(ids))
    if category_slug:
        # Если выбрана категория, варианты должны относиться к её характеристикам
        found = (
            found.join(Attribute, Attribute.id == AttributeOption.attribute_id)
            .join(Category, Category.id == Attribute.category_id)
            .where(Category.slug == category_slug)
        )
    rows = (await db.execute(found)).all()

    # Если нашлось меньше, чем передали: часть id не существует или чужая для категории.
    # Лучше ошибка, чем молчаливое игнорирование: иначе фильтр выглядел бы применённым
    if len(rows) != len(ids):
        raise HTTPException(
            status_code=422,
            detail="Вариант характеристики не найден или не относится к выбранной категории",
        )

    # Группируем выбранные варианты по атрибутам: attribute_id -> [option_id, ...]
    groups: dict[int, list[int]] = defaultdict(list)
    for option_id, attribute_id in rows:
        groups[attribute_id].append(option_id)

    # По одному EXISTS на атрибут, т.к. JOIN размножал бы строки товаров при нескольких вариантах
    for group in groups.values():
        stmt = stmt.where(
            exists().where(ProductOption.product_id == Product.id, ProductOption.option_id.in_(group))
        )
    return stmt


@router.get("", response_model=ProductListOut, summary="Список товаров")
async def list_products(
    category: str | None = Query(None, description="slug категории, например 'laptops'"),
    search: str | None = Query(None, max_length=100, description="поиск по названию"),
    min_price: Decimal | None = Query(None, ge=0, description="цена от (включительно)"),
    max_price: Decimal | None = Query(None, ge=0, description="цена до (включительно)"),
    brand: list[str] | None = Query(None, description="slug бренда, можно несколько: ?brand=apple&brand=asus"),
    has_discount: bool = Query(False, description="только товары со скидкой"),
    sort: ProductSort = Query(ProductSort.newest, description="порядок сортировки"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
    option: list[int] | None = Query(None, description="id варианта характеристики, можно несколько: ?option=3&option=7"),
    db: AsyncSession = Depends(get_db),
):
    if min_price is not None and max_price is not None and min_price > max_price:
        raise HTTPException(
            status_code=422,
            detail="Минимальная цена не может быть больше максимальной",
        )

    stmt = _public_products()

    if category:
        stmt = stmt.where(Category.slug == category)
    if search and search.strip():
        stmt = stmt.where(Product.name.ilike(f"%{search.strip()}%"))
    # Фильтруем по price, чтобы учитывалась скидка
    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)

    # JOIN с брендами только когда фильтр задан, ибо есть товары без бренда
    if brand:
        stmt = stmt.join(Brand, Product.brand_id == Brand.id).where(
            Brand.slug.in_(brand),
            Brand.is_active.is_(True),
        )
    # old_price > price защищает от некорректных данных и совпадает с условием показа карточки товара
    if has_discount:
        stmt = stmt.where(Product.old_price.is_not(None), Product.old_price > Product.price)

    if option:
        stmt = await _filter_by_options(db, stmt, option, category)

    # Сколько всего товаров под фильтром (считаем до order_by/offset/limit)
    total = await db.scalar(select(func.count()).select_from(stmt.subquery()))

    result = await db.scalars(
        # Обязательно упорядочить для страниц
        stmt.order_by(*ORDER_BY[sort])
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


@router.get("/price-range", response_model=PriceRangeOut, summary="Границы цен для слайдера")
async def price_range(category: str | None = Query(None), db: AsyncSession = Depends(get_db)):
    stmt = _public_products()
    if category:
        stmt = stmt.where(Category.slug == category)

    sub = stmt.subquery()
    row = (await db.execute(select(func.min(sub.c.price), func.max(sub.c.price)))).one()
    return {"price_min": row[0], "price_max": row[1]}


@router.get("/{product_id}", response_model=ProductOut, summary="Карточка товара")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.scalar(_public_products().where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return product


# noinspection PyTypeChecker
@router.get("/{product_id}/attributes", response_model=list[ProductAttributeOut],
            summary="Характеристики товара")
async def get_product_attributes(product_id: int, db: AsyncSession = Depends(get_db)):
    # Сначала убеждаемся, что товар существует и виден публично (активен, категория активна)
    exists_ = await db.scalar(_public_products().where(Product.id == product_id).with_only_columns(Product.id))
    if exists_ is None:
        raise HTTPException(status_code=404, detail="Товар не найден")

    return await fetch_product_attributes(db, product_id)