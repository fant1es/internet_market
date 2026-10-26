from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.order import OrderStatus
from app.schemas.types import Phone


class CheckoutIn(BaseModel):
    """Схема с заполняемой пользователем формой"""
    model_config = ConfigDict(str_strip_whitespace=True)
    shipping_address: str = Field(min_length=5, max_length=500)
    contact_phone: Phone


class OrderItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: int
    product_name: str
    product_price: Decimal
    quantity: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: OrderStatus
    total_amount: Decimal
    shipping_address: str | None
    created_at: datetime
    items: list[OrderItemOut]