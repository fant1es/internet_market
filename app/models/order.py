from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, ForeignKey, Enum as SQLEnum, DECIMAL, Text, Boolean, DateTime, func, String
from sqlalchemy.orm import relationship

from app.database import Base


class OrderStatus(str, Enum):
    PENDING = 'pending'
    PAID = 'paid'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class Order(Base):
    __tablename__ = 'orders'

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    status: str = Column(SQLEnum(OrderStatus,
                                 values_callable=lambda obj: [e.value for e in obj],
                                 native_enum=False), nullable=False, default=OrderStatus.PENDING)

    total_amount: float = Column(DECIMAL(precision=10, scale=2), nullable=False)

    contact_phone: str | None = Column(String(20), nullable=True)
    shipping_address: str = Column(Text, nullable=True)

    receipt_sent: bool = Column(Boolean, nullable=False, default=False)

    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())

    # Загружаем явно через selectinload()
    items = relationship("OrderItem", back_populates="order", lazy="raise")