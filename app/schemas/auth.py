import re

from pydantic import BaseModel, EmailStr, ConfigDict, field_validator


# region Схемы данных, получаемых от пользователя
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    name: str

    @field_validator("password")
    @classmethod
    def validate_password_length(cls, v: str) -> str:
        if not re.match(r"^[0-9a-zA-Z_+-]{6,20}$", v):
            raise ValueError("Пароль должен быть длиной 6-20 символов, использовать только буквы, цифры, _+- only")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[а-яА-Яa-zA-Z- ]+$", v):
            raise ValueError("Name must be letters/space only")
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
    model_config = ConfigDict(from_attributes=True)
# endregion