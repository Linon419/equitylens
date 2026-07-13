from datetime import datetime

from pydantic import BaseModel


class QuotaStatus(BaseModel):
    limit: int
    used: int
    remaining: int
    resets_at: datetime
