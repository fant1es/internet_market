from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import Column, Integer, String, Enum as SQLEnum, Boolean, DateTime, func, DECIMAL, CheckConstraint, text

from app.database import Base


class UserRole(str, Enum):
    ADMIN = 'admin'
    USER = 'user'


class User(Base):
    __tablename__ = 'users'

    id: int = Column(Integer, primary_key=True)

    name: str = Column(String, nullable=False)
    email: str = Column(String, unique=True, nullable=False)
    password_hash: str = Column(String, nullable=False)

    balance: Decimal = Column(DECIMAL(10, 2), nullable=False, server_default=text("0"))

    role: UserRole = Column(SQLEnum(UserRole,
                                    values_callable=lambda obj: [e.value for e in obj], # Храним как строку
                                    native_enum=False), nullable=False, default=UserRole.USER)

    is_active: bool = Column(Boolean, nullable=False, default=True)
    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_users_balance_nonneg"),
    )