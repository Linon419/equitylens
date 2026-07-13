from datetime import UTC, datetime, timedelta

import pytest

from app.quota.identity import (
    GuestAssertion,
    RequestPrincipal,
    principal_from_assertion,
    sign_guest_assertion,
    verify_guest_assertion,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)
SECRET = "guest-secret-with-at-least-32-characters"
HASH_SECRET = "quota-secret-with-at-least-32-characters"
GUEST_ID = "11111111-1111-4111-8111-111111111111"


def test_signed_guest_assertion_round_trips_without_raw_ip() -> None:
    token = sign_guest_assertion(
        guest_id=GUEST_ID,
        ip_hash="daily-ip-hash",
        secret=SECRET,
        now=NOW,
    )
    assertion = verify_guest_assertion(token, secret=SECRET, now=NOW)

    assert assertion == GuestAssertion(
        guest_id=GUEST_ID,
        ip_hash="daily-ip-hash",
        expires_at=NOW + timedelta(minutes=5),
    )
    assert "daily-ip-hash" not in token


def test_expired_or_tampered_assertion_is_rejected() -> None:
    token = sign_guest_assertion(
        guest_id=GUEST_ID,
        ip_hash="hash",
        secret=SECRET,
        now=NOW,
    )

    with pytest.raises(ValueError):
        verify_guest_assertion(token + "x", secret=SECRET, now=NOW)
    with pytest.raises(ValueError):
        verify_guest_assertion(
            token,
            secret=SECRET,
            now=NOW + timedelta(minutes=6),
        )


def test_principals_use_keyed_hashes() -> None:
    token = sign_guest_assertion(
        guest_id=GUEST_ID,
        ip_hash="a" * 64,
        secret=SECRET,
        now=NOW,
    )

    guest = principal_from_assertion(
        token,
        signing_secret=SECRET,
        hash_secret=HASH_SECRET,
        now=NOW,
    )
    user = RequestPrincipal.user(42, HASH_SECRET)

    assert guest.principal_type == "guest"
    assert guest.principal_hash != GUEST_ID
    assert len(guest.principal_hash) == 64
    assert guest.ip_hash == "a" * 64
    assert user.principal_type == "user"
    assert len(user.principal_hash) == 64
