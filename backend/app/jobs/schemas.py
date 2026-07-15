from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel

from app.models.job_model import IngestionJob
from app.quota.schemas import QuotaStatus


class JobSubmission(BaseModel):
    job_id: str


class JobBackend(Protocol):
    async def enqueue(
        self,
        *,
        job_type: str,
        payload: dict,
    ) -> JobSubmission: ...


class JobPublic(BaseModel):
    id: UUID
    result_kind: Literal[
        "company_intelligence",
        "supply_chain_graph",
        "filing_index",
    ]
    company_symbol: str
    state: str
    current_step: str
    attempt_count: int
    retry_eligible: bool
    error_code: str | None
    snapshot_id: UUID | None
    graph_snapshot_id: UUID | None
    provider_run_id: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_job(cls, job: IngestionJob, symbol: str) -> "JobPublic":
        return cls(
            id=job.id,
            result_kind=job.job_type,
            company_symbol=symbol,
            state=job.state,
            current_step=job.current_step,
            attempt_count=job.attempt_count,
            retry_eligible=job.retry_eligible,
            error_code=job.error_code,
            snapshot_id=job.snapshot_id,
            graph_snapshot_id=job.graph_snapshot_id,
            provider_run_id=job.provider_run_id,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class SyncResponse(BaseModel):
    status: Literal["accepted", "active_job", "reused_snapshot"]
    job: JobPublic | None = None
    snapshot_id: UUID | None = None
    quota: QuotaStatus


class FilingIndexSyncResponse(BaseModel):
    status: Literal["accepted", "active_job", "ready"]
    job: JobPublic | None = None
    filing_id: UUID | None = None
