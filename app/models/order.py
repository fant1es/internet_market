from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, ForeignKey, Enum as SQLEnum, DECIMAL, Text, Boolean, DateTime, func

from app.database import Base


class OrderStatus(str, Enum):
    PENDING = 'pending'
    PAID = 'paid'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class Order(Base):
    __tablename__ = 'orders'

    id: int = Column(Integer, primary_key=True)
    user_id: int = Column(Integer, ForeignKey('users.id'), nullable=False)
    status: str = Column(SQLEnum(OrderStatus,
                                 values_callable=lambda obj: [e.value for e in obj],
                                 native_enum=False), nullable=False, default=OrderStatus.PENDING)

    total_amount: float = Column(DECIMAL(precision=10, scale=2), nullable=False)
    shipping_address: str = Column(Text, nullable=True)
    receipt_sent: bool = Column(Boolean, nullable=False, default=False)

    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())