from datetime import datetime
from typing import Annotated
from pydantic import BaseModel, EmailStr, StringConstraints


class UserBase(BaseModel):
    email: EmailStr
    username: str


class UserCreate(UserBase):
    password: Annotated[str, StringConstraints(min_length=6, max_length=72)]


class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

