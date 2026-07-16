from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.chat.artifacts import StoredWebArtifact, WebArtifactPage
    from app.chat.intents import AgentRouteDecision, IntentRoutingRequest
    from app.chat.market_analysis_skills import MarketAnalysisSkill
    from app.chat.prompts import AnswerPlanningRequest
    from app.chat.retrieval import ChunkCandidate, QueryRewrite, RewriteRequest
    from app.chat.schemas import (
        ApprovedEvidenceRecord,
        ContextSelection,
        ResearchAnswerPlan,
        StructuredContextPack,
    )
    from app.chat.web_discovery import SearchDiscovery
    from app.chat.web_fetcher import FetchedWebPage
    from app.models.company_model import Company


class EmbeddingProvider(Protocol):
    model_id: str
    dimensions: int

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class FilingChunkRepository(Protocol):
    def full_text_candidates(
        self,
        *,
        company_id: int,
        filing_id: UUID,
        query: str,
        limit: int,
    ) -> list["ChunkCandidate"]: ...

    def vector_candidates(
        self,
        *,
        company_id: int,
        filing_id: UUID,
        embedding: list[float],
        limit: int,
    ) -> list["ChunkCandidate"]: ...


class QueryRewriter(Protocol):
    async def rewrite(self, request: "RewriteRequest") -> "QueryRewrite": ...


class StructuredContextProvider(Protocol):
    async def resolve(
        self,
        *,
        company: "Company",
        selections: list["ContextSelection"],
        locale: str,
    ) -> "StructuredContextPack": ...


class WebSearchProvider(Protocol):
    async def search(
        self,
        *,
        question: str,
        company_name: str,
        symbol: str,
        internal_coverage: str,
        locale: str,
        official_hosts: tuple[str, ...] = (),
    ) -> "SearchDiscovery": ...


class WebPageFetcher(Protocol):
    async def fetch(self, url: str) -> "FetchedWebPage": ...


class MarketAnalysisProvider(Protocol):
    async def collect(
        self,
        *,
        company: "Company",
        question: str,
        skills: list["MarketAnalysisSkill"],
    ) -> list["ApprovedEvidenceRecord"]: ...


class WebArtifactWriter(Protocol):
    async def store(
        self,
        *,
        principal_scope: str,
        conversation_id: UUID,
        message_id: UUID,
        ordinal: int,
        page: "WebArtifactPage",
    ) -> "StoredWebArtifact": ...


class AnswerPlanningModel(Protocol):
    async def plan(
        self,
        request: "AnswerPlanningRequest",
    ) -> "ResearchAnswerPlan": ...


class IntentRoutingModel(Protocol):
    model_id: str

    async def route(
        self,
        request: "IntentRoutingRequest",
    ) -> "AgentRouteDecision": ...


@dataclass(frozen=True)
class ChatQuotaReservation:
    request_id: UUID
    principal_type: Literal["guest", "user"]
    principal_key: str
    usage_date: date
    conversation_id: UUID
    attempt_number: int
    now: datetime


@dataclass(frozen=True)
class ChatQuotaRecord:
    id: UUID
    request_id: UUID
    principal_type: Literal["guest", "user"]
    principal_key: str
    usage_date: date
    conversation_id: UUID | None
    user_message_id: UUID | None
    assistant_message_id: UUID | None
    attempt_number: int
    state: Literal["reserved", "consumed", "refunded"]


class ChatQuotaRepository(Protocol):
    def lock_scope(
        self,
        principal_type: str,
        principal_key: str,
        usage_date: date,
    ) -> None: ...

    def find_by_request(self, request_id: UUID) -> ChatQuotaRecord | None: ...

    def count_active(
        self,
        principal_type: str,
        principal_key: str,
        usage_date: date,
    ) -> int: ...

    def add(self, reservation: ChatQuotaReservation) -> ChatQuotaRecord: ...

    def get(self, ledger_id: UUID, *, lock: bool = False) -> ChatQuotaRecord | None: ...

    def attach_messages(
        self,
        ledger_id: UUID,
        user_message_id: UUID,
        assistant_message_id: UUID,
    ) -> ChatQuotaRecord: ...

    def transition(
        self,
        ledger_id: UUID,
        *,
        target: Literal["consumed", "refunded"],
        now: datetime,
        refund_reason: str | None = None,
    ) -> bool: ...
