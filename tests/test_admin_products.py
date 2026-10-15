"""
Запуск (внутри контейнера):
    docker compose exec web pytest tests/test_admin_products.py -v
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Product


def product_payload(category_id: int, **overrides) -> dict:
    """Минимально корректное тело для POST/PUT. Любое поле можно переопределить."""
    return {
        "category_id": category_id,
        "brand_id": None,
        "sku": "TST-001",
        "name": "Тестовый товар",
        "description": "Описание",
        "price": "99.90",
        "old_price": None,
        "stock_quantity": 10,
        "is_active": True,
        **overrides,
    }


async def count_products(db_session) -> int:
    return await db_session.scalar(select(func.count(Product.id)))


# region --- Создание --------------------------------------------------------------
async def test_create_product_success(admin_client, db_session, make_category):
    category = await make_category()

    response = await admin_client.post("/admin/products", json=product_payload(category.id))

    assert response.status_code == 201
    data = response.json()
    assert data["sku"] == "TST-001"
    assert data["name"] == "Тестовый товар"
    assert data["category_id"] == category.id
    assert data["brand_id"] is None
    assert Decimal(data["price"]) == Decimal("99.90")
    assert data["old_price"] is None
    assert data["stock_quantity"] == 10
    assert data["is_active"] is True
    assert data["image_path"] is None
    assert "created_at" in data  # служебное поле, которого нет в публичной схеме

    saved = await db_session.get(Product, data["id"])
    assert saved is not None
    assert saved.sku == "TST-001"


async def test_create_product_with_brand_and_old_price(admin_client, make_category, make_brand):
    category = await make_category()
    brand = await make_brand()

    response = await admin_client.post("/admin/products", json=product_payload(
        category.id, brand_id=brand.id, old_price="129.90",
    ))

    assert response.status_code == 201
    data = response.json()
    assert data["brand_id"] == brand.id
    assert Decimal(data["old_price"]) == Decimal("129.90")


async def test_create_product_uses_defaults(admin_client, make_category):
    """Из обязательных полей только категория, артикул, название и цена."""
    category = await make_category()

    response = await admin_client.post("/admin/products", json={
        "category_id": category.id, "sku": "MIN-1", "name": "Минимум", "price": "10.00",
    })

    assert response.status_code == 201
    data = response.json()
    assert data["stock_quantity"] == 0
    assert data["is_active"] is True
    assert data["brand_id"] is None
    assert data["description"] is None


async def test_create_product_strips_whitespace(admin_client, make_category):
    category = await make_category()

    response = await admin_client.post("/admin/products", json=product_payload(
        category.id, sku="  SPACE-1  ", name="  Товар с пробелами  ",
    ))

    assert response.status_code == 201
    assert response.json()["sku"] == "SPACE-1"
    assert response.json()["name"] == "Товар с пробелами"


async def test_create_product_duplicate_sku(admin_client, db_session, make_product):
    existing = await make_product(sku="DUP-1")

    response = await admin_client.post("/admin/products", json=product_payload(
        existing.category_id, sku="DUP-1",
    ))

    assert response.status_code == 409
    assert "артикулом" in response.json()["detail"]
    assert await count_products(db_session) == 1


async def test_create_product_unknown_category(admin_client, db_session):
    response = await admin_client.post("/admin/products", json=product_payload(999999))

    assert response.status_code == 422
    assert response.json()["detail"] == "Категория не найдена"
    assert await count_products(db_session) == 0


async def test_create_product_unknown_brand(admin_client, make_category):
    category = await make_category()

    response = await admin_client.post("/admin/products", json=product_payload(category.id, brand_id=999999))

    assert response.status_code == 422
    assert response.json()["detail"] == "Бренд не найден"


@pytest.mark.parametrize(("field", "value"), [
    ("price", "0"),                  # цена строго больше нуля
    ("price", "-5.00"),
    ("price", "99.999"),             # не больше двух знаков после запятой
    ("price", "123456789.00"),       # больше 10 цифр всего
    ("old_price", "99.90"),          # равна текущей цене: скидки нет
    ("old_price", "50.00"),          # меньше текущей цены
    ("old_price", "0"),
    ("stock_quantity", -1),
    ("name", ""),
    ("name", "   "),                 # после обрезки пробелов пусто
    ("name", "N" * 201),
    ("sku", ""),
    ("sku", "S" * 51),
])
async def test_create_product_invalid_fields(admin_client, db_session, make_category, field, value):
    category = await make_category()

    response = await admin_client.post("/admin/products", json=product_payload(category.id, **{field: value}))

    assert response.status_code == 422
    assert await count_products(db_session) == 0


async def test_create_product_old_price_error_message(admin_client, make_category):
    category = await make_category()

    response = await admin_client.post("/admin/products", json=product_payload(
        category.id, price="99.90", old_price="50.00",
    ))

    assert response.status_code == 422
    assert "Старая цена" in str(response.json()["detail"])


@pytest.mark.parametrize("missing", ["category_id", "sku", "name", "price"])
async def test_create_product_missing_required_field(admin_client, make_category, missing):
    category = await make_category()
    payload = product_payload(category.id)
    del payload[missing]

    response = await admin_client.post("/admin/products", json=payload)

    assert response.status_code == 422
# endregion


# region --- Чтение: один товар ----------------------------------------------------
async def test_get_product(admin_client, make_product):
    product = await make_product(name="Конкретный товар")

    response = await admin_client.get(f"/admin/products/{product.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == product.id
    assert data["name"] == "Конкретный товар"
    assert data["is_active"] is True


async def test_get_hidden_product_is_available_for_admin(admin_client, make_product):
    """Скрытые товары для админа остаются доступными (в отличие от публичного API)."""
    product = await make_product(is_active=False)

    response = await admin_client.get(f"/admin/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_get_product_not_found(admin_client):
    response = await admin_client.get("/admin/products/999999")

    assert response.status_code == 404
# endregion


# region --- Чтение: список --------------------------------------------------------
async def test_list_products_empty(admin_client):
    response = await admin_client.get("/admin/products")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20, "pages": 0}


async def test_list_products_includes_hidden(admin_client, make_product):
    visible = await make_product()
    hidden = await make_product(is_active=False)

    data = (await admin_client.get("/admin/products")).json()

    assert data["total"] == 2
    assert {p["id"] for p in data["items"]} == {visible.id, hidden.id}


async def test_list_products_pagination(admin_client, make_product):
    for _ in range(5):
        await make_product()

    page1 = (await admin_client.get("/admin/products", params={"page": 1, "page_size": 2})).json()
    page3 = (await admin_client.get("/admin/products", params={"page": 3, "page_size": 2})).json()

    assert page1["total"] == 5
    assert page1["pages"] == 3
    assert page1["page"] == 1
    assert page1["page_size"] == 2
    assert len(page1["items"]) == 2
    assert len(page3["items"]) == 1  # 5 = 2 + 2 + 1

    ids = [p["id"] for p in page1["items"]]
    assert ids == sorted(ids)  # порядок стабильный: по возрастанию id


async def test_list_products_page_out_of_range(admin_client, make_product):
    await make_product()

    data = (await admin_client.get("/admin/products", params={"page": 10})).json()

    assert data["items"] == []
    assert data["total"] == 1  # общее число при этом сохраняется


async def test_list_products_search_by_name_is_case_insensitive(admin_client, make_product):
    match = await make_product(name="Phone Alpha")
    await make_product(name="Laptop Beta")

    data = (await admin_client.get("/admin/products", params={"search": "ALPHA"})).json()

    assert [p["id"] for p in data["items"]] == [match.id]


async def test_list_products_search_by_sku(admin_client, make_product):
    match = await make_product(sku="PH-001", name="Первый")
    await make_product(sku="LT-001", name="Второй")

    data = (await admin_client.get("/admin/products", params={"search": "ph-0"})).json()

    assert [p["id"] for p in data["items"]] == [match.id]


async def test_list_products_search_ignores_blank(admin_client, make_product):
    await make_product()
    await make_product()

    data = (await admin_client.get("/admin/products", params={"search": "   "})).json()

    assert data["total"] == 2


async def test_list_products_filter_by_category_slug(admin_client, make_category, make_product):
    phones = await make_category(slug="phones")
    laptops = await make_category(slug="laptops")
    phone = await make_product(category=phones)
    await make_product(category=laptops)

    data = (await admin_client.get("/admin/products", params={"category": "phones"})).json()
    unknown = (await admin_client.get("/admin/products", params={"category": "no-such"})).json()

    assert [p["id"] for p in data["items"]] == [phone.id]
    assert unknown["items"] == []


async def test_list_products_filter_by_status(admin_client, make_product):
    visible = await make_product()
    hidden = await make_product(is_active=False)

    only_visible = (await admin_client.get("/admin/products", params={"is_active": "true"})).json()
    only_hidden = (await admin_client.get("/admin/products", params={"is_active": "false"})).json()

    assert [p["id"] for p in only_visible["items"]] == [visible.id]
    assert [p["id"] for p in only_hidden["items"]] == [hidden.id]


async def test_list_products_combined_filters(admin_client, make_category, make_product):
    phones = await make_category(slug="phones")
    await make_product(category=phones, name="Phone One")
    hidden = await make_product(category=phones, name="Phone Two", is_active=False)
    await make_product(name="Phone Three")  # другая категория

    data = (await admin_client.get("/admin/products", params={
        "category": "phones", "is_active": "false", "search": "phone",
    })).json()

    assert [p["id"] for p in data["items"]] == [hidden.id]


@pytest.mark.parametrize("params", [
    {"page": 0},
    {"page_size": 0},
    {"page_size": 101},
    {"search": "x" * 101},
    {"is_active": "maybe"},
], ids=["page-0", "page_size-0", "page_size-101", "search-too-long", "is_active-not-bool"])
async def test_list_products_invalid_query(admin_client, params):
    response = await admin_client.get("/admin/products", params=params)

    assert response.status_code == 422
# endregion


# region --- Обновление ------------------------------------------------------------
async def test_update_product_success(admin_client, db_session, make_product, make_category, make_brand):
    product = await make_product(name="Старое", sku="OLD-1", price=Decimal("50.00"))
    new_category = await make_category()
    brand = await make_brand()

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        new_category.id, brand_id=brand.id, sku="NEW-1", name="Новое", description=None,
        price="120.50", old_price="150.00", stock_quantity=3, is_active=False,
    ))

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == product.id
    assert data["sku"] == "NEW-1"
    assert data["name"] == "Новое"
    assert data["category_id"] == new_category.id
    assert data["brand_id"] == brand.id
    assert data["description"] is None
    assert Decimal(data["price"]) == Decimal("120.50")
    assert Decimal(data["old_price"]) == Decimal("150.00")
    assert data["stock_quantity"] == 3
    assert data["is_active"] is False

    # Проверяем, что изменения действительно записаны в БД
    await db_session.refresh(product)
    assert product.sku == "NEW-1"
    assert product.is_active is False


async def test_update_product_can_clear_brand_and_old_price(admin_client, make_product, make_brand):
    brand = await make_brand()
    product = await make_product(brand=brand, old_price=Decimal("200.00"))

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        product.category_id, sku=product.sku, brand_id=None, old_price=None,
    ))

    assert response.status_code == 200
    assert response.json()["brand_id"] is None
    assert response.json()["old_price"] is None


async def test_update_product_keeps_own_sku(admin_client, make_product):
    """Сохранение товара с его же артикулом не должно считаться дублем."""
    product = await make_product(sku="KEEP-1")

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        product.category_id, sku="KEEP-1", name="Переименован",
    ))

    assert response.status_code == 200
    assert response.json()["name"] == "Переименован"


async def test_update_product_sku_taken_by_other(admin_client, db_session, make_product):
    await make_product(sku="TAKEN")
    product = await make_product(sku="MINE")

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        product.category_id, sku="TAKEN",
    ))

    assert response.status_code == 409
    await db_session.refresh(product)
    assert product.sku == "MINE"  # ничего не изменилось


async def test_update_product_does_not_touch_image(admin_client, make_product):
    """Картинка меняется отдельными запросами, а PUT её не затрагивает."""
    product = await make_product(image_path="img/products/keep-test.webp")

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        product.category_id, sku=product.sku, name="Новое название",
    ))

    assert response.status_code == 200
    assert response.json()["image_path"] == "img/products/keep-test.webp"


async def test_update_product_not_found(admin_client):
    response = await admin_client.put("/admin/products/999999", json=product_payload(1))

    assert response.status_code == 404


async def test_update_product_unknown_category(admin_client, make_product):
    product = await make_product()

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        999999, sku=product.sku,
    ))

    assert response.status_code == 422


async def test_update_product_invalid_old_price(admin_client, make_product):
    product = await make_product()

    response = await admin_client.put(f"/admin/products/{product.id}", json=product_payload(
        product.category_id, sku=product.sku, price="100.00", old_price="100.00",
    ))

    assert response.status_code == 422
# endregion


# region --- Скрытие и показ (мягкое удаление) ---------------------------------------
async def test_hide_and_show_product(admin_client, client, make_product):
    product = await make_product()

    hide = await admin_client.patch(f"/admin/products/{product.id}/active", json={"is_active": False})
    assert hide.status_code == 200
    assert hide.json()["is_active"] is False
    # Для обычных покупателей скрытого товара больше нет
    assert (await client.get(f"/products/{product.id}")).status_code == 404

    show = await admin_client.patch(f"/admin/products/{product.id}/active", json={"is_active": True})
    assert show.status_code == 200
    assert show.json()["is_active"] is True
    assert (await client.get(f"/products/{product.id}")).status_code == 200


async def test_hide_product_does_not_change_other_fields(admin_client, make_product):
    product = await make_product(name="Не трогать", price=Decimal("77.70"), stock_quantity=9)

    data = (await admin_client.patch(f"/admin/products/{product.id}/active", json={"is_active": False})).json()

    assert data["name"] == "Не трогать"
    assert Decimal(data["price"]) == Decimal("77.70")
    assert data["stock_quantity"] == 9


async def test_set_active_not_found(admin_client):
    response = await admin_client.patch("/admin/products/999999/active", json={"is_active": False})

    assert response.status_code == 404


async def test_set_active_requires_body_field(admin_client, make_product):
    product = await make_product()

    response = await admin_client.patch(f"/admin/products/{product.id}/active", json={})

    assert response.status_code == 422
# endregion