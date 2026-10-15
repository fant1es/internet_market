import itertools
from decimal import Decimal

import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db
from app.config import settings
from app.models import Brand, Cart, Category, Product, User
from app.models.user import UserRole
from app.utils.security import hash_password

# Отдельная тестовая база данных
TEST_DATABASE_URL = settings.database_url.rsplit("/", 1)[0] + "/test_db"

# Пароль всех тестовых пользователей
TEST_PASSWORD = "Secret123"


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
    Тестовый HTTP-клиент, обращающийся к приложению в памяти (анонимный, без входа).
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


# region --- Авторизованные клиенты ------------------------------------------------
# Cookie хранятся внутри каждого AsyncClient, поэтому для каждой роли свой клиент.
# Все клиенты работают с одним приложением и одной тестовой сессией

async def _create_user(session, email: str, role: UserRole) -> User:
    """Создаёт пользователя напрямую в БД без регистрации.
    Корзину заводим сразу, как это делает /auth/register: у каждого пользователя она есть."""
    user = User(name="Test User", email=email, password_hash=hash_password(TEST_PASSWORD), role=role)
    session.add(user)
    await session.commit()
    session.add(Cart(user_id=user.id))
    await session.commit()
    return user


async def _login(email: str) -> AsyncClient:
    """Новый клиент, который уже вошёл в систему: cookie с токеном сохраняется в нём."""
    ac = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    response = await ac.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return ac


@pytest_asyncio.fixture(scope="function")
async def admin_client(client, db_session):
    # Зависимость от client нужна, чтобы подмена get_db уже была установлена
    await _create_user(db_session, "admin@example.com", UserRole.ADMIN)
    ac = await _login("admin@example.com")
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture(scope="function")
async def user_client(client, db_session):
    await _create_user(db_session, "user@example.com", UserRole.USER)
    ac = await _login("user@example.com")
    yield ac
    await ac.aclose()


@pytest_asyncio.fixture(scope="function")
async def other_user_client(client, db_session):
    """Второй обычный пользователь: для проверок изоляции данных между аккаунтами."""
    await _create_user(db_session, "other@example.com", UserRole.USER)
    ac = await _login("other@example.com")
    yield ac
    await ac.aclose()
# endregion


# region --- Фабрики тестовых данных -----------------------------------------------
# Каждая фабрика сама подбирает уникальные slug/sku, переопределить можно любое поле:
#     await make_product(name="Особый", is_active=False)

@pytest_asyncio.fixture(scope="function")
async def make_category(db_session):
    counter = itertools.count(1)

    async def _make(**fields) -> Category:
        n = next(counter)
        category = Category(**{"name": f"Категория {n}", "slug": f"category-{n}", **fields})
        db_session.add(category)
        await db_session.commit()
        await db_session.refresh(category)
        return category

    return _make


@pytest_asyncio.fixture(scope="function")
async def make_brand(db_session):
    counter = itertools.count(1)

    async def _make(**fields) -> Brand:
        n = next(counter)
        brand = Brand(**{"name": f"Бренд {n}", "slug": f"brand-{n}", **fields})
        db_session.add(brand)
        await db_session.commit()
        await db_session.refresh(brand)
        return brand

    return _make


@pytest_asyncio.fixture(scope="function")
async def make_product(db_session, make_category):
    counter = itertools.count(1)

    async def _make(category: Category | None = None, brand: Brand | None = None, **fields) -> Product:
        n = next(counter)
        if category is None:
            category = await make_category()  # у товара обязательно есть категория

        product = Product(**{
            "sku": f"SKU-{n:03d}",
            "name": f"Товар {n}",
            "description": "Описание",
            "price": Decimal("100.00"),
            "old_price": None,
            "stock_quantity": 5,
            "is_active": True,
            "category_id": category.id,
            "brand_id": brand.id if brand else None,
            **fields,
        })
        db_session.add(product)
        await db_session.commit()
        await db_session.refresh(product)
        return product

    return _make
# endregion