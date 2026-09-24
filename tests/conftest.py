import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import settings

# Отдельная тестовая база данных
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/test_db"

@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Создаёт все таблицы перед тестом, отдаёт сессию для работы с БД,
    после теста удаляет все таблицы — следующий тест стартует с чистого листа. """
    # NullPool отключает пул соединений SQLAlchemy
    test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    test_session_local = async_sessionmaker(bind=test_engine, expire_on_commit=False)

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with test_session_local() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    # Явное закрытие всех соединений движка
    await test_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    Тестовый HTTP-клиент, обращающийся к приложению в памяти.
    Подменяет реальную зависимость get_db на тестовую сессию db_session,
    чтобы роуты внутри приложения работали с тестовой БД, а не с рабочей.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()