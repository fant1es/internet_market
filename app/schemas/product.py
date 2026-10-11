from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ProductOut(BaseModel):
    # Позволяет собирать схему из ORM-объекта
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    brand_id: int | None
    sku: str
    name: str
    description: str | None
    price: Decimal
    old_price: Decimal | None  # Цена до скидки, None если скидки нет
    stock_quantity: int
    image_path: str | None


class ProductListOut(BaseModel):
    # Модель для страницы каталога с товарами и данными для построения страницы
    items: list[ProductOut]
    total: int       # сколько товаров всего подошло под фильтр
    page: int        # текущая страница (с 1)
    page_size: int   # размер страницы
    pages: int       # всего страниц