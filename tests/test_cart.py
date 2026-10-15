from decimal import Decimal


def item_payload(product, quantity: int = 1) -> dict:
    """Тело для POST /cart/items."""
    return {"product_id": product.id, "quantity": quantity}


# region --- Доступ и чтение --------------------------------------------------------
async def test_cart_requires_auth(client):
    response = await client.get("/cart")

    assert response.status_code == 401


async def test_empty_cart(user_client):
    response = await user_client.get("/cart")

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert Decimal(data["total"]) == 0
    assert data["total_quantity"] == 0
# endregion


# region --- Добавление -------------------------------------------------------------
async def test_add_item_and_totals(user_client, make_product):
    """Две позиции: проверяем subtotal каждой, общую сумму и общее количество."""
    mouse = await make_product(price=Decimal("100.00"))
    keyboard = await make_product(price=Decimal("50.50"))

    await user_client.post("/cart/items", json=item_payload(mouse, 2))
    response = await user_client.post("/cart/items", json=item_payload(keyboard, 3))

    assert response.status_code == 200
    data = response.json()
    subtotals = {i["product"]["id"]: Decimal(i["subtotal"]) for i in data["items"]}
    assert subtotals == {mouse.id: Decimal("200.00"), keyboard.id: Decimal("151.50")}
    assert Decimal(data["total"]) == Decimal("351.50")
    assert data["total_quantity"] == 5


async def test_add_same_product_merges_quantity(user_client, make_product):
    """Повторное добавление не создаёт вторую позицию, а увеличивает количество."""
    product = await make_product(stock_quantity=10)

    await user_client.post("/cart/items", json=item_payload(product, 2))
    response = await user_client.post("/cart/items", json=item_payload(product, 3))

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity"] == 5


async def test_add_over_stock(user_client, make_product):
    """Лимит считается с учётом уже лежащего в корзине, при отказе корзина не меняется."""
    product = await make_product(stock_quantity=5)

    await user_client.post("/cart/items", json=item_payload(product, 3))
    response = await user_client.post("/cart/items", json=item_payload(product, 3))  # 3 + 3 > 5

    assert response.status_code == 409
    cart = (await user_client.get("/cart")).json()
    assert cart["items"][0]["quantity"] == 3


async def test_add_hidden_product(user_client, make_product):
    product = await make_product(is_active=False)

    response = await user_client.post("/cart/items", json=item_payload(product))

    assert response.status_code == 404


async def test_add_unknown_product(user_client):
    response = await user_client.post("/cart/items", json={"product_id": 999999, "quantity": 1})

    assert response.status_code == 404


async def test_add_invalid_quantity(user_client, make_product):
    product = await make_product()

    response = await user_client.post("/cart/items", json=item_payload(product, 0))

    assert response.status_code == 422
# endregion


# region --- Изменение --------------------------------------------------------------
async def test_update_quantity(user_client, make_product):
    product = await make_product(price=Decimal("100.00"), stock_quantity=10)
    item_id = (await user_client.post("/cart/items", json=item_payload(product))).json()["items"][0]["id"]

    response = await user_client.patch(f"/cart/items/{item_id}", json={"quantity": 4})

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["quantity"] == 4
    assert Decimal(data["items"][0]["subtotal"]) == Decimal("400.00")
    assert Decimal(data["total"]) == Decimal("400.00")


async def test_update_over_stock(user_client, make_product):
    product = await make_product(stock_quantity=5)
    item_id = (await user_client.post("/cart/items", json=item_payload(product, 2))).json()["items"][0]["id"]

    response = await user_client.patch(f"/cart/items/{item_id}", json={"quantity": 6})

    assert response.status_code == 409
    cart = (await user_client.get("/cart")).json()
    assert cart["items"][0]["quantity"] == 2  # ничего не изменилось
# endregion


# region --- Удаление ---------------------------------------------------------------
async def test_delete_item(user_client, make_product):
    keep = await make_product()
    remove = await make_product()
    await user_client.post("/cart/items", json=item_payload(keep))
    items = (await user_client.post("/cart/items", json=item_payload(remove))).json()["items"]
    remove_id = next(i["id"] for i in items if i["product"]["id"] == remove.id)

    response = await user_client.delete(f"/cart/items/{remove_id}")

    assert response.status_code == 200
    assert [i["product"]["id"] for i in response.json()["items"]] == [keep.id]


async def test_delete_item_twice(user_client, make_product):
    product = await make_product()
    item_id = (await user_client.post("/cart/items", json=item_payload(product))).json()["items"][0]["id"]
    await user_client.delete(f"/cart/items/{item_id}")

    response = await user_client.delete(f"/cart/items/{item_id}")

    assert response.status_code == 404
# endregion


# region --- Изоляция пользователей -------------------------------------------------
async def test_cannot_touch_foreign_cart_item(user_client, other_user_client, make_product):
    """Чужую позицию нельзя ни изменить, ни удалить (404), а у владельца она остаётся нетронутой."""
    product = await make_product(stock_quantity=10)
    item_id = (await user_client.post("/cart/items", json=item_payload(product, 2))).json()["items"][0]["id"]

    patch = await other_user_client.patch(f"/cart/items/{item_id}", json={"quantity": 5})
    delete = await other_user_client.delete(f"/cart/items/{item_id}")

    assert patch.status_code == 404
    assert delete.status_code == 404
    assert (await other_user_client.get("/cart")).json()["items"] == []  # корзины раздельные
    owner_cart = (await user_client.get("/cart")).json()
    assert owner_cart["items"][0]["quantity"] == 2
# endregion