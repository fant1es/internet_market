from enum import Enum

from sqlalchemy import Column, Integer, DateTime, func, DECIMAL, ForeignKey, Enum as SQLEnum

from app.database import Base

class TransactionType(str, Enum):
    TOPUP = "topup"
    PAYMENT = "payment"
    REFUND = "refund"

class BalanceTransaction(Base):
    __tablename__ = "balance_transactions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=True, index=True)
    amount = Column(DECIMAL(10, 2), nullable=False)  # со знаком: + пополнение/возврат, − оплата
    type = Column(SQLEnum(TransactionType,
                          values_callable=lambda obj: [e.value for e in obj],  # Храним как строку
                          native_enum=False), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.now())