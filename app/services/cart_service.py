from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Cart, CartItem, Product
from app.schemas.cart import CartOut


async def _get_cart(db: AsyncSession, user_id: int) -> Cart:
    cart = await db.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        raise HTTPException(404, "Корзина не найдена")
    return cart


async def _get_own_item(db: AsyncSession, cart: Cart, item_id: int) -> CartItem:
    # Фильтр по cart_id обязателен, чтобы нельзя было менять чужую корзину по id
    item = await db.scalar(
        select(CartItem)
        .where(CartItem.id == item_id, CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.product))
    )
    if item is None:
        raise HTTPException(404, "Позиция не найдена")
    return item


def _check_stock(product: Product, quantity: int) -> None:
    if quantity > product.stock_quantity:
        raise HTTPException(
            409, f"Доступно только {product.stock_quantity} шт. товара «{product.name}»"
        )


async def get_cart_out(db: AsyncSession, user_id: int) -> CartOut:
    cart = await _get_cart(db, user_id)
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


async def add_item(db: AsyncSession, user_id: int, product_id: int, quantity: int) -> CartOut:
    cart = await _get_cart(db, user_id)

    product = await db.get(Product, product_id)
    if product is None or not product.is_active:
        raise HTTPException(404, "Товар не найден")

    item = await db.scalar(
        select(CartItem).where(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
    )
    new_qty = (item.quantity if item else 0) + quantity
    _check_stock(product, new_qty)

    if item:
        item.quantity = new_qty
    else:
        db.add(CartItem(cart_id=cart.id, product_id=product.id, quantity=new_qty))
    await db.commit()
    return await get_cart_out(db, user_id)


async def update_item(db: AsyncSession, user_id: int, item_id: int, quantity: int) -> CartOut:
    cart = await _get_cart(db, user_id)
    item = await _get_own_item(db, cart, item_id)
    _check_stock(item.product, quantity)
    item.quantity = quantity
    await db.commit()
    return await get_cart_out(db, user_id)


async def remove_item(db: AsyncSession, user_id: int, item_id: int) -> CartOut:
    cart = await _get_cart(db, user_id)
    item = await _get_own_item(db, cart, item_id)
    await db.delete(item)
    await db.commit()
    return await get_cart_out(db, user_id)