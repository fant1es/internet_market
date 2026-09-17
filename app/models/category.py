from sqlalchemy import Column, Integer, String, Boolean

from app.database import Base

class Category(Base):
    __tablename__ = 'categories'

    id: int = Column(Integer, primary_key=True)
    name: str = Column(String, nullable=False)
    slug: str = Column(String, nullable=False, unique=True) # Понятное для человека URL
    is_active: bool = Column(Boolean, nullable=False, default=True)
