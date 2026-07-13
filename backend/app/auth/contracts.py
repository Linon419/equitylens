from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    full_name: str | None
    picture: str | None


class GoogleVerifier(Protocol):
    def verify(self, credential: str) -> GoogleIdentity: ...
