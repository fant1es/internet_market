import pytest


async def me(client) -> dict:
    return (await client.get("/auth/me")).json()


async def test_patch_requires_auth(client):
    assert (await client.patch("/users/me", json={"name": "Иван"})).status_code == 401


async def test_update_profile(user_client):
    response = await user_client.patch("/users/me", json={
        "name": "Ёжик Иван", "phone": "8 (029) 123-45-67", "default_address": "Минск, ул. Тестовая, 1",
    })

    assert response.status_code == 200
    data = await me(user_client)
    assert data["name"] == "Ёжик Иван"
    assert data["phone"] == "+375291234567"
    assert data["default_address"] == "Минск, ул. Тестовая, 1"


async def test_partial_update_keeps_other_fields(user_client):
    await user_client.patch("/users/me", json={"phone": "+375291234567"})

    await user_client.patch("/users/me", json={"default_address": "Минск, ул. Новая, 5"})

    data = await me(user_client)
    assert data["phone"] == "+375291234567"           # не затёрт
    assert data["default_address"] == "Минск, ул. Новая, 5"


@pytest.mark.parametrize("empty", [None, "", "   "])
async def test_clear_phone_and_address(user_client, empty):
    await user_client.patch("/users/me", json={"phone": "+375291234567", "default_address": "Минск, ул. Тестовая, 1"})

    response = await user_client.patch("/users/me", json={"phone": empty, "default_address": empty})

    assert response.status_code == 200
    data = await me(user_client)
    assert data["phone"] is None and data["default_address"] is None


async def test_empty_body_changes_nothing(user_client):
    before = await me(user_client)

    assert (await user_client.patch("/users/me", json={})).status_code == 200
    assert await me(user_client) == before


@pytest.mark.parametrize("body", [
    {"phone": "291234567"},        # нет кода страны
    {"phone": "abc"},
    {"name": None},
    {"name": "   "},
    {"name": "Ivan123"},
    {"default_address": "abc"},    # короче 5
    {"default_address": "x" * 501},
])
async def test_invalid_values(user_client, body):
    before = await me(user_client)

    assert (await user_client.patch("/users/me", json=body)).status_code == 422
    assert await me(user_client) == before


@pytest.mark.parametrize("field, value", [
    ("role", "admin"),
    ("balance", "999999"),
    ("email", "hacker@example.com"),
    ("is_active", False),
    ("id", 1),
])
async def test_mass_assignment_rejected(user_client, field, value):
    before = await me(user_client)

    response = await user_client.patch("/users/me", json={"name": "Иван", field: value})

    assert response.status_code == 422
    assert await me(user_client) == before     # даже name не применился