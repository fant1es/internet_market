from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base

class CartItem(Base):
    __tablename__ = 'cart_items'

    id: int = Column(Integer, primary_key=True)
    cart_id: int = Column(Integer, ForeignKey('carts.id'), nullable=False)
    product_id: int = Column(Integer, ForeignKey('products.id'), nullable=False)
    quantity: int = Column(Integer, default=1, nullable=False)

    # Нужен для selectinload()
    product = relationship("Product", lazy="raise")

    __table_args__ = (
        UniqueConstraint('cart_id', 'product_id', name='uq_cart_product'),
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_pos"),
    )