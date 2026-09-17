from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=True)

async_session = async_sessionmaker(bind=engine,
                       expire_on_commit=False)

async def get_db():
    # Вызов фабрики () создает контекстный менеджер, который возвращает AsyncSession
    async with async_session() as db:
        yield db
    # Контекстный менеджер сам закроет сессию, поэтому close() не нужен