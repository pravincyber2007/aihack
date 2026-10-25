from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.user import UserRole, UserStatus


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class Registration(Credentials):
    role: UserRole


class LoginRequest(Credentials):
    selected_role: UserRole | None = None


class EmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class TokenRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)


class PasswordReset(TokenRequest):
    password: str = Field(min_length=12, max_length=128)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    role: UserRole | None
    status: UserStatus
    email_verified: bool
    floor: int | None = None
    is_available: bool = False

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    message: str


class CsrfResponse(BaseModel):
    csrf_token: str
