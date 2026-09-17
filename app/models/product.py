from datetime import datetime

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DECIMAL, DateTime, func

from app.database import Base

class Product(Base):
    __tablename__ = 'products'

    id: int = Column(Integer, primary_key=True)
    category_id: int = Column(Integer, ForeignKey('categories.id'), nullable=False)

    sku: str = Column(String, unique=True, nullable=False) # Артикул
    name: str = Column(String, nullable=False)
    description: str = Column(Text, nullable=True)

    price: float = Column(DECIMAL(precision=10, scale=2), nullable=False)
    stock_quantity: int = Column(Integer, default=0, nullable=False)

    image_path: str = Column(String, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())
    is_active: bool = Column(Boolean, default=True, nullable=False)