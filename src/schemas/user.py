from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from typing import Optional


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=5, max_length=50)


class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(min_length=5, max_length=50)
    password: str = Field(min_length=8, max_length=16)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "joao@email.com",
                "username": "joaosilva",
                "password": "senha1234",
            }
        }
    )


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "joao@email.com",
                "password": "senha1234",
            }
        }
    )


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=5, max_length=50)
    password: Optional[str] = Field(None, min_length=8, max_length=16)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "novo@email.com",
                "username": "novousername",
            }
        }
    )


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
