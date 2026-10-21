import asyncio
from decimal import Decimal

from sqlalchemy import func, select, update

from app.models import BalanceTransaction, Order, Product, User
from app.models.balance_transaction import TransactionType

ADDRESS = {"shipping_address": "Минск, ул. Тестовая, 1"}


# region --- Хелперы ----------------------------------------------------------------
async def add_to_cart(client, product, quantity: int = 1):
    response = await client.post("/cart/items", json={"product_id": product.id, "quantity": quantity})
    assert response.status_code == 200, response.text


async def checkout(client):
    return await client.post("/orders", json=ADDRESS)


async def place_order(client, product, quantity: int = 1) -> dict:
    """Кладёт товар в корзину и оформляет заказ. Возвращает JSON заказа."""
    await add_to_cart(client, product, quantity)
    response = await checkout(client)
    assert response.status_code == 201, response.text
    return response.json()


async def topup(client, amount: str):
    response = await client.post("/balance/topup", json={"amount": amount})
    assert response.status_code == 200, response.text


async def balance_of(client) -> Decimal:
    return Decimal((await client.get("/auth/me")).json()["balance"])


async def stock_of(db_session, product) -> int:
    # Выбираем колонку, а не объект: так значение всегда свежее, а не из кэша сессии
    return await db_session.scalar(select(Product.stock_quantity).where(Product.id == product.id))


async def count_orders(db_session) -> int:
    return await db_session.scalar(select(func.count(Order.id)))


async def transactions_of(db_session, order_id: int) -> list[tuple]:
    rows = await db_session.execute(
        select(BalanceTransaction.type, BalanceTransaction.amount)
        .where(BalanceTransaction.order_id == order_id)
    )
    return [(t, a) for t, a in rows.all()]
# endregion


# region --- Оформление: успех ------------------------------------------------------
async def test_checkout_requires_auth(client):
    response = await client.post("/orders", json=ADDRESS)

    assert response.status_code == 401


async def test_checkout_success(user_client, db_session, make_product):
    """Заказ создан, позиции снапшотятся, остаток списан, корзина пуста."""
    mouse = await make_product(price=Decimal("100.00"), stock_quantity=10)
    keyboard = await make_product(price=Decimal("50.50"), stock_quantity=10)
    await add_to_cart(user_client, mouse, 2)
    await add_to_cart(user_client, keyboard, 3)

    response = await checkout(user_client)

    assert response.status_code == 201
    order = response.json()
    assert order["status"] == "pending"
    assert order["shipping_address"] == ADDRESS["shipping_address"]
    assert Decimal(order["total_amount"]) == Decimal("351.50")
    assert {(i["product_id"], i["quantity"]) for i in order["items"]} == {(mouse.id, 2), (keyboard.id, 3)}

    assert await stock_of(db_session, mouse) == 8
    assert await stock_of(db_session, keyboard) == 7

    cart = (await user_client.get("/cart")).json()
    assert cart["items"] == []


async def test_order_keeps_price_snapshot(user_client, db_session, make_product):
    """Смена цены и названия товара после заказа не меняет сам заказ."""
    product = await make_product(name="Старое имя", price=Decimal("100.00"))
    order = await place_order(user_client, product, 2)

    await db_session.execute(
        update(Product).where(Product.id == product.id)
        .values(price=Decimal("999.00"), name="Новое имя")
    )
    await db_session.commit()

    orders = (await user_client.get("/orders")).json()
    item = orders[0]["items"][0]
    assert orders[0]["id"] == order["id"]
    assert item["product_name"] == "Старое имя"
    assert Decimal(item["product_price"]) == Decimal("100.00")
    assert Decimal(orders[0]["total_amount"]) == Decimal("200.00")
# endregion


# region --- Оформление: ошибки и откат ---------------------------------------------
async def test_checkout_empty_cart(user_client, db_session):
    response = await checkout(user_client)

    assert response.status_code == 400
    assert await count_orders(db_session) == 0


async def test_checkout_invalid_address(user_client, make_product):
    await add_to_cart(user_client, await make_product())

    response = await user_client.post("/orders", json={"shipping_address": "abc"})

    assert response.status_code == 422


