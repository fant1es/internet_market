from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.product import ProductOut


class ProductIn(BaseModel):
    """Данные товара для POST и PUT."""
    # Пробелы по краям строк обрезаются автоматически
    model_config = ConfigDict(str_strip_whitespace=True)

    category_id: int
    brand_id: int | None = None
    sku: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    old_price: Decimal | None = Field(None, gt=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(0, ge=0, le=1_000_000)
    is_active: bool = True

    @model_validator(mode="after")
    def check_old_price(self):
        # Старая цена нужна только для показа скидки, значит, она обязана быть выше текущей
        if self.old_price is not None and self.old_price <= self.price:
            raise ValueError("Старая цена должна быть больше текущей")
        return self


class ActiveUpdate(BaseModel):
    """Отдельное тело запроса для скрытия/показа товара."""
    is_active: bool


class ProductAdminOut(ProductOut):
    """Товар для админа (как у юзеров + служебные поля)"""
    is_active: bool
    created_at: datetime


class ProductAdminListOut(BaseModel):
    items: list[ProductAdminOut]
    total: int
    page: int
    page_size: int
    pages: int