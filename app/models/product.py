from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DECIMAL, DateTime, CheckConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base

class Product(Base):
    __tablename__ = 'products'

    id: int = Column(Integer, primary_key=True)
    category_id: int = Column(Integer, ForeignKey('categories.id'), nullable=False)
    brand_id: int = Column(Integer, ForeignKey('brands.id'), nullable=True, index=True)

    sku: str = Column(String, unique=True, nullable=False) # Артикул
    name: str = Column(String, nullable=False)
    description: str = Column(Text, nullable=True)

    price: float = Column(DECIMAL(precision=10, scale=2), nullable=False) # Нынешняя цена(может быть со скидкой)
    old_price: float = Column(DECIMAL(precision=10, scale=2), nullable=True)  # Цена до скидки
    stock_quantity: int = Column(Integer, default=0, nullable=False)

    image_path: str = Column(String, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())
    is_active: bool = Column(Boolean, default=True, nullable=False)

    selected_options = relationship(
        "ProductOption",
        cascade="all, delete-orphan",  # если убрали из списка, то строка удалится из БД
        passive_deletes=True,  # при удалении товара каскад сделает сама БД
        lazy="selectin",
    )


    reviews = relationship(
        "Review",
        back_populates="product",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def option_ids(self) -> list[int]:
        return [po.option_id for po in self.selected_options]

    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_products_stock_nonneg"),
    )