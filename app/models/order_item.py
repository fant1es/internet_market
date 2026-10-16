from sqlalchemy import Column, Integer, ForeignKey, DECIMAL, String, CheckConstraint
from sqlalchemy.orm import relationship

from app.database import Base

class OrderItem(Base):
    __tablename__ = 'order_items'

    id: int = Column(Integer, primary_key=True)
    order_id: int = Column(Integer, ForeignKey('orders.id'), nullable=False, index=True)
    product_id: int = Column(Integer, ForeignKey('products.id'), nullable=False)

    product_name: str = Column(String, nullable=False) # Снапшот имени на момент заказа
    product_price: float = Column(DECIMAL(10,2), nullable=False) # Снапшот цены на момент заказа
    quantity: int = Column(Integer, nullable=False)

    order = relationship("Order", back_populates="items", lazy="raise")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_pos"),
    )