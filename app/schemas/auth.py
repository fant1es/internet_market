from pydantic import BaseModel, EmailStr, ConfigDict

# region Схемы данных, получаемых от пользователя
class RegisterSchema(BaseModel):
    email: EmailStr
    password: str
    name: str

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