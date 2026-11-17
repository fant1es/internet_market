import argparse
import asyncio
import random
from decimal import Decimal

from sqlalchemy import select, text

import app.models  # noqa: F401 # импорт нужен, чтобы все модели попали в Base.metadata
from app.config import settings
from app.database import Base, engine, async_session
from app.models import Attribute, AttributeOption, Brand, Cart, Category, Product, ProductOption, User
from app.models.user import UserRole
from app.utils.security import hash_password

# --- Тестовые данные -------------------------------------------------------
# (название бренда, slug)
BRANDS = [
    # Смартфоны
    ("Xiaomi", "xiaomi"), ("Apple", "apple"), ("Samsung", "samsung"),
    ("Realme", "realme"), ("Nokia", "nokia"), ("Pulse", "pulse"),
    # Ноутбуки
    ("HP", "hp"), ("Acer", "acer"), ("Lenovo", "lenovo"),
    ("Asus", "asus"), ("Dell", "dell"), ("MSI", "msi"),
    # Наушники
    ("Beats", "beats"), ("Marshall", "marshall"), ("Sonic", "sonic"), ("Sony", "sony"),
    ("JBL", "jbl"), ("Razer", "razer"), ("Jabra", "jabra"), ("Sennheiser", "sennheiser"),
]

# Характеристики категорий: slug категории -> [(название, slug атрибута, [варианты])]
# Порядок в списках задаёт position и у атрибутов, и у их вариантов
# Значения характеристик у товаров в CATALOG в заданном порядке
ATTRIBUTES = {
    "smartphones": [
        ("Оперативная память", "ram", ["4 ГБ", "6 ГБ", "8 ГБ", "12 ГБ", "16 ГБ"]),
        ("Встроенная память", "storage", ["64 ГБ", "128 ГБ", "256 ГБ", "512 ГБ", "1 ТБ"]),
        ("Размер экрана", "screen-size", ['до 6.0"', '6.1–6.5"', 'от 6.6"']),
        ("Операционная система", "os", ["Android", "iOS"]),
        ("Ёмкость аккумулятора", "battery", ["до 4000 мАч", "4000–4999 мАч", "от 5000 мАч"]),
        ("Мощность зарядки", "charging", ["до 20 Вт", "21–45 Вт", "от 46 Вт"]),
        ("Технология экрана", "screen-tech", ["IPS", "OLED", "TFT", "PLS"]),
    ],
    "laptops": [
        ("Тип", "type", ["Классический", "Офисный", "Игровой", "Ультрабук", "Рабочая станция", "Нетбук"]),
        ("Диагональ экрана", "screen-size", ['до 12"', '13–14"', '15–16"', '17" и больше']),
        ("Процессор", "cpu", ["Intel Celeron", "Intel Core i3", "Intel Core i5", "Intel Core i7", "Intel Core i9",
                              "AMD Ryzen 3", "AMD Ryzen 5", "AMD Ryzen 7", "AMD Ryzen 9", "Apple M-серии"]),
        ("Оперативная память", "ram", ["4 ГБ", "8 ГБ", "16 ГБ", "32 ГБ", "64 ГБ"]),
        ("Тип оперативной памяти", "ram-type", ["DDR4", "DDR5", "LPDDR4X", "LPDDR5"]),
        ("Видеокарта", "gpu", ["Интегрированная", "NVIDIA GeForce GTX", "NVIDIA GeForce RTX", "AMD Radeon"]),
        ("Тип накопителя", "storage-type", ["SSD", "HDD", "SSD + HDD", "eMMC"]),
        ("Встроенная операционная система", "os",
         ["Windows 11 Home", "Windows 11 Pro", "macOS", "Linux", "ChromeOS", "Без ОС"]),
    ],
    "headphones": [
        ("Конструкция", "design", ["Внутриканальные", "Вставные", "Мониторные", "Накладные", "Каффы"]),
        # Одно значение на товар: у универсальных наушников выбираем основное назначение
        ("Назначение", "purpose", ["Портативные", "Геймерские", "Для общения", "Профессиональные", "Спортивные"]),
        ("Подключение", "connection", ["Беспроводные", "Проводные"]),
    ],
}

