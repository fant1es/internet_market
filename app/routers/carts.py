from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut
from app.services import cart_service

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartOut)
async def get_cart(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await cart_service.get_cart_out(db, user.id)


@router.post("/items", response_model=CartOut)
async def add_item(data: CartItemAdd, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await cart_service.add_item(db, user.id, data.product_id, data.quantity)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_item(item_id: int, data: CartItemUpdate,
                      db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await cart_service.update_item(db, user.id, item_id, data.quantity)


@router.delete("/items/{item_id}", response_model=CartOut)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await cart_service.remove_item(db, user.id, item_id)