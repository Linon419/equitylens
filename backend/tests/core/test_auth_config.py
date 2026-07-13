from app.core.config import Settings


def test_authentication_defaults_are_short_lived() -> None:
    settings = Settings()

    assert settings.GOOGLE_CLIENT_ID == "test-google-client-id"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 30
    assert settings.REFRESH_REUSE_GRACE_SECONDS == 10
    assert settings.FRONTEND_URL == "http://localhost:3000"
