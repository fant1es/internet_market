import math

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Product, Review, User, Category
from app.models.user import UserRole
from app.schemas.review import ReviewCreate, ReviewUpdate
from app.utils.database import commit_or_409, get_or_404, run_in_transaction


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
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Товар не найден")


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

    review = Review(**data.model_dump(), user_id=user.id, product_id=product_id)
    db.add(review)
    await commit_or_409(db, "Вы уже оставили отзыв на этот товар")
    return await _load_review(db, review.id)


async def _apply_update(db: AsyncSession, review_id: int, user: User, data: ReviewUpdate) -> None:
    review = await get_or_404(db, Review, review_id, "Отзыв не найден")
    # Редактировать чужое нельзя даже админу
    if review.user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Это не ваш отзыв")

    for field, value in data.model_dump(exclude_unset=True).items():
        # Если None в обязательных полях, не меняем данные
        if value is None and field not in ("pros", "cons"):
            continue
        setattr(review, field, value)


async def update_review(db: AsyncSession, review_id: int, user: User, data: ReviewUpdate) -> Review:
    await run_in_transaction(db, _apply_update, review_id, user, data)
    return await _load_review(db, review_id)


async def _remove(db: AsyncSession, review_id: int, user: User) -> None:
    review = await get_or_404(db, Review, review_id, "Отзыв не найден")
    if review.user_id != user.id and user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Нет прав на удаление")
    await db.delete(review)


async def delete_review(db: AsyncSession, review_id: int, user: User) -> None:
    await run_in_transaction(db, _remove, review_id, user)