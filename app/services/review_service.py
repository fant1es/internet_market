import math

from loguru import logger
from sqlalchemy import func, select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Product, Review, User, Category, OrderItem, Order
from app.models.order import OrderStatus
from app.models.user import UserRole
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.utils.database import commit_or_409, get_or_404, run_in_transaction
from app.utils.errors import AppError

audit = logger.bind(channel="audit")


# Покупкой считается оплаченный и выполненный
PURCHASED_STATUSES = (OrderStatus.PAID, OrderStatus.COMPLETED)


# noinspection PyTypeChecker
async def _has_purchased(db: AsyncSession, user_id: int, product_id: int) -> bool:
    return await db.scalar(
        select(
            exists().where(
                Order.user_id == user_id,
                Order.status.in_(PURCHASED_STATUSES),
                OrderItem.order_id == Order.id,
                OrderItem.product_id == product_id,
            )
        )
    )


async def _ensure_purchased(db: AsyncSession, user_id: int, product_id: int) -> None:
    """Отзыв можно оставить только на товар из оплаченного заказа."""
    if not await _has_purchased(db, user_id, product_id):
        logger.warning("Отзыв отклонён | причина=нет покупки user_id={} product_id={}", user_id, product_id)
        raise AppError(403, "review_buyers_only")


# noinspection PyTypeChecker
async def can_review(db: AsyncSession, product_id: int, user: User) -> dict:
    await _ensure_active_product(db, product_id)

    already = await db.scalar(
        select(exists().where(Review.user_id == user.id, Review.product_id == product_id))
    )
    if already:
        return {"can_review": False, "reason": "already_reviewed"}
    if not await _has_purchased(db, user.id, product_id):
        return {"can_review": False, "reason": "not_purchased"}

    return {"can_review": True, "reason": None}


# noinspection PyTypeChecker
async def _ensure_active_product(db: AsyncSession, product_id: int) -> None:
    found = await db.scalar(
        select(Product.id)
        .join(Category, Product.category_id == Category.id)
        .where(
            Product.id == product_id,
            Product.is_active.is_(True),
            Category.is_active.is_(True),
        )
    )
    if found is None:
        raise AppError(404, "product_not_found")


async def _load_review(db: AsyncSession, review_id: int) -> Review | None:
    """Свежий отзыв вместе с автором и created_at, updated_at"""
    return await db.scalar(
        select(Review)
        .options(selectinload(Review.user))
        .where(Review.id == review_id)
        .execution_options(populate_existing=True)
    )


async def list_reviews(db: AsyncSession, product_id: int, page: int, page_size: int) -> dict:
    await _ensure_active_product(db, product_id)

    total, avg = (
        await db.execute(
            select(func.count(Review.id), func.avg(Review.rating))
            .where(Review.product_id == product_id)
        )
    ).one()

    items = (
        await db.scalars(
            select(Review)
            .options(selectinload(Review.user))
            .where(Review.product_id == product_id)
            .order_by(Review.created_at.desc(), Review.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size),
        "summary": {
            "average": round(float(avg), 1) if avg is not None else None,
            "count": total,
        },
    }


async def create_review(db: AsyncSession, product_id: int, user: User, data: ReviewCreate) -> Review:
    await _ensure_active_product(db, product_id)
    await _ensure_purchased(db, user.id, product_id)

    review = Review(**data.model_dump(), user_id=user.id, product_id=product_id)
    db.add(review)
    await commit_or_409(db, "review_exists")
    loaded = await _load_review(db, review.id)
    logger.info("Отзыв создан | review_id={} product_id={} user_id={} оценка={}",
                loaded.id, loaded.product_id, loaded.user_id, loaded.rating)
    return loaded


async def _apply_update(db: AsyncSession, review_id: int, user: User, data: ReviewUpdate) -> None:
    review = await get_or_404(db, Review, review_id, "review_not_found")
    # Редактировать чужое нельзя даже админу
    if review.user_id != user.id:
        logger.warning("Правка отзыва отклонена | причина=чужой отзыв review_id={} user_id={}",
                       review_id, user.id)
        raise AppError(403, "review_not_yours")

    for field, value in data.model_dump(exclude_unset=True).items():
        # Если None в обязательных полях, не меняем данные
        if value is None and field not in ("pros", "cons"):
            continue
        setattr(review, field, value)


async def update_review(db: AsyncSession, review_id: int, user: User, data: ReviewUpdate) -> Review:
    await run_in_transaction(db, _apply_update, review_id, user, data)
    return await _load_review(db, review_id)


async def _remove(db: AsyncSession, review_id: int, user: User) -> int:
    review = await get_or_404(db, Review, review_id, "review_not_found")
    if review.user_id != user.id and user.role != UserRole.ADMIN:
        logger.warning("Удаление отзыва отклонено | причина=нет прав review_id={} user_id={}",
                       review_id, user.id)
        raise AppError(403, "review_delete_forbidden")
    author_id = review.user_id  # запоминаем до удаления: нужен для лога
    await db.delete(review)
    return author_id


async def delete_review(db: AsyncSession, review_id: int, user: User) -> None:
    user_id = user.id  # до commit
    author_id = await run_in_transaction(db, _remove, review_id, user)
    if author_id != user_id:
        audit.info("Отзыв удалён администратором | review_id={} admin_id={} author_id={}",
                   review_id, user_id, author_id)
    else:
        logger.info("Отзыв удалён автором | review_id={} user_id={}", review_id, user_id)