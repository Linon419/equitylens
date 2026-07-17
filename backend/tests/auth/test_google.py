import logging

import pytest

from app.auth.errors import AuthError
from app.auth.google import GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS, GoogleTokenVerifier


def test_google_verifier_normalizes_required_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verification_arguments: dict[str, object] = {}

    def verify_token(
        credential: str,
        request: object,
        audience: str,
        clock_skew_in_seconds: int,
    ) -> dict[str, object]:
        verification_arguments.update(
            credential=credential,
            request=request,
            audience=audience,
            clock_skew_in_seconds=clock_skew_in_seconds,
        )
        return {
            "sub": "google-sub-1",
            "email": "Investor@Example.com",
            "email_verified": True,
            "name": "Investor One",
            "picture": "https://example.com/avatar.png",
        }

    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        verify_token,
    )

    verifier = GoogleTokenVerifier("client-id")
    identity = verifier.verify("credential")

    assert verification_arguments == {
        "credential": "credential",
        "request": verifier.request,
        "audience": "client-id",
        "clock_skew_in_seconds": GOOGLE_ID_TOKEN_CLOCK_SKEW_SECONDS,
    }
    assert identity.subject == "google-sub-1"
    assert identity.email == "investor@example.com"
    assert identity.email_verified is True
    assert identity.full_name == "Investor One"
    assert identity.picture == "https://example.com/avatar.png"


@pytest.mark.parametrize(
    "claims",
    [
        {},
        {"sub": "sub", "email": "a@example.com", "email_verified": False},
        {"sub": "sub", "email_verified": True},
    ],
)
def test_google_verifier_rejects_incomplete_identity(
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> None:
    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        lambda credential, request, audience, clock_skew_in_seconds: claims,
    )

    with pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN") as error:
        GoogleTokenVerifier("client-id").verify("credential")

    assert error.value.status_code == 401


def test_google_verifier_maps_library_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def reject(
        credential: str,
        request: object,
        audience: str,
        clock_skew_in_seconds: int,
    ) -> None:
        raise ValueError("wrong audience")

    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        reject,
    )

    with (
        caplog.at_level(logging.WARNING),
        pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN") as error,
    ):
        GoogleTokenVerifier("client-id").verify("secret-credential")

    assert error.value.status_code == 401
    assert "Google ID token validation failed: wrong audience" in caplog.text
    assert "secret-credential" not in caplog.text
