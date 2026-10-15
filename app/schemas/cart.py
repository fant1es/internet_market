from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.product import ProductOut


class CartItemAdd(BaseModel):
    product_id: int
    quantity: int = Field(1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemOut(BaseModel):
    id: int
    product: ProductOut
    quantity: int
    subtotal: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal
    total_quantity: int