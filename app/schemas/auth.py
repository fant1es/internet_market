from decimal import Decimal

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field

from app.schemas.types import Name, Phone, Password


class RegisterSchema(BaseModel):
    email: EmailStr
    password: Password
    name: Name

class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    balance: Decimal
    phone: str | None
    default_address: str | None
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    # forbid запрещает попытки с полями, которых нет в схеме
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    name: Name | None = None
    phone: Phone | None = None
    default_address: str | None = Field(default=None, max_length=500)

    @field_validator("phone", "default_address", mode="before")
    @classmethod
    def blank_to_none(cls, v: str):
        # При очистке поля убираем из него " " и ""
        return None if isinstance(v, str) and not v.strip() else v

    @field_validator("name")
    @classmethod
    def name_not_null(cls, v: str):
        if v is None:
            raise ValueError("Имя нельзя очистить")
        return v

    @field_validator("default_address")
    @classmethod
    def default_address_min_length(cls, v: str):
        if v is not None and len(v) < 5:
            raise ValueError("Длина адреса должна быть не короче 5 символов")
        return v