# (название категории, slug, префикс sku, [(название товара, цена, slug бренда или None, старая цена или None,
# (значения характеристик в порядке ATTRIBUTES[slug])), ...])
CATALOG = [
    (
        "Смартфоны", "smartphones", "PH",
        [
            # Порядок: ОЗУ, встроенная память, экран, ОС, аккумулятор, зарядка, технология экрана
            ("Смартфон Xiaomi X1", "29990.00", "xiaomi", "34990.00",
             ("8 ГБ", "256 ГБ", 'от 6.6"', "Android", "от 5000 мАч", "от 46 Вт", "OLED")),
            ("Смартфон IPhone 17 Pro", "39990.00", "apple", None,
             ("8 ГБ", "256 ГБ", '6.1–6.5"', "iOS", "4000–4999 мАч", "21–45 Вт", "OLED")),
            ("Смартфон Samsung Galaxy 5", "19990.00", "samsung", "24990.00",
             ("6 ГБ", "128 ГБ", '6.1–6.5"', "Android", "от 5000 мАч", "21–45 Вт", "PLS")),
            ("Смартфон Realme C30 S", "14990.00", "realme", None,
             ("4 ГБ", "64 ГБ", '6.1–6.5"', "Android", "от 5000 мАч", "до 20 Вт", "IPS")),
            ("Смартфон Nokia 3310", "24990.00", "nokia", None,
             ("4 ГБ", "128 ГБ", 'до 6.0"', "Android", "до 4000 мАч", "до 20 Вт", "TFT")),
            ("Смартфон IPhone Duo", "54990.00", "apple", None,
             ("12 ГБ", "512 ГБ", 'от 6.6"', "iOS", "4000–4999 мАч", "21–45 Вт", "OLED")),
            ("Смартфон Pulse A2", "9990.00", "pulse", None,
             ("4 ГБ", "64 ГБ", '6.1–6.5"', "Android", "от 5000 мАч", "до 20 Вт", "TFT")),
            ("Смартфон Samsung Galaxy S Ultra", "69990.00", "samsung", "79990.00",
             ("12 ГБ", "1 ТБ", 'от 6.6"', "Android", "от 5000 мАч", "21–45 Вт", "OLED")),
            ("Смартфон Xiaomi Redmi Note 14", "17990.00", "xiaomi", None,
             ("8 ГБ", "256 ГБ", 'от 6.6"', "Android", "от 5000 мАч", "21–45 Вт", "OLED")),
            ("Смартфон Realme GT Neo", "32990.00", "realme", "37990.00",
             ("16 ГБ", "256 ГБ", 'от 6.6"', "Android", "от 5000 мАч", "от 46 Вт", "OLED")),
            ("Смартфон IPhone 16e", "34990.00", "apple", None,
             ("8 ГБ", "128 ГБ", '6.1–6.5"', "iOS", "до 4000 мАч", "до 20 Вт", "OLED")),
            ("Смартфон Samsung Galaxy A Lite", "11990.00", "samsung", "13990.00",
             ("4 ГБ", "128 ГБ", '6.1–6.5"', "Android", "от 5000 мАч", "до 20 Вт", "PLS")),
            ("Смартфон Nokia G Pro", "13990.00", "nokia", None,
             ("6 ГБ", "128 ГБ", '6.1–6.5"', "Android", "от 5000 мАч", "до 20 Вт", "IPS")),
            ("Смартфон Pulse X Max", "21990.00", "pulse", None,
             ("8 ГБ", "256 ГБ", 'от 6.6"', "Android", "от 5000 мАч", "21–45 Вт", "OLED")),
            ("Смартфон Xiaomi Mini", "15990.00", "xiaomi", None,
             ("6 ГБ", "128 ГБ", 'до 6.0"', "Android", "4000–4999 мАч", "21–45 Вт", "IPS")),
        ],
    ),
    (
        "Ноутбуки", "laptops", "LT",
        [
            # Порядок: тип, диагональ, процессор, ОЗУ, тип ОЗУ, видеокарта, накопитель, ОС
            ("Ноутбук HP Omnibook 7", "69990.00", "hp", None,
             ("Ультрабук", '13–14"', "Intel Core i7", "16 ГБ", "LPDDR5", "Интегрированная", "SSD", "Windows 11 Home")),
            ("Ноутбук Acer Aspire 17", "89990.00", "acer", None,
             ("Классический", '17" и больше', "AMD Ryzen 7", "16 ГБ", "DDR4", "NVIDIA GeForce GTX", "SSD",
              "Windows 11 Home")),
            ("Ноутбук MacBook Pro 13", "129990.00", "apple", None,
             ("Рабочая станция", '13–14"', "Apple M-серии", "16 ГБ", "LPDDR5", "Интегрированная", "SSD", "macOS")),
            ("Ноутбук Xiaomi G15", "39990.00", "xiaomi", "44990.00",
             ("Игровой", '15–16"', "AMD Ryzen 5", "8 ГБ", "DDR4", "NVIDIA GeForce GTX", "SSD", "Windows 11 Home")),
            ("Ноутбук HP Gaming TUF", "99990.00", "hp", None,
             ("Игровой", '15–16"', "Intel Core i7", "16 ГБ", "DDR5", "NVIDIA GeForce RTX", "SSD", "Windows 11 Home")),
            ("Ноутбук MacBook Slim Air", "59990.00", "apple", None,
             ("Ультрабук", '13–14"', "Apple M-серии", "8 ГБ", "LPDDR4X", "Интегрированная", "SSD", "macOS")),
            ("Ноутбук Acer Swift Go 14", "54990.00", "acer", "62990.00",
             ("Ультрабук", '13–14"', "Intel Core i5", "16 ГБ", "LPDDR5", "Интегрированная", "SSD", "Windows 11 Home")),
            ("Ноутбук Lenovo ThinkPad P1", "139990.00", "lenovo", None,
             ("Рабочая станция", '15–16"', "Intel Core i9", "64 ГБ", "DDR5", "NVIDIA GeForce RTX", "SSD",
              "Windows 11 Pro")),
            ("Ноутбук Asus ROG Strix 17", "149990.00", "asus", "169990.00",
             ("Игровой", '17" и больше', "AMD Ryzen 9", "32 ГБ", "DDR5", "NVIDIA GeForce RTX", "SSD",
              "Windows 11 Home")),
            ("Ноутбук Lenovo IdeaPad 3", "34990.00", "lenovo", None,
             ("Офисный", '15–16"', "AMD Ryzen 3", "8 ГБ", "DDR4", "Интегрированная", "HDD", "Без ОС")),
            ("Ноутбук Dell Latitude 14", "79990.00", "dell", None,
             ("Офисный", '13–14"', "Intel Core i7", "16 ГБ", "DDR4", "Интегрированная", "SSD", "Windows 11 Pro")),
            ("Ноутбук Acer Chromebook 11", "17990.00", "acer", "21990.00",
             ("Нетбук", 'до 12"', "Intel Celeron", "4 ГБ", "LPDDR4X", "Интегрированная", "eMMC", "ChromeOS")),
            ("Ноутбук HP Pavilion 15", "44990.00", "hp", None,
             ("Классический", '15–16"', "Intel Core i3", "8 ГБ", "DDR4", "Интегрированная", "SSD + HDD",
              "Windows 11 Home")),
            ("Ноутбук Dell Inspiron 16", "49990.00", "dell", "54990.00",
             ("Классический", '15–16"', "AMD Ryzen 5", "16 ГБ", "DDR5", "AMD Radeon", "SSD", "Linux")),
            ("Ноутбук MSI Katana 15", "84990.00", "msi", None,
             ("Игровой", '15–16"', "Intel Core i7", "16 ГБ", "DDR5", "NVIDIA GeForce RTX", "SSD", "Без ОС")),
        ],
    ),
    (
        "Наушники", "headphones", "HP",
        [
            # Порядок: конструкция, назначение, подключение
            ("Наушники Beats Wireless", "4990.00", "beats", "5990.00",
             ("Накладные", "Портативные", "Беспроводные")),
            ("Наушники Marshall Major IV", "8990.00", "marshall", None,
             ("Накладные", "Портативные", "Беспроводные")),
            ("Наушники IPods", "12990.00", "apple", None,
             ("Вставные", "Портативные", "Беспроводные")),
            ("Наушники Sport Buds", "2990.00", "sonic", None,
             ("Внутриканальные", "Спортивные", "Беспроводные")),
            ("Наушники Silence ANC", "15990.00", "sonic", None,
             ("Мониторные", "Портативные", "Беспроводные")),
            ("Наушники Basic In-Ear", "990.00", "sonic", None,
             ("Внутриканальные", "Портативные", "Проводные")),
            ("Наушники Sony LinkBuds", "11990.00", "sony", "14990.00",
             ("Вставные", "Портативные", "Беспроводные")),
            ("Наушники JBL Quantum 400", "7990.00", "jbl", "9990.00",
             ("Мониторные", "Геймерские", "Проводные")),
            ("Наушники Razer Barracuda", "14990.00", "razer", None,
             ("Мониторные", "Геймерские", "Беспроводные")),
            ("Наушники Jabra Evolve2 65", "12990.00", "jabra", None,
             ("Накладные", "Для общения", "Беспроводные")),
            ("Наушники Sennheiser HD 560", "17990.00", "sennheiser", None,
             ("Мониторные", "Профессиональные", "Проводные")),
            ("Наушники Cuff Air", "5990.00", "sonic", "7490.00",
             ("Каффы", "Спортивные", "Беспроводные")),
        ],
    ),
]


