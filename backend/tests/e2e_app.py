import asyncio
import json
import os
from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

TEST_DATABASE = Path("/tmp/equitylens-auth-e2e.db")
TEST_DATABASE.unlink(missing_ok=True)

ENV = {
    "SECRET_KEY_ACCESS_API": "e2e-secret-key-with-at-least-32-characters",
    "DATABASE_URL": f"sqlite:///{TEST_DATABASE}",
    "OPENAI_API_KEY": "e2e-openai-key",
    "OPENAI_ORGANIZATION": "e2e-organization",
    "FIRST_SUPERUSER": "admin@example.com",
    "FIRST_SUPERUSER_PASSWORD": "e2e-password",
    "GOOGLE_CLIENT_ID": "e2e-client",
    "FRONTEND_URL": "http://127.0.0.1:3000",
    "SEC_USER_AGENT": "EquityLens e2e admin@example.com",
    "GUEST_SIGNING_SECRET": "g" * 32,
    "QUOTA_HASH_SECRET": "q" * 32,
    "INTERNAL_JOB_SECRET": "i" * 32,
    "REDIS_URL": "redis://localhost:6379/0",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "S3_BUCKET": "filings",
    "S3_ACCESS_KEY_ID": "e2e-key",
    "S3_SECRET_ACCESS_KEY": "e2e-secret",
}
for key, value in ENV.items():
    os.environ.setdefault(key, value)

from sqlmodel import Session, SQLModel, create_engine  # noqa: E402

from app import models  # noqa: E402, F401
from app.api.deps import (  # noqa: E402
    get_chat_answer_agent,
    get_chat_context_provider,
    get_chat_evidence_pipeline,
    get_db,
    get_google_verifier,
    get_intelligence_generator,
    get_job_backend,
    get_market_data_provider,
    get_sec_data_provider,
)
from app.auth.contracts import GoogleIdentity  # noqa: E402
from app.auth.errors import AuthError  # noqa: E402
from app.chat.schemas import (  # noqa: E402
    AnswerEvidencePack,
    ChatReadiness,
    ReadinessResource,
    ResearchAnswerPlan,
    StructuredContextPack,
)
from app.chat.service import PreparedAnswerEvidence  # noqa: E402
from app.core.errors import DomainError  # noqa: E402
from app.jobs.pipeline import CompanyIntelligencePipeline  # noqa: E402
from app.jobs.schemas import JobSubmission  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.company_model import Company  # noqa: E402
from app.models.job_model import IngestionJob  # noqa: E402
from app.quota.repository import SQLiteQuotaRepository  # noqa: E402
from app.supply_chain.collector import SourceCollectionError  # noqa: E402
from app.supply_chain.pipeline import (  # noqa: E402
    SupplyChainGraphPipeline,
    SupplyChainPipelineServices,
)
from app.supply_chain.repository import (  # noqa: E402
    SqlSupplyChainGraphRepository,
)
from app.supply_chain.schemas import (  # noqa: E402
    AcceptedGraph,
    GraphDraft,
    GraphLocalization,
    GraphVerification,
    OfficialSourceDocument,
    ResolvedEntity,
    SourcePlan,
)
from app.supply_chain.validator import validate_for_publication  # noqa: E402
from tests.fixtures.company_intelligence import (  # noqa: E402
    COMPANY_NAMES,
    COMPANY_SYMBOLS,
    DeterministicIntelligenceGenerator,
    DeterministicMarketProvider,
    DeterministicSecProvider,
)

engine = create_engine(
    f"sqlite:///{TEST_DATABASE}",
    connect_args={"check_same_thread": False},
)
SQLModel.metadata.create_all(engine)
market = DeterministicMarketProvider()
sec = DeterministicSecProvider()
generator = DeterministicIntelligenceGenerator()
GRAPH_FIXTURES = Path(__file__).parent / "fixtures" / "supply_chain"
CHAT_FIXTURES = Path(__file__).parent / "fixtures" / "chat"


