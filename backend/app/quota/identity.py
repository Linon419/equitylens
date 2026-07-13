import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID


@dataclass(frozen=True)
class GuestAssertion:
    guest_id: str
    ip_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class RequestPrincipal:
    principal_type: Literal["guest", "user"]
    principal_hash: str
    ip_hash: str | None

    @classmethod
    def guest(cls, principal_hash: str, ip_hash: str) -> "RequestPrincipal":
        return cls("guest", principal_hash, ip_hash)

    @classmethod
    def user(
        cls,
        user_id: int,
        secret: str,
    ) -> "RequestPrincipal":
        return cls("user", _keyed_hash(secret, f"user:{user_id}"), None)


def sign_guest_assertion(
    *,
    guest_id: str,
    ip_hash: str,
    secret: str,
    now: datetime | None = None,
) -> str:
    _validate_secret(secret)
    UUID(guest_id)
    issued_at = _as_utc(now or datetime.now(UTC))
    expires_at = issued_at + timedelta(minutes=5)
    payload = {
        "guest_id": guest_id,
        "ip_hash": ip_hash,
        "issued_at": _format_timestamp(issued_at),
        "expires_at": _format_timestamp(expires_at),
    }
    encoded = _encode(json.dumps(payload, separators=(",", ":")).encode())
    signature = _sign(encoded, secret)
    return f"{encoded}.{signature}"


def verify_guest_assertion(
    token: str,
    *,
    secret: str,
    now: datetime | None = None,
) -> GuestAssertion:
    _validate_secret(secret)
    try:
        encoded, supplied_signature = token.split(".", maxsplit=1)
        expected_signature = _sign(encoded, secret)
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise ValueError("invalid guest assertion signature")
        payload = json.loads(_decode(encoded))
        if list(payload) != [
            "guest_id",
            "ip_hash",
            "issued_at",
            "expires_at",
        ]:
            raise ValueError("invalid guest assertion fields")
        guest_id = str(payload["guest_id"])
        UUID(guest_id)
        ip_hash = str(payload["ip_hash"])
        issued_at = _parse_timestamp(payload["issued_at"])
        expires_at = _parse_timestamp(payload["expires_at"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("invalid guest assertion") from error
    if expires_at - issued_at != timedelta(minutes=5):
        raise ValueError("invalid guest assertion lifetime")
    if _as_utc(now or datetime.now(UTC)) >= expires_at:
        raise ValueError("expired guest assertion")
    return GuestAssertion(guest_id, ip_hash, expires_at)


def principal_from_assertion(
    token: str,
    *,
    signing_secret: str,
    hash_secret: str,
    now: datetime | None = None,
) -> RequestPrincipal:
    assertion = verify_guest_assertion(
        token,
        secret=signing_secret,
        now=now,
    )
    return RequestPrincipal.guest(
        _keyed_hash(hash_secret, f"guest:{assertion.guest_id}"),
        assertion.ip_hash,
    )


def _keyed_hash(secret: str, value: str) -> str:
    _validate_secret(secret)
    return hmac.new(
        secret.encode(),
        value.encode(),
        hashlib.sha256,
    ).hexdigest()


def _sign(encoded: str, secret: str) -> str:
    return hmac.new(
        secret.encode(),
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode()


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _validate_secret(secret: str) -> None:
    if len(secret) < 32:
        raise ValueError("quota secrets require at least 32 characters")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _format_timestamp(value: datetime) -> str:
    return _as_utc(value).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("invalid assertion timestamp")
    return _as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))
