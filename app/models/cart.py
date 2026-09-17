from datetime import datetime

from sqlalchemy import Column, Integer, ForeignKey, DateTime, func

from app.database import Base

class Cart(Base):
    __tablename__ = 'carts'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False)
    created_at: datetime = Column(DateTime, nullable=False, server_default=func.now())