def seed_companies() -> None:
    now = datetime.now(UTC)
    with Session(engine) as session:
        for index, symbol in enumerate(COMPANY_SYMBOLS):
            session.add(
                Company(
                    symbol=symbol,
                    cik=f"{index + 320193:010d}",
                    name=COMPANY_NAMES[symbol],
                    exchange="Nasdaq",
                    sector="Technology",
                    industry="Consumer Electronics",
                    description=(
                        f"{COMPANY_NAMES[symbol]} is represented by fabricated "
                        "company data in this deterministic test environment."
                    ),
                    profile_fetched_at=now,
                    updated_at=now,
                )
            )
        session.commit()


seed_companies()


def graph_fixture(name: str) -> dict[str, Any]:
    return json.loads((GRAPH_FIXTURES / name).read_text())


GRAPH_SOURCES_PAYLOAD = graph_fixture("aapl_sources.json")
GRAPH_SOURCES = [
    OfficialSourceDocument.model_validate(item)
    for item in GRAPH_SOURCES_PAYLOAD["documents"]
]
GRAPH_PLAN = SourcePlan.model_validate(GRAPH_SOURCES_PAYLOAD["source_plan"])
GRAPH_DRAFT = GraphDraft.model_validate(graph_fixture("aapl_draft.json"))
GRAPH_VERIFICATION = GraphVerification.model_validate(
    graph_fixture("aapl_verification.json")
)
GRAPH_ACCEPTED = validate_for_publication(
    draft=GRAPH_DRAFT,
    verification=GRAPH_VERIFICATION,
    sources=GRAPH_SOURCES,
    min_nodes=25,
    max_nodes=40,
    evidence_threshold=0.75,
)


def graph_localization(graph: AcceptedGraph) -> GraphLocalization:
    def node_payload(node) -> dict[str, Any]:
        return {
            "node_key": node.node_key,
            "kind": node.kind,
            "layer": node.layer,
            "label_zh": f"中文 {node.label_en}",
            "description_zh": f"中文说明 {node.description_en}",
            "company_id": node.company_id,
            "symbol": node.symbol,
            "cik": node.cik,
            "importance": node.importance,
            "confidence": node.confidence,
            "rank": node.rank,
        }

    def edge_payload(edge) -> dict[str, Any]:
        return {
            "edge_key": edge.edge_key,
            "source_node_key": edge.source_node_key,
            "target_node_key": edge.target_node_key,
            "relationship_type": edge.relationship_type,
            "evidence_status": edge.evidence_status,
            "confidence": edge.confidence,
            "importance": edge.importance,
            "explanation_zh": f"中文说明 {edge.explanation_en}",
            "evidence_refs": [
                item.model_dump() for item in edge.evidence_refs
            ],
        }

    return GraphLocalization.model_validate(
        {
            "locale": "zh",
            "focus_node_key": graph.focus_node_key,
            "thesis_zh": f"中文 {graph.thesis_en}",
            "nodes": [node_payload(node) for node in graph.accepted_nodes],
            "public_edges": [edge_payload(edge) for edge in graph.public_edges],
            "potential_edges": [edge_payload(edge) for edge in graph.potential_edges],
            "internal_edges": [edge_payload(edge) for edge in graph.internal_edges],
        }
    )


GRAPH_LOCALIZATION = graph_localization(GRAPH_ACCEPTED)


class E2EChatContextProvider:
    async def resolve(self, **_kwargs) -> StructuredContextPack:
        ready = ReadinessResource(state="ready", action=None)
        return StructuredContextPack(
            items=[],
            evidence=[],
            readiness=ChatReadiness(
                company_symbol="AAPL",
                intelligence=ready,
                filing_text=ready,
                filing_index=ready,
                supply_chain_graph=ready,
                web_recency=ready,
            ),
            gaps=[],
        )