# Демо-пользователи для разработки и итогового показа (имя, email, пароль).
# Пароли должны проходить валидацию входа: 6-20 символов, буквы, цифры, _ + -
# Администратор сюда не входит: его данные берутся из .env (ADMIN_EMAIL, ADMIN_PASSWORD)
DEMO_USERS = [
    ("Иван Петров", "ivan@example.com", "Demo_pass1"),
    ("Анна Смирнова", "anna@example.com", "Demo_pass2"),
    ("Олег Иванов", "oleg@example.com", "Demo_pass3"),
]


def _validate_catalog() -> None:
    """Ловит опечатки в тестовых данных до обращения к БД"""
    brand_slugs = {slug for _, slug in BRANDS}
    errors: list[str] = []

    for _, cat_slug, _, products in CATALOG:
        attrs = ATTRIBUTES.get(cat_slug)
        if attrs is None:
            errors.append(f"{cat_slug}: нет описания характеристик в ATTRIBUTES")
            continue

        for name, price, brand_slug, old_price, specs in products:
            if brand_slug is not None and brand_slug not in brand_slugs:
                errors.append(f"{name}: неизвестный бренд '{brand_slug}'")
            if old_price is not None and Decimal(old_price) <= Decimal(price):
                errors.append(f"{name}: старая цена должна быть больше текущей")
            if len(specs) != len(attrs):
                errors.append(f"{name}: ожидалось {len(attrs)} значений характеристик, передано {len(specs)}")
                continue
            for (attr_name, _, options), value in zip(attrs, specs):
                if value not in options:
                    errors.append(f"{name}: значения '{value}' нет среди вариантов атрибута '{attr_name}'")

    if errors:
        raise ValueError("Ошибки в тестовых данных:\n  " + "\n  ".join(errors))


