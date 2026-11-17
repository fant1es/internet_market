from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str


class FilterOptionOut(BaseModel):
    id: int
    value: str


class FilterAttributeOut(BaseModel):
    id: int
    name: str
    slug: str
    options: list[FilterOptionOut]