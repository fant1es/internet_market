from pydantic import BaseModel, ConfigDict, Field


class AttributeIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class OptionIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    value: str = Field(min_length=1, max_length=100)


class OptionAdminOut(BaseModel):
    id: int
    value: str
    products_count: int  # у скольких товаров выбран этот вариант


class AttributeOut(BaseModel):
    id: int
    name: str
    slug: str
    products_count: int  # у скольких товаров задана эта характеристика


class ProductAttributeOut(BaseModel):
    name: str
    value: str


class AttributeAdminOut(AttributeOut):
    options: list[OptionAdminOut]