def _make_product_data(index: int, name: str, price: str, brand_id: int | None, old_price: str | None) -> dict:
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
        "old_price": Decimal(old_price) if old_price else None,
        "brand_id": brand_id,
        "stock_quantity": stock,
        "is_active": is_active,
    }


# --- Команды ---------------------------------------------------------------
async def _ensure_user(session, name: str, email: str, password: str, role: UserRole) -> str:
    """Создаёт пользователя вместе с пустой корзиной (как это делает регистрация).
    Возвращает 'created', 'promoted' или 'exists'.
    """
    user = await session.scalar(select(User).where(User.email == email))

    if user is not None:
        # Аккаунт с таким email уже есть: для админа просто повышаем роль, пароль не трогаем
        if role == UserRole.ADMIN and user.role != UserRole.ADMIN:
            user.role = UserRole.ADMIN
            return "promoted"
        return "exists"

    user = User(name=name, email=email, password_hash=hash_password(password), role=role)
    session.add(user)
    await session.flush()  # Получаем user.id
    session.add(Cart(user_id=user.id))
    return "created"


async def _seed_users(session) -> dict[str, int]:
    """Создаёт администратора из .env и демо-пользователей."""
    stats = {"created": 0, "promoted": 0, "exists": 0}

    if settings.admin_email and settings.admin_password:
        result = await _ensure_user(
            session, settings.admin_name, settings.admin_email.strip(),
            settings.admin_password, UserRole.ADMIN,
        )
        stats[result] += 1
    else:
        print("ADMIN_EMAIL / ADMIN_PASSWORD не заданы в .env — администратор не создан")

    for name, email, password in DEMO_USERS:
        stats[await _ensure_user(session, name, email, password, UserRole.USER)] += 1

    return stats


