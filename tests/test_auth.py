import pytest
from sqlalchemy import select

from app.models import Cart


# --- Регистрация -----------------------------------------------------------
async def test_register_success(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "secret123",
        "name": "Test User",
    })

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["role"] == "user"
    assert "password" not in data
    assert "password_hash" not in data


async def test_register_creates_cart(client, db_session):
    response = await client.post("/auth/register", json={
        "email": "cart@example.com",
        "password": "secret123",
        "name": "Test User",
    })
    user_id = response.json()["id"]

    result = await db_session.execute(select(Cart).where(Cart.user_id == user_id))
    cart = result.scalar_one_or_none()

    assert cart is not None


async def test_register_duplicate_email(client):
    payload = {
        "email": "dup@example.com",
        "password": "secret123",
        "name": "Test User",
    }

    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 200

    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400
    assert "зарегистрирована" in second.json()["detail"]


@pytest.mark.parametrize("password", [
    "123",           # короче 6 символов
    "a" * 25,        # длиннее 20 символов
    "пароль123",     # кириллица не разрешена
    "with space",    # пробел не разрешён
])
async def test_register_invalid_password(client, password):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": password,
        "name": "Test User",
    })
    assert response.status_code == 422 # status code связанный с провалом валидации Pydantic-схемы


async def test_register_invalid_name(client):
    response = await client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "secret123",
        "name": "Test123",  # цифры в имени
    })
    assert response.status_code == 422


async def test_register_invalid_email(client):
    response = await client.post("/auth/register", json={
        "email": "not-an-email",
        "password": "secret123",
        "name": "Test User",
    })
    assert response.status_code == 422


# --- Логин -------------------------------------------------------------

async def test_login_success(client):
    await client.post("/auth/register", json={
        "email": "login@example.com",
        "password": "secret123",
        "name": "Test User",
    })

    response = await client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "secret123",
    })

    assert response.status_code == 200
    assert "access_token" in response.cookies
    assert response.json()["email"] == "login@example.com"


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={
        "email": "wrongpass@example.com",
        "password": "secret123",
        "name": "Test User",
    })

    response = await client.post("/auth/login", json={
        "email": "wrongpass@example.com",
        "password": "wrongpassword",
    })

    assert response.status_code == 401


async def test_login_nonexistent_email(client):
    response = await client.post("/auth/login", json={
        "email": "ghost@example.com",
        "password": "whatever123",
    })

    assert response.status_code == 401


async def test_login_error_message_is_same_for_both_cases(client):
    """
    Сообщение об ошибке должно быть одинаковым и для несуществующего email,
    и для неверного пароля — чтобы не подсказывать атакующему, что именно неверно.
    """
    await client.post("/auth/register", json={
        "email": "sameerror@example.com",
        "password": "secret123",
        "name": "Test User",
    })

    wrong_password = await client.post("/auth/login", json={
        "email": "sameerror@example.com",
        "password": "wrongpassword",
    })
    no_such_user = await client.post("/auth/login", json={
        "email": "ghost2@example.com",
        "password": "whatever123",
    })

    assert wrong_password.json()["detail"] == no_such_user.json()["detail"]


# --- /auth/me -----------------------------------------------------------
async def test_me_requires_auth(client):
    response = await client.get("/auth/me")
    assert response.status_code == 401


async def test_me_with_valid_session(client):
    await client.post("/auth/register", json={
        "email": "me@example.com",
        "password": "secret123",
        "name": "Test User",
    })
    await client.post("/auth/login", json={
        "email": "me@example.com",
        "password": "secret123",
    })
    # AsyncClient сам хранит cookies между запросами в пределах одного client,
    # поэтому передавать токен вручную не нужно.

    response = await client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"


# --- /auth/logout ---------------------------------------------------------
async def test_logout_clears_session(client):
    await client.post("/auth/register", json={
        "email": "logout@example.com",
        "password": "secret123",
        "name": "Test User",
    })
    await client.post("/auth/login", json={
        "email": "logout@example.com",
        "password": "secret123",
    })

    logout_response = await client.post("/auth/logout")
    assert logout_response.status_code == 200

    me_response = await client.get("/auth/me")
    assert me_response.status_code == 401