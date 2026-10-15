import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Латиница, цифры и одиночные дефисы между ними
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class _ReferenceIn(BaseModel):
    """Общие поля бренда и категории."""
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100)

    @field_validator("slug")
    @classmethod
    def check_slug(cls, value: str) -> str:
        value = value.lower()
        if not SLUG_RE.match(value):
            raise ValueError("Slug: только латиница, цифры и дефисы, например smart-home")
        return value


class BrandIn(_ReferenceIn):
    is_active: bool = True


class CategoryIn(_ReferenceIn):
    pass


class CategoryAdminOut(BaseModel):
    id: int
    name: str
    slug: str
    products_count: int  # сколько товаров привязано: по нему решаем, можно ли удалять


class BrandAdminOut(CategoryAdminOut):
    is_active: bool