class E2EChatEvidencePipeline:
    async def prepare_internal(self, **kwargs):
        await asyncio.sleep(0.12)
        return kwargs["question"]

    async def add_web(self, **kwargs) -> PreparedAnswerEvidence:
        await asyncio.sleep(0.12)
        question = kwargs["question"].casefold()
        if "required web failure" in question:
            raise DomainError("CHAT_WEB_SEARCH_FAILED", 503)
        evidence = AnswerEvidencePack.model_validate_json(
            (CHAT_FIXTURES / "aapl_evidence.json").read_text()
        )
        use_web = any(
            term in question
            for term in ("current", "recent", "latest", "最新", "近期")
        )
        if use_web:
            return PreparedAnswerEvidence(evidence, [])
        return PreparedAnswerEvidence(
            evidence.model_copy(
                update={
                    "records": [
                        record
                        for record in evidence.records
                        if record.candidate.source_kind != "web"
                    ],
                    "web_search_used": False,
                }
            ),
            [],
        )


class E2EChatAnswerAgent:
    model_id = "e2e-company-research-agent"

    def __init__(self) -> None:
        self.failed_once: set[str] = set()

    async def create_plan(
        self,
        question: str,
        evidence: AnswerEvidencePack,
        **kwargs,
    ) -> ResearchAnswerPlan:
        await asyncio.sleep(0.12)
        if (
            "force model failure" in question.casefold()
            and question not in self.failed_once
        ):
            self.failed_once.add(question)
            raise DomainError("CHAT_ANSWER_GENERATION_FAILED", 503)
        answers = json.loads((CHAT_FIXTURES / "aapl_answers.json").read_text())
        answer = answers["valid_zh" if kwargs["locale"] == "zh-CN" else "valid_en"]
        if not evidence.web_search_used:
            answer["risks_and_uncertainties"] = []
            answer["sources"] = [
                source for source in answer["sources"] if not source.startswith("web:")
            ]
            answer["web_search_used"] = False
        return ResearchAnswerPlan.model_validate(answer)


class E2EOfficialSourceTools:
    async def fetch_official_source(
        self,
        *,
        source_id: str,
    ) -> OfficialSourceDocument:
        return next(item for item in GRAPH_SOURCES if item.source_id == source_id)

    def selected_documents(self, source_ids) -> list[OfficialSourceDocument]:
        selected = set(source_ids)
        return [item for item in GRAPH_SOURCES if item.source_id in selected]


class E2EOfficialSourceCollector:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def prepare_catalog(self, *, company: Company):
        if self.fail:
            raise SourceCollectionError("E2E_REFRESH_FAILED", retryable=True)
        return E2EOfficialSourceTools()


class E2ESupplyChainAgent:
    async def plan_sources(self, *, company, tools) -> SourcePlan:
        return GRAPH_PLAN

    async def extract_graph(self, *, company, sources) -> GraphDraft:
        return GRAPH_DRAFT

    async def verify_graph(self, *, draft, sources) -> GraphVerification:
        return GRAPH_VERIFICATION

    async def localize_graph(
        self,
        *,
        graph,
        locale="zh",
    ) -> GraphLocalization:
        return GRAPH_LOCALIZATION


class E2EEntityResolver:
    async def resolve(self, candidate) -> ResolvedEntity:
        raise AssertionError("E2E graph pipeline resolves the complete draft")

    async def resolve_draft(self, draft: GraphDraft) -> GraphDraft:
        return draft


class E2EGoogleVerifier:
    def verify(self, credential: str) -> GoogleIdentity:
        identities = {
            "e2e-google-token": (
                "e2e-google-sub",
                "investor@example.com",
                "E2E Investor",
            ),
            "e2e-google-token-2": (
                "e2e-google-sub-2",
                "analyst@example.com",
                "E2E Analyst",
            ),
        }
        if credential not in identities:
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)
        subject, email, full_name = identities[credential]
        return GoogleIdentity(
            subject=subject,
            email=email,
            email_verified=True,
            full_name=full_name,
            picture=None,
        )


def override_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


