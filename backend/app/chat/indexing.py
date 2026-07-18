import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import tiktoken
from sqlalchemy import case
from sqlmodel import Session, select

from app.chat.chunker import SectionChunk, TokenCodec, chunk_section
from app.chat.contracts import EmbeddingProvider
from app.core.errors import DomainError
from app.filings.mapper import ANNUAL_FILING_FORMS
from app.models.chat_model import FilingChunk
from app.models.research_model import Filing, FilingSection


class TiktokenCodec:
    def __init__(self, model_id: str) -> None:
        try:
            self._encoding = tiktoken.encoding_for_model(model_id)
        except KeyError:
            self._encoding = tiktoken.get_encoding("cl100k_base")

    def encode(self, value: str) -> list[int]:
        return self._encoding.encode(value)

    def decode(self, tokens: list[int]) -> str:
        return self._encoding.decode(tokens)


class LangChainEmbeddingProvider:
    def __init__(self, model: Any, *, model_id: str, dimensions: int) -> None:
        self._model = model
        self.model_id = model_id
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._model.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self._model.aembed_query(text)


@dataclass(frozen=True)
class FilingIndexResult:
    filing_id: UUID
    chunk_count: int
    indexed_sections: int
    reused_sections: int


@dataclass(frozen=True)
class _SectionPlan:
    section: FilingSection
    chunks: list[SectionChunk]
    existing: list[FilingChunk]


class FilingIndexService:
    def __init__(
        self,
        session: Session,
        embeddings: EmbeddingProvider,
        *,
        token_codec: TokenCodec | None = None,
        chunk_schema_version: str = "filing-chunk.v1",
        target_tokens: int = 700,
        overlap_tokens: int = 100,
        minimum_final_tokens: int = 120,
        now: datetime | None = None,
    ) -> None:
        self._session = session
        self._embeddings = embeddings
        self._codec = token_codec or TiktokenCodec(embeddings.model_id)
        self._schema_version = chunk_schema_version
        self._target = target_tokens
        self._overlap = overlap_tokens
        self._minimum_final = minimum_final_tokens
        self._now = now

    async def index_latest(self, *, company_id: int) -> FilingIndexResult:
        filing = self._latest_annual_filing(company_id)
        sections = list(
            self._session.exec(
                select(FilingSection)
                .where(FilingSection.filing_id == filing.id)
                .order_by(FilingSection.ordinal)
            ).all()
        )
        if not sections:
            raise DomainError("CHAT_FILING_SECTIONS_MISSING", 422)
        reusable = 0
        changed: list[_SectionPlan] = []
        for section in sections:
            plan = self._plan_section(filing, section)
            if _matches(plan.existing, plan.chunks):
                reusable += 1
            else:
                changed.append(plan)
        if not changed:
            return self._result(filing, indexed=0, reused=reusable)
        await self._replace_changed(filing, changed)
        return self._result(filing, indexed=len(changed), reused=reusable)

    def _latest_annual_filing(self, company_id: int) -> Filing:
        filing = self._session.exec(
            select(Filing)
            .where(
                Filing.company_id == company_id,
                Filing.form.in_(ANNUAL_FILING_FORMS),
            )
            .order_by(
                Filing.filed_at.desc(),
                case((Filing.form == "10-K", 1), else_=0).desc(),
                Filing.id.desc(),
            )
        ).first()
        if filing is None:
            raise DomainError("FILING_NOT_FOUND", 404)
        return filing

    def _plan_section(
        self,
        filing: Filing,
        section: FilingSection,
    ) -> _SectionPlan:
        chunks = chunk_section(
            section,
            token_codec=self._codec,
            target=self._target,
            overlap=self._overlap,
            minimum_final=self._minimum_final,
        )
        existing = list(
            self._session.exec(
                select(FilingChunk)
                .where(
                    FilingChunk.filing_id == filing.id,
                    FilingChunk.section_id == section.id,
                    FilingChunk.chunk_schema_version == self._schema_version,
                    FilingChunk.embedding_model == self._embeddings.model_id,
                )
                .order_by(FilingChunk.ordinal)
            ).all()
        )
        return _SectionPlan(section, chunks, existing)

    async def _replace_changed(
        self,
        filing: Filing,
        plans: list[_SectionPlan],
    ) -> None:
        chunk_pairs = [
            (plan, chunk)
            for plan in plans
            for chunk in plan.chunks
        ]
        if not chunk_pairs:
            raise DomainError("CHAT_FILING_SECTIONS_MISSING", 422)
        vectors = await self._embeddings.embed_documents(
            [chunk.embedding_text for _plan, chunk in chunk_pairs]
        )
        _validate_vectors(
            vectors,
            expected_count=len(chunk_pairs),
            dimensions=self._embeddings.dimensions,
        )
        for plan in plans:
            for existing in plan.existing:
                self._session.delete(existing)
        self._session.flush()
        created_at = self._now or datetime.now(UTC)
        for (plan, chunk), vector in zip(chunk_pairs, vectors, strict=True):
            self._session.add(
                FilingChunk(
                    company_id=filing.company_id,
                    filing_id=filing.id,
                    section_id=plan.section.id,
                    ordinal=chunk.ordinal,
                    text=chunk.text,
                    token_count=chunk.token_count,
                    content_hash=chunk.content_hash,
                    chunk_schema_version=self._schema_version,
                    embedding_model=self._embeddings.model_id,
                    embedding=vector,
                    created_at=created_at,
                )
            )
        self._session.flush()

    def _result(
        self,
        filing: Filing,
        *,
        indexed: int,
        reused: int,
    ) -> FilingIndexResult:
        rows = self._session.exec(
            select(FilingChunk.id).where(
                FilingChunk.filing_id == filing.id,
                FilingChunk.chunk_schema_version == self._schema_version,
                FilingChunk.embedding_model == self._embeddings.model_id,
            )
        ).all()
        return FilingIndexResult(
            filing_id=filing.id,
            chunk_count=len(rows),
            indexed_sections=indexed,
            reused_sections=reused,
        )


def _matches(existing: list[FilingChunk], chunks: list[SectionChunk]) -> bool:
    if len(existing) != len(chunks):
        return False
    return all(
        stored.ordinal == expected.ordinal
        and stored.content_hash == expected.content_hash
        and stored.token_count == expected.token_count
        for stored, expected in zip(existing, chunks, strict=True)
    )


def _validate_vectors(
    vectors: list[list[float]],
    *,
    expected_count: int,
    dimensions: int,
) -> None:
    if len(vectors) != expected_count:
        raise ValueError("embedding count does not match filing chunks")
    if any(len(vector) != dimensions for vector in vectors):
        raise ValueError("embedding dimensions do not match configuration")
    if any(not math.isfinite(value) for vector in vectors for value in vector):
        raise ValueError("embedding values must be finite")
