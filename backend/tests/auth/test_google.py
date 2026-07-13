import pytest

from app.auth.errors import AuthError
from app.auth.google import GoogleTokenVerifier


def test_google_verifier_normalizes_required_claims(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        lambda credential, request, audience: {
            "sub": "google-sub-1",
            "email": "Investor@Example.com",
            "email_verified": True,
            "name": "Investor One",
            "picture": "https://example.com/avatar.png",
        },
    )

    identity = GoogleTokenVerifier("client-id").verify("credential")

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
        lambda credential, request, audience: claims,
    )

    with pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN") as error:
        GoogleTokenVerifier("client-id").verify("credential")

    assert error.value.status_code == 401


def test_google_verifier_maps_library_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject(credential: str, request: object, audience: str) -> None:
        raise ValueError("wrong audience")

    monkeypatch.setattr(
        "app.auth.google.google_id_token.verify_oauth2_token",
        reject,
    )

    with pytest.raises(AuthError, match="AUTH_INVALID_GOOGLE_TOKEN") as error:
        GoogleTokenVerifier("client-id").verify("credential")

    assert error.value.status_code == 401
