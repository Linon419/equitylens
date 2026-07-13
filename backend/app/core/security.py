from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


ALGORITHM = "HS256"


@dataclass(frozen=True)
class AccessTokenClaims:
    user_id: int
    session_id: UUID
    token_type: str


@dataclass(frozen=True)
class RefreshTokenParts:
    record_id: UUID
    token_hash: str


def create_access_token(
    user_id: int,
    session_id: UUID,
    *,
    now: datetime | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    lifetime = expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "type": "access",
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + lifetime).timestamp()),
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY_ACCESS_API,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    payload = jwt.decode(
        token,
        settings.SECRET_KEY_ACCESS_API,
        algorithms=[ALGORITHM],
    )
    if payload.get("type") != "access":
        raise JWTError("Unexpected token type")
    try:
        return AccessTokenClaims(
            user_id=int(payload["sub"]),
            session_id=UUID(payload["sid"]),
            token_type=payload["type"],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise JWTError("Invalid access token claims") from exc


def create_refresh_token(record_id: UUID) -> tuple[str, str]:
    raw_token = f"{record_id}.{token_urlsafe(48)}"
    return raw_token, hash_refresh_token(raw_token)


def hash_refresh_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def parse_refresh_token(raw_token: str) -> RefreshTokenParts:
    record_text, separator, secret = raw_token.partition(".")
    if separator != "." or not secret:
        raise ValueError("Malformed refresh token")
    try:
        record_id = UUID(record_text)
    except ValueError as exc:
        raise ValueError("Malformed refresh token") from exc
    return RefreshTokenParts(
        record_id=record_id,
        token_hash=hash_refresh_token(raw_token),
    )


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