class E2EJobBackend:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[None]] = set()
        self.graph_lock = asyncio.Lock()
        self.enqueued_since_reset = 0
        self.intelligence_enqueued_since_reset = 0

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        job_id = UUID(str(payload["job_id"]))
        self.enqueued_since_reset += 1
        if job_type == "supply_chain_graph":
            task = asyncio.create_task(
                self._run_graph(job_id, fail=self._is_forced_refresh(job_id))
            )
            self.tasks.add(task)
            task.add_done_callback(self._complete)
        else:
            self.intelligence_enqueued_since_reset += 1
            if self.intelligence_enqueued_since_reset == 1:
                task = asyncio.create_task(self._run_intelligence(job_id))
                self.tasks.add(task)
                task.add_done_callback(self._complete)
        return JobSubmission(job_id=f"e2e:{job_id}")

    def _is_forced_refresh(self, job_id: UUID) -> bool:
        with Session(engine) as session:
            job = session.get(IngestionJob, job_id)
            return bool(job and ":refresh:" in job.deduplication_key)

    async def drain(self) -> None:
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)

    async def _run_intelligence(self, job_id: UUID) -> None:
        await asyncio.sleep(0.4)
        with Session(engine) as session:
            pipeline = CompanyIntelligencePipeline(
                session,
                sec,
                generator,
                schema_version="company-intelligence-v1",
                prompt_version="company-intelligence-2026-07-13",
            )
            for step in (
                pipeline.download,
                pipeline.parse,
                pipeline.index,
                pipeline.analyze,
                pipeline.verify,
                pipeline.localize,
            ):
                await step(job_id)
                await asyncio.sleep(0.12)

    async def _run_graph(self, job_id: UUID, *, fail: bool) -> None:
        async with self.graph_lock:
            await self._run_graph_serialized(job_id, fail=fail)

    async def _run_graph_serialized(self, job_id: UUID, *, fail: bool) -> None:
        await asyncio.sleep(2.4 if fail else 0.25)
        with Session(engine) as session:
            pipeline = SupplyChainGraphPipeline(
                SupplyChainPipelineServices(
                    session=session,
                    collector=E2EOfficialSourceCollector(fail=fail),
                    agent=E2ESupplyChainAgent(),
                    resolver=E2EEntityResolver(),
                    repository=SqlSupplyChainGraphRepository(session),
                    quota_repository=SQLiteQuotaRepository(session),
                    validator=validate_for_publication,
                    schema_version="supply-chain-graph.v1",
                    prompt_version="supply-chain-graph.2026-07-14",
                    model_id="e2e-graph-agent",
                    min_nodes=25,
                    max_nodes=40,
                    evidence_threshold=0.75,
                    now=datetime(2026, 7, 14, 12, tzinfo=UTC),
                )
            )
            try:
                await pipeline.collect(job_id)
                session.commit()
                await asyncio.sleep(2.0)
                for step in (
                    pipeline.extract,
                    pipeline.resolve,
                    pipeline.verify,
                    pipeline.localize,
                    pipeline.publish,
                ):
                    await step(job_id)
                    session.commit()
                    await asyncio.sleep(0.1)
            except SourceCollectionError:
                session.commit()
                return

    def _complete(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled():
            task.exception()


jobs = E2EJobBackend()
chat_context = E2EChatContextProvider()
chat_evidence = E2EChatEvidencePipeline()
chat_agent = E2EChatAnswerAgent()


app = create_app()
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_google_verifier] = E2EGoogleVerifier
app.dependency_overrides[get_market_data_provider] = lambda: market
app.dependency_overrides[get_sec_data_provider] = lambda: sec
app.dependency_overrides[get_intelligence_generator] = lambda: generator
app.dependency_overrides[get_job_backend] = lambda: jobs
app.dependency_overrides[get_chat_context_provider] = lambda: chat_context
app.dependency_overrides[get_chat_evidence_pipeline] = lambda: chat_evidence
app.dependency_overrides[get_chat_answer_agent] = lambda: chat_agent


@app.post("/__e2e__/reset", include_in_schema=False)
async def reset_e2e_state() -> dict[str, str]:
    await jobs.drain()
    jobs.enqueued_since_reset = 0
    jobs.intelligence_enqueued_since_reset = 0
    chat_agent.failed_once.clear()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    seed_companies()
    return {"status": "reset"}
