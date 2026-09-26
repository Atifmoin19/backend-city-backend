import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from app.models.enums import Role


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=2, max_length=32)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserPublic(BaseModel):
    """Learner-safe view of a user. Never add password_hash or internal flags here."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    role: Role
    is_verified: bool
    onboarded_at: datetime | None = Field(default=None, exclude=True)
    learning_goal: str | None = None  # track slug chosen at signup
    start_district: str | None = None  # where the placement quiz suggested starting

    @computed_field  # type: ignore[prop-decorator]
    @property
    def onboarded(self) -> bool:
        """Finished the first-run orientation (so login can skip /welcome)."""
        return self.onboarded_at is not None


class AuthResponse(BaseModel):
    user: UserPublic


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=16, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class EmailTokenRequest(BaseModel):
    token: str = Field(min_length=16, max_length=200)
