from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models import User
from app.schemas.review import ReviewCreate, ReviewListOut, ReviewOut, ReviewUpdate, CanReviewOut
from app.services import review_service

product_reviews_router = APIRouter(prefix="/products/{product_id}/reviews", tags=["reviews"])
review_router = APIRouter(prefix="/reviews", tags=["reviews"])


@product_reviews_router.get("", response_model=ReviewListOut, summary="Отзывы на товар")
async def list_reviews(product_id: int, page: int = Query(1, ge=1),
                       page_size: int = Query(10, ge=1, le=50),
                       db: AsyncSession = Depends(get_db)):
    return await review_service.list_reviews(db, product_id, page, page_size)


@product_reviews_router.post("", response_model=ReviewOut,
                             status_code=status.HTTP_201_CREATED,summary="Оставить отзыв")
async def create_review(product_id: int, data: ReviewCreate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    return await review_service.create_review(db, product_id, user, data)


@product_reviews_router.get("/can-review", response_model=CanReviewOut,
                            summary="Может ли текущий пользователь оставить отзыв")
async def can_review(product_id: int, db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return await review_service.can_review(db, product_id, user)


@review_router.patch("/{review_id}", response_model=ReviewOut, summary="Изменить свой отзыв")
async def update_review(review_id: int, data: ReviewUpdate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    return await review_service.update_review(db, review_id, user, data)


@review_router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT,
                      summary="Удалить отзыв (автор или админ)")
async def delete_review(review_id: int, db: AsyncSession = Depends(get_db),
                        user: User = Depends(get_current_user)):
    await review_service.delete_review(db, review_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)