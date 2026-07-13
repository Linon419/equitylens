from google.auth.transport.requests import Request
from google.oauth2 import id_token as google_id_token

from app.auth.contracts import GoogleIdentity
from app.auth.errors import AuthError


class GoogleTokenVerifier:
    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.request = Request()

    def verify(self, credential: str) -> GoogleIdentity:
        try:
            claims = google_id_token.verify_oauth2_token(
                credential,
                self.request,
                self.client_id,
            )
        except ValueError as error:
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401) from error

        subject = claims.get("sub")
        email = claims.get("email")
        email_verified = claims.get("email_verified") is True
        if not subject or not email or not email_verified:
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)

        return GoogleIdentity(
            subject=str(subject),
            email=str(email).lower(),
            email_verified=True,
            full_name=str(claims["name"]) if claims.get("name") else None,
            picture=str(claims["picture"]) if claims.get("picture") else None,
        )
