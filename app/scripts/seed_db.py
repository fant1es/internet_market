import argparse
import asyncio
import random
from decimal import Decimal

from sqlalchemy import select, text

import app.models  # noqa: F401 # импорт нужен, чтобы все модели попали в Base.metadata
from app.database import Base, engine, async_session
from app.models import Category, Product

# --- Тестовые данные -------------------------------------------------------
CATALOG = [
    (
        "Смартфоны", "smartphones", "PH",
        [
            ("Смартфон Xiaomi X1", "29990.00"),
            ("Смартфон IPhone 17 Pro", "39990.00"),
            ("Смартфон Samsung Galaxy 5", "19990.00"),
            ("Смартфон Realme C30 S", "14990.00"),
            ("Смартфон Nokia 3310", "24990.00"),
            ("Смартфон IPhone Duo", "54990.00"),
            ("Смартфон Pulse A2", "9990.00"),
        ],
    ),
    (
        "Ноутбуки", "laptops", "LT",
        [
            ("Ноутбук HP Omnibook 7", "69990.00"),
            ("Ноутбук Acer Aspire 17", "89990.00"),
            ("Ноутбук MacBook Pro 13", "129990.00"),
            ("Ноутбук Xiaomi G15", "39990.00"),
            ("Ноутбук HP Gaming TUF", "99990.00"),
            ("Ноутбук MacBook Slim Air", "59990.00"),
        ],
    ),
    (
        "Наушники", "headphones", "HP",
        [
            ("Наушники Beats Wireless", "4990.00"),
            ("Наушники Marshall Major IV", "8990.00"),
            ("Наушники IPods", "12990.00"),
            ("Наушники Sport Buds", "2990.00"),
            ("Наушники Silence ANC", "15990.00"),
            ("Наушники Basic In-Ear", "990.00"),
        ],
    ),
    (
        "Аксессуары", "accessories", "AC",
        [
            ("Зарядное устройство 65 Вт", "1990.00"),
            ("Кабель USB-C 1 м", "490.00"),
            ("Чехол для смартфона", "790.00"),
            ("Powerbank 20000 мАч", "2490.00"),
            ("Подставка для ноутбука", "1590.00"),
            ("Беспроводная мышь", "1290.00"),
        ],
    ),
    (
        "Умный дом", "smart-home", "SH",
        [
            ("Датчик движения", "1190.00"),
            ("Камера видеонаблюдения", "3990.00"),
            ("Умная колонка Яндекс Станция", "5990.00"),
            ("Робот-пылесос Xiaomi Boot Clean", "19990.00"),
        ],
    ),
]


def _make_product_data(index: int, name: str, price: str) -> dict:
    """Вспомогательная команда, собирает поля товара. Часть товаров намеренно делаем с особыми условиями."""
    stock = random.randint(1, 50)
    is_active = True

    # Каждый 9-й товар — закончился на складе
    if index % 9 == 0:
        stock = 0
    # Каждый 13-й товар — скрыт
    if index % 13 == 0:
        is_active = False

    return {
        "name": name,
        "description": f"{name} (Проверка описания)",
        "price": Decimal(price),
        "stock_quantity": stock,
        "is_active": is_active,
    }


# --- Команды ---------------------------------------------------------------
async def seed() -> None:
    """Генерирует товары для базы данных"""
    # Определенный сид для отладки
    random.seed(42)

    created_categories = 0
    created_products = 0
    skipped_products = 0
    counter = 0 # Общий счетчик для _make_product_data

    async with async_session() as session:
        for cat_name, slug, sku_prefix, products in CATALOG:
            category = await session.scalar(select(Category).where(Category.slug == slug))

            # Создание новой категории
            if category is None:
                category = Category(name=cat_name, slug=slug)
                session.add(category)
                await session.flush() # Получаем category.id
                created_categories += 1

            # Обработка всех товаров одной категории
            for i, (name, price) in enumerate(products, start=1):
                counter += 1
                # Префикс + число в 3 цифры (если 4-значное то больше)
                sku = f"{sku_prefix}-{i:03d}"

                exists = await session.scalar(select(Product.id).where(Product.sku == sku))
                if exists:
                    skipped_products += 1
                    continue

                data = _make_product_data(counter, name, price)
                session.add(Product(sku=sku, category_id=category.id, **data))
                created_products += 1

        await session.commit()

    print(
        f"Готово: категорий создано — {created_categories}, "
        f"товаров создано — {created_products}, пропущено (уже есть) — {skipped_products}"
    )


async def clear(keep_users: bool = False) -> None:
    """TRUNCATE всех таблиц приложения со сбросом счётчиков id. Миграции alembic не затрагиваются."""
    keep = {"users", "carts"} if keep_users else set()
    tables = [t.name for t in Base.metadata.sorted_tables if t.name not in keep]
    if not tables:
        print("Нечего очищать.")
        return

    table_names = ", ".join(f'"{t}"' for t in tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))

    print(f"Очищено таблиц: {len(tables)} ({', '.join(tables)})")
    if keep_users:
        print("users и carts сохранены.")


def _confirm(message: str) -> bool:
    return input(f"{message} [y/N]: ").strip().lower() in {"y", "yes", "д", "да"}


async def main() -> None:
    parser = argparse.ArgumentParser(description="Наполнение и очистка БД")
    parser.add_argument("command", choices=["seed", "clear", "reset"])
    parser.add_argument("--keep-users", action="store_true", help="не трогать users и carts (для clear)")
    parser.add_argument("-y", "--yes", action="store_true", help="не спрашивать подтверждение")
    args = parser.parse_args()

    try:
        if args.command == "seed":
            await seed()

        elif args.command == "clear":
            if args.yes or _confirm("Удалить ВСЕ данные из таблиц?"):
                await clear(keep_users=args.keep_users)
            else:
                print("Отменено.")

        elif args.command == "reset":
            if args.yes or _confirm("Очистить каталог и заказы (users/carts сохранятся) и заполнить заново?"):
                await clear(keep_users=True)
                await seed()
            else:
                print("Отменено.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())