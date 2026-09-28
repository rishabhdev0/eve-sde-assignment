import re
from pydantic import BaseModel, EmailStr, field_validator

PASSWORD_RULES = (
    "Password must be 8-72 characters and include at least one uppercase letter, "
    "one lowercase letter, one digit, and one special character (@$!%*?&#^_-)"
)


def validate_password_strength(v: str) -> str:
    if not (8 <= len(v) <= 72):  # 72 = bcrypt's hard byte limit
        raise ValueError(PASSWORD_RULES)
    if not re.search(r"[A-Z]", v):
        raise ValueError(PASSWORD_RULES)
    if not re.search(r"[a-z]", v):
        raise ValueError(PASSWORD_RULES)
    if not re.search(r"\d", v):
        raise ValueError(PASSWORD_RULES)
    if not re.search(r"[@$!%*?&#^_\-]", v):
        raise ValueError(PASSWORD_RULES)
    if v.strip() != v:
        raise ValueError("Password cannot have leading/trailing whitespace")
    return v


class SignupRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        return validate_password_strength(v)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v):
        return validate_password_strength(v)


class VerifyEmailRequest(BaseModel):
    token: str