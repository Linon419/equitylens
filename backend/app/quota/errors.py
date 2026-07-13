from app.core.errors import DomainError


class QuotaExceeded(DomainError):
    def __init__(self, code: str = "AGENT_DAILY_QUOTA_EXCEEDED") -> None:
        super().__init__(code, 429)


class QuotaRowLimitReached(Exception):
    def __init__(self, principal_type: str) -> None:
        super().__init__(principal_type)
        self.principal_type = principal_type