async def _seed_attributes(session, category_id: int, cat_slug: str) -> tuple[list, int, int]:
    """Создаёт (если их ещё нет) атрибуты и варианты категории.
    Возвращает ([(id атрибута, {значение: id варианта}), ...] в порядке ATTRIBUTES, создано атрибутов, создано вариантов).
    Уже существующие записи не трогаем: их мог поправить администратор.
    """
    lookup = []
    new_attributes = 0
    new_options = 0

    for attr_position, (attr_name, attr_slug, options) in enumerate(ATTRIBUTES[cat_slug]):
        attribute = await session.scalar(
            select(Attribute).where(Attribute.category_id == category_id, Attribute.slug == attr_slug)
        )
        if attribute is None:
            attribute = Attribute(category_id=category_id, name=attr_name, slug=attr_slug, position=attr_position)
            session.add(attribute)
            await session.flush()  # Получаем attribute.id
            new_attributes += 1

        option_ids: dict[str, int] = {}
        for opt_position, value in enumerate(options):
            option = await session.scalar(
                select(AttributeOption).where(
                    AttributeOption.attribute_id == attribute.id, AttributeOption.value == value
                )
            )
            if option is None:
                option = AttributeOption(attribute_id=attribute.id, value=value, position=opt_position)
                session.add(option)
                await session.flush()  # Получаем option.id
                new_options += 1
            option_ids[value] = option.id

        lookup.append((attribute.id, option_ids))

    return lookup, new_attributes, new_options


async def seed() -> None:
    """Генерирует бренды, категории, характеристики, товары и пользователей для базы данных"""
    # Сначала проверяем данные: опечатка в характеристике не должна всплыть посреди записи в БД
    _validate_catalog()

    # Определенный сид для отладки
    random.seed(42)

    created_brands = 0
    created_categories = 0
    created_attributes = 0
    created_options = 0
    created_products = 0
    skipped_products = 0
    counter = 0  # Общий счетчик для _make_product_data

    async with async_session() as session:
        # Сначала бренды, т.к нужны их id для товаров
        brand_ids: dict[str, int] = {}

        for brand_name, brand_slug in BRANDS:
            brand = await session.scalar(select(Brand).where(Brand.slug == brand_slug))
            if brand is None:
                brand = Brand(name=brand_name, slug=brand_slug)
                session.add(brand)
                await session.flush()  # Получаем brand.id
                created_brands += 1
            brand_ids[brand_slug] = brand.id

        for cat_name, slug, sku_prefix, products in CATALOG:
            category = await session.scalar(select(Category).where(Category.slug == slug))

            # Создание новой категории
            if category is None:
                category = Category(name=cat_name, slug=slug)
                session.add(category)
                await session.flush()  # Получаем category.id
                created_categories += 1

            # Характеристики категории нужны до товаров, чтобы привязывать к ним варианты
            attr_lookup, new_attrs, new_opts = await _seed_attributes(session, category.id, slug)
            created_attributes += new_attrs
            created_options += new_opts

            # Обработка всех товаров одной категории
            for i, (name, price, brand_slug, old_price, specs) in enumerate(products, start=1):
                counter += 1
                # Префикс + число в 3 цифры (если 4-значное то больше)
                sku = f"{sku_prefix}-{i:03d}"

                exists = await session.scalar(select(Product.id).where(Product.sku == sku))
                if exists:
                    skipped_products += 1
                    continue

                brand_id = brand_ids.get(brand_slug) if brand_slug else None
                data = _make_product_data(counter, name, price, brand_id, old_price)
                product = Product(sku=sku, category_id=category.id, **data)
                session.add(product)
                await session.flush()  # Получаем product.id для характеристик

                # По одному варианту на атрибут: значения идут в порядке ATTRIBUTES[slug]
                session.add_all(
                    ProductOption(product_id=product.id, attribute_id=attribute_id, option_id=option_ids[value])
                    for (attribute_id, option_ids), value in zip(attr_lookup, specs)
                )
                created_products += 1

        # В конце отдельной функцией пользователи
        user_stats = await _seed_users(session)

        await session.commit()

    print(f"Готово: брендов создано — {created_brands}, категорий создано — {created_categories}, "
          f"товаров создано — {created_products}, пропущено (уже есть) — {skipped_products}")
    print(f"Характеристики: атрибутов создано — {created_attributes}, вариантов создано — {created_options}")
    print(f"Пользователи: создано — {user_stats['created']}, повышено до админа — {user_stats['promoted']}, "
          f"уже были — {user_stats['exists']}")


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