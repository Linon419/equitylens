from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    parse_refresh_token,
)


def test_access_token_contains_user_session_and_type() -> None:
    family_id = uuid4()
    now = datetime.now(UTC)

    token = create_access_token(42, family_id, now=now)
    claims = decode_access_token(token)

    assert claims.user_id == 42
    assert claims.session_id == family_id
    assert claims.token_type == "access"


def test_refresh_token_round_trips_record_id_and_hash() -> None:
    record_id = uuid4()

    raw_token, token_hash = create_refresh_token(record_id)
    parsed = parse_refresh_token(raw_token)

    assert parsed.record_id == record_id
    assert parsed.token_hash == token_hash


def test_access_token_rejects_wrong_type() -> None:
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": "42",
            "sid": str(uuid4()),
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=5)).timestamp()),
        },
        settings.SECRET_KEY_ACCESS_API,
        algorithm=ALGORITHM,
    )

    with pytest.raises(JWTError, match="Unexpected token type"):
        decode_access_token(token)


def test_access_token_rejects_tampered_signature() -> None:
    token = create_access_token(42, uuid4(), now=datetime.now(UTC))
    payload = token.rsplit(".", 1)

    with pytest.raises(JWTError):
        decode_access_token(".".join([payload[0], "invalid-signature"]))


def test_access_token_rejects_expired_claims() -> None:
    token = create_access_token(
        42,
        uuid4(),
        now=datetime.now(UTC) - timedelta(hours=2),
        expires_delta=timedelta(minutes=1),
    )

    with pytest.raises(JWTError):
        decode_access_token(token)


@pytest.mark.parametrize("raw_token", ["", "missing-separator", "not-a-uuid.secret"])
def test_refresh_token_rejects_malformed_values(raw_token: str) -> None:
    with pytest.raises(ValueError, match="Malformed refresh token"):
        parse_refresh_token(raw_token)
