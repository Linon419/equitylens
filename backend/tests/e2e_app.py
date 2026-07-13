import asyncio
import os
from collections.abc import Generator
from pathlib import Path
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
    get_db,
    get_google_verifier,
    get_intelligence_generator,
    get_job_backend,
    get_market_data_provider,
    get_sec_data_provider,
)
from app.auth.contracts import GoogleIdentity  # noqa: E402
from app.auth.errors import AuthError  # noqa: E402
from app.jobs.pipeline import CompanyIntelligencePipeline  # noqa: E402
from app.jobs.schemas import JobSubmission  # noqa: E402
from app.main import create_app  # noqa: E402
from tests.fixtures.company_intelligence import (  # noqa: E402
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


class E2EGoogleVerifier:
    def verify(self, credential: str) -> GoogleIdentity:
        if credential != "e2e-google-token":
            raise AuthError("AUTH_INVALID_GOOGLE_TOKEN", 401)
        return GoogleIdentity(
            subject="e2e-google-sub",
            email="investor@example.com",
            email_verified=True,
            full_name="E2E Investor",
            picture=None,
        )


def override_db() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


class E2EJobBackend:
    def __init__(self) -> None:
        self.tasks: set[asyncio.Task[None]] = set()
        self.enqueued_since_reset = 0

    async def enqueue(self, *, job_type: str, payload: dict) -> JobSubmission:
        job_id = UUID(str(payload["job_id"]))
        self.enqueued_since_reset += 1
        if self.enqueued_since_reset == 1:
            task = asyncio.create_task(self._run(job_id))
            self.tasks.add(task)
            task.add_done_callback(self._complete)
        return JobSubmission(job_id=f"e2e:{job_id}")

    async def drain(self) -> None:
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)

    async def _run(self, job_id: UUID) -> None:
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
                pipeline.analyze,
                pipeline.verify,
                pipeline.localize,
            ):
                await step(job_id)
                await asyncio.sleep(0.12)

    def _complete(self, task: asyncio.Task[None]) -> None:
        self.tasks.discard(task)
        if not task.cancelled():
            task.exception()


jobs = E2EJobBackend()


app = create_app()
app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_google_verifier] = E2EGoogleVerifier
app.dependency_overrides[get_market_data_provider] = lambda: market
app.dependency_overrides[get_sec_data_provider] = lambda: sec
app.dependency_overrides[get_intelligence_generator] = lambda: generator
app.dependency_overrides[get_job_backend] = lambda: jobs


@app.post("/__e2e__/reset", include_in_schema=False)
async def reset_e2e_state() -> dict[str, str]:
    await jobs.drain()
    jobs.enqueued_since_reset = 0
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    return {"status": "reset"}
