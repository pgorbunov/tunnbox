from pydantic import BaseModel, field_validator
from datetime import datetime


class UserCreate(BaseModel):
    username: str
    password: str


class User(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: datetime


class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        return v


class TokenData(BaseModel):
    username: str | None = None
    user_id: int | None = None
