from decimal import Decimal
from pydantic import BaseModel, Field
from app.schemas.product import ProductOut


class CartItemAdd(BaseModel):
    product_id: int = Field(ge=1, le=2_147_483_647)
    quantity: int = Field(1, ge=1, le=1_000_000)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1, le=1_000_000)


class CartItemOut(BaseModel):
    id: int
    product: ProductOut
    quantity: int
    subtotal: Decimal


class CartOut(BaseModel):
    items: list[CartItemOut]
    total: Decimal
    total_quantity: int