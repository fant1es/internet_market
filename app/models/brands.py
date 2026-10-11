from sqlalchemy import Column, Integer, String, Boolean

from app.database import Base

class Brand(Base):
    __tablename__ = 'brands'

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False, unique=True)
    slug: str = Column(String, nullable=False, unique=True)
    is_active: bool = Column(Boolean, nullable=False, default=True)