async def test_checkout_hidden_product(user_client, db_session, make_product):
    """Скрытый после добавления товар блокирует заказ: 409, ничего не создано и не списано."""
    product = await make_product(stock_quantity=5)
    await add_to_cart(user_client, product, 2)
    await db_session.execute(update(Product).where(Product.id == product.id).values(is_active=False))
    await db_session.commit()

    response = await checkout(user_client)

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["code"] == "cart_unavailable"
    assert detail["items"] == [{"product_id": product.id, "name": product.name, "reason": "inactive"}]
    assert await count_orders(db_session) == 0
    assert await stock_of(db_session, product) == 5
    assert len((await user_client.get("/cart")).json()["items"]) == 1  # корзина не тронута


async def test_checkout_hidden_brand(user_client, db_session, make_product, make_brand):
    brand = await make_brand()
    product = await make_product(brand=brand)
    await add_to_cart(user_client, product)
    brand.is_active = False
    await db_session.commit()

    response = await checkout(user_client)

    assert response.status_code == 409
    assert response.json()["detail"]["items"][0]["reason"] == "inactive"


async def test_checkout_insufficient_stock(user_client, db_session, make_product):
    product = await make_product(stock_quantity=5)
    await add_to_cart(user_client, product, 4)
    await db_session.execute(update(Product).where(Product.id == product.id).values(stock_quantity=1))
    await db_session.commit()

    response = await checkout(user_client)

    assert response.status_code == 409
    problem = response.json()["detail"]["items"][0]
    assert problem["reason"] == "insufficient_stock"
    assert problem["available"] == 1


async def test_checkout_reports_all_problems(user_client, db_session, make_product):
    """Сервер отдаёт все проблемные позиции сразу, а не только первую."""
    hidden = await make_product()
    scarce = await make_product(stock_quantity=5)
    await add_to_cart(user_client, hidden)
    await add_to_cart(user_client, scarce, 3)
    await db_session.execute(update(Product).where(Product.id == hidden.id).values(is_active=False))
    await db_session.execute(update(Product).where(Product.id == scarce.id).values(stock_quantity=1))
    await db_session.commit()

    response = await checkout(user_client)

    reasons = {i["product_id"]: i["reason"] for i in response.json()["detail"]["items"]}
    assert reasons == {hidden.id: "inactive", scarce.id: "insufficient_stock"}


async def test_checkout_rolls_back_everything(user_client, db_session, make_product):
    """Одна плохая позиция откатывает весь заказ: у исправного товара остаток не меняется."""
    good = await make_product(stock_quantity=10)
    bad = await make_product(stock_quantity=5)
    await add_to_cart(user_client, good, 2)
    await add_to_cart(user_client, bad, 3)
    await db_session.execute(update(Product).where(Product.id == bad.id).values(stock_quantity=0))
    await db_session.commit()

    response = await checkout(user_client)

    assert response.status_code == 409
    assert await count_orders(db_session) == 0
    assert await stock_of(db_session, good) == 10
    assert len((await user_client.get("/cart")).json()["items"]) == 2
# endregion


# region --- Гонки ------------------------------------------------------------------
async def test_race_for_last_item(user_client, other_user_client, db_session, make_product, isolated_sessions):
    """Двое одновременно оформляют заказ на последний экземпляр: проходит ровно один."""
    product = await make_product(stock_quantity=1)
    await add_to_cart(user_client, product)
    await add_to_cart(other_user_client, product)

    first, second = await asyncio.gather(checkout(user_client), checkout(other_user_client))

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    assert await stock_of(db_session, product) == 0
    assert await count_orders(db_session) == 1


async def test_double_checkout_same_cart(user_client, db_session, make_product, isolated_sessions):
    """Двойной клик: из одной корзины получается один заказ, второй запрос видит пустую корзину."""
    product = await make_product(stock_quantity=10)
    await add_to_cart(user_client, product, 2)

    first, second = await asyncio.gather(checkout(user_client), checkout(user_client))

    assert sorted([first.status_code, second.status_code]) == [201, 400]
    assert await count_orders(db_session) == 1
    assert await stock_of(db_session, product) == 8


async def test_double_pay_charges_once(user_client, db_session, make_product, isolated_sessions):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product, 2)
    await topup(user_client, "1000")

    first, second = await asyncio.gather(
        user_client.post(f"/orders/{order['id']}/pay"),
        user_client.post(f"/orders/{order['id']}/pay"),
    )

    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert await balance_of(user_client) == Decimal("800.00")
# endregion


# region --- История заказов --------------------------------------------------------
async def test_orders_list_isolation_and_order(user_client, other_user_client, make_product):
    product = await make_product(stock_quantity=20)
    first = await place_order(user_client, product)
    second = await place_order(user_client, product)
    await place_order(other_user_client, product)

    orders = (await user_client.get("/orders")).json()

    assert [o["id"] for o in orders] == [second["id"], first["id"]]  # новые сверху, чужих нет
# endregion


# region --- Оплата -----------------------------------------------------------------
async def test_pay_success(user_client, db_session, make_product):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product, 3)
    await topup(user_client, "1000")

    response = await user_client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert await balance_of(user_client) == Decimal("700.00")
    assert await transactions_of(db_session, order["id"]) == [(TransactionType.PAYMENT, Decimal("-300.00"))]


async def test_pay_insufficient_funds(user_client, make_product):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product, 3)
    await topup(user_client, "100")

    response = await user_client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 402
    assert await balance_of(user_client) == Decimal("100.00")
    assert (await user_client.get("/orders")).json()[0]["status"] == "pending"


async def test_pay_twice(user_client, make_product):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product)
    await topup(user_client, "1000")
    await user_client.post(f"/orders/{order['id']}/pay")

    response = await user_client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 409
    assert await balance_of(user_client) == Decimal("900.00")  # списано один раз


async def test_cannot_pay_foreign_order(user_client, other_user_client, make_product):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product)
    await topup(other_user_client, "1000")

    response = await other_user_client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 404
    assert await balance_of(other_user_client) == Decimal("1000.00")
# endregion


# region --- Отмена -----------------------------------------------------------------
async def test_cancel_pending_returns_stock(user_client, db_session, make_product):
    product = await make_product(stock_quantity=10)
    order = await place_order(user_client, product, 4)
    assert await stock_of(db_session, product) == 6

    response = await user_client.post(f"/orders/{order['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await stock_of(db_session, product) == 10
    assert await transactions_of(db_session, order["id"]) == []  # денег не было, возврата нет


async def test_cancel_paid_refunds_money(user_client, db_session, make_product):
    product = await make_product(price=Decimal("100.00"), stock_quantity=10)
    order = await place_order(user_client, product, 2)
    await topup(user_client, "1000")
    await user_client.post(f"/orders/{order['id']}/pay")
    assert await balance_of(user_client) == Decimal("800.00")

    response = await user_client.post(f"/orders/{order['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert await balance_of(user_client) == Decimal("1000.00")
    assert await stock_of(db_session, product) == 10
    assert await transactions_of(db_session, order["id"]) == [
        (TransactionType.PAYMENT, Decimal("-200.00")),
        (TransactionType.REFUND, Decimal("200.00")),
    ]


async def test_cancel_twice(user_client, db_session, make_product):
    """Повторная отмена не должна вернуть остаток второй раз."""
    product = await make_product(stock_quantity=10)
    order = await place_order(user_client, product, 4)
    await user_client.post(f"/orders/{order['id']}/cancel")

    response = await user_client.post(f"/orders/{order['id']}/cancel")

    assert response.status_code == 409
    assert await stock_of(db_session, product) == 10


async def test_cannot_pay_cancelled_order(user_client, make_product):
    product = await make_product(price=Decimal("100.00"))
    order = await place_order(user_client, product)
    await topup(user_client, "1000")
    await user_client.post(f"/orders/{order['id']}/cancel")

    response = await user_client.post(f"/orders/{order['id']}/pay")

    assert response.status_code == 409


async def test_cannot_cancel_foreign_order(user_client, other_user_client, db_session, make_product):
    product = await make_product(stock_quantity=10)
    order = await place_order(user_client, product, 3)

    response = await other_user_client.post(f"/orders/{order['id']}/cancel")

    assert response.status_code == 404
    assert await stock_of(db_session, product) == 7  # остаток не вернулся
# endregion


# region --- Баланс -----------------------------------------------------------------
async def test_topup_validation(user_client):
    assert (await user_client.post("/balance/topup", json={"amount": "0"})).status_code == 422
    assert (await user_client.post("/balance/topup", json={"amount": "-5"})).status_code == 422
    assert (await user_client.post("/balance/topup", json={"amount": "100001"})).status_code == 422
    assert await balance_of(user_client) == Decimal("0.00")
# endregion