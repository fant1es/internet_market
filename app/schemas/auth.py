import re
from decimal import Decimal

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from app.schemas.types import Name


# region Схемы данных, получаемых от пользователя
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

# endregion

# region Схемы данных, отдаваемых пользователю
class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    balance: Decimal
    model_config = ConfigDict(from_attributes=True)
# endregion