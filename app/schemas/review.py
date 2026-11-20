from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

# Decimal в JSON по умолчанию уходит строкой, а фронтенду удобнее передать число
Rating = Annotated[
    Decimal,
    Field(ge=1, le=5, max_digits=2, decimal_places=1),
    PlainSerializer(float, return_type=float, when_used="json"),
]


class _ReviewTextNormalized(BaseModel):
    """Общая нормализация текстовых полей."""

    @field_validator("title", "body", "pros", "cons", mode="before", check_fields=False)
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v


class ReviewCreate(_ReviewTextNormalized):
    rating: Rating
    title: str = Field(min_length=3, max_length=150)
    body: str = Field(min_length=10, max_length=5000)
    pros: str | None = Field(default=None, max_length=2000)
    cons: str | None = Field(default=None, max_length=2000)


class ReviewUpdate(_ReviewTextNormalized):
    rating: Rating | None = None
    title: str | None = Field(default=None, min_length=3, max_length=150)
    body: str | None = Field(default=None, min_length=10, max_length=5000)
    pros: str | None = Field(default=None, max_length=2000)
    cons: str | None = Field(default=None, max_length=2000)


class ReviewAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    rating: Rating
    title: str
    body: str
    pros: str | None
    cons: str | None
    created_at: datetime
    updated_at: datetime
    user: ReviewAuthor


class ReviewSummary(BaseModel):
    average: float | None   # None, если отзывов ещё нет
    count: int


class ReviewListOut(BaseModel):
    items: list[ReviewOut]
    total: int
    summary: ReviewSummary