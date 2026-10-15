from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import Cart, CartItem, Product
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartOut

router = APIRouter(prefix="/cart", tags=["cart"])


async def _get_cart(db: AsyncSession, user) -> Cart:
    return await db.scalar(select(Cart).where(Cart.user_id == user.id))


async def _build_cart_out(db: AsyncSession, cart: Cart) -> CartOut:
    rows = (await db.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.product))
        .order_by(CartItem.id)
    )).all()

    items = [
        {
            "id": r.id,
            "product": r.product,
            "quantity": r.quantity,
            "subtotal": r.product.price * r.quantity,
        }
        for r in rows
    ]
    return CartOut(
        items=items,
        total=sum((i["subtotal"] for i in items), Decimal("0")),
        total_quantity=sum(i["quantity"] for i in items),
    )


async def _get_own_item(db: AsyncSession, cart: Cart, item_id: int) -> CartItem:
    # фильтр по cart_id обязателен: иначе можно менять чужую корзину по id
    item = await db.scalar(
        select(CartItem)
        .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.product))
    )
    if item is None:
        raise HTTPException(404, "Позиция не найдена")
    return item


def _check_stock(product: Product, quantity: int):
    if quantity > product.stock_quantity:
        raise HTTPException(
            409, f"Доступно только {product.stock_quantity} шт. товара «{product.name}»"
        )


@router.get("", response_model=CartOut)
async def get_cart(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    cart = await _get_cart(db, user)
    return await _build_cart_out(db, cart)


@router.post("/items", response_model=CartOut)
async def add_item(data: CartItemAdd, db: AsyncSession = Depends(get_db),
                   user=Depends(get_current_user)):
    cart = await _get_cart(db, user)

    product = await db.get(Product, data.product_id)
    if product is None or not product.is_active:
        raise HTTPException(404, "Товар не найден")

    item = await db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id,
                               CartItem.product_id == product.id)
    )
    new_qty = (item.quantity if item else 0) + data.quantity
    _check_stock(product, new_qty)

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=new_qty))
    await db.commit()
    return await _build_cart_out(db, cart)


@router.patch("/items/{item_id}", response_model=CartOut)
async def update_item(item_id: int, data: CartItemUpdate,
                      db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    cart = await _get_cart(db, user)
    item = await _get_own_item(db, cart, item_id)
    _check_stock(item.product, data.quantity)
    item.quantity = data.quantity
    await db.commit()
    return await _build_cart_out(db, cart)


@router.delete("/items/{item_id}", response_model=CartOut)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db),
                      user=Depends(get_current_user)):
    cart = await _get_cart(db, user)
    item = await _get_own_item(db, cart, item_id)
    await db.delete(item)
    await db.commit()
    return await _build_cart_out(db, cart)