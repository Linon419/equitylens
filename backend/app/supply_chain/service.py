from datetime import UTC, datetime

from sqlmodel import Session, select

from app.core.errors import DomainError
from app.jobs.schemas import JobPublic
from app.models.company_model import Company
from app.models.job_model import IngestionJob
from app.quota.identity import RequestPrincipal
from app.quota.repository import QuotaRepository
from app.quota.service import get_quota
from app.supply_chain._service_serializer import serialize_graph
from app.supply_chain.repository import SqlSupplyChainGraphRepository
from app.supply_chain.schemas import PublicSupplyChainGraph

_ACTIVE_TERMINAL_STATES = {"completed", "failed"}


class SupplyChainGraphService:
    def __init__(
        self,
        *,
        session: Session,
        repository: SqlSupplyChainGraphRepository,
        quota_repository: QuotaRepository,
        now: datetime | None = None,
        guest_limit: int = 2,
        user_limit: int = 10,
    ) -> None:
        self._session = session
        self._repository = repository
        self._quota_repository = quota_repository
        self._now = now
        self._guest_limit = guest_limit
        self._user_limit = user_limit

    def get_current(
        self,
        *,
        company: Company,
        principal: RequestPrincipal,
        locale: str,
        evidence: set[str] | None = None,
        limit: int = 40,
    ) -> PublicSupplyChainGraph:
        if locale not in {"en", "zh"}:
            raise DomainError("GRAPH_LOCALE_INVALID", 422)
        selected_evidence = {"verified"} if evidence is None else evidence
        if not selected_evidence or not selected_evidence <= {
            "verified",
            "potential",
        }:
            raise DomainError("GRAPH_EVIDENCE_FILTER_INVALID", 422)
        if company.id is None:
            raise DomainError("COMPANY_NOT_FOUND", 404)
        snapshot = self._repository.latest_public(company.id)
        if snapshot is None:
            raise DomainError("GRAPH_NOT_FOUND", 404)
        persisted = self._repository.load_public(snapshot.id)
        current_time = _as_utc(self._now or datetime.now(UTC))
        quota = get_quota(
            self._quota_repository,
            principal,
            current_time.date(),
            guest_limit=self._guest_limit,
            user_limit=self._user_limit,
        )
        graph = serialize_graph(
            persisted,
            company=company,
            locale=locale,
            evidence=selected_evidence,
            limit=max(10, min(40, limit)),
            quota=quota,
        )
        graph.refresh_job = self._active_refresh(company)
        return graph

    def _active_refresh(self, company: Company) -> JobPublic | None:
        job = self._session.exec(
            select(IngestionJob)
            .where(
                IngestionJob.company_id == company.id,
                IngestionJob.job_type == "supply_chain_graph",
                IngestionJob.state.not_in(_ACTIVE_TERMINAL_STATES),
            )
            .order_by(IngestionJob.created_at.desc())
        ).first()
        return JobPublic.from_job(job, company.symbol) if job is not None else None


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
