from datetime import datetime
from typing import Literal

from sqlmodel import SQLModel

Locale = Literal["en-US", "zh-CN"]


class GoogleAuthRequest(SQLModel):
    credential: str
    preferred_locale: Locale


class RefreshRequest(SQLModel):
    refresh_token: str


class LogoutRequest(SQLModel):
    refresh_token: str


class PreferencesUpdate(SQLModel):
    preferred_locale: Locale


class UserPublic(SQLModel):
    id: int
    email: str
    full_name: str | None
    avatar_url: str | None
    preferred_locale: Locale
    created_at: datetime


class TokenResponse(SQLModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_expires_in: int
    refresh_expires_in: int


class AuthResponse(TokenResponse):
    user: UserPublic
