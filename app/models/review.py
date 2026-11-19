from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint, func, Column, Integer, DateTime,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Review(Base):
    __tablename__ = "reviews"

    id: int = Column(Integer, primary_key=True, nullable=False)

    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id: int = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"),
                             index=True, nullable=False)

    rating: Decimal = Column(Numeric(2,1), nullable=False)
    title: str = Column(String(150), nullable=False)
    body: str = Column(Text, nullable=False)
    pros: str | None = Column(Text, nullable=True)
    cons: str | None = Column(Text, nullable=True)

    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())
    updated_at: datetime = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="reviews")
    product = relationship("Product", back_populates="reviews")

    __table_args__ = (
        # Один пользователь имеет один отзыв на товар
        UniqueConstraint("user_id", "product_id", name="uq_reviews_user_product"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_reviews_rating_range"),
    )