from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.utils.security import hash_password


async def create_user(name: str, email: str, password: str, db: AsyncSession):
    password_hash = hash_password(password)
    user = User(name=name, email=email, password_hash=password_hash)
    db.add(user)
    await db.flush()
    return user