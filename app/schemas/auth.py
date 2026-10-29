import re
from decimal import Decimal

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator, Field

from app.schemas.types import Name, Phone


class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    name: Name

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if not re.match(r"^[0-9a-zA-Z_+-]{6,20}$", v):
            raise ValueError("Пароль должен быть длиной 6-20 символов, использовать только буквы, цифры, _+- only")
        return v

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