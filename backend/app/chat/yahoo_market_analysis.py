import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import yfinance as yf
from loguru import logger

from app.chat.market_analysis_skills import MarketAnalysisSkill
from app.chat.schemas import ApprovedEvidenceRecord, EvidenceCandidate
from app.chat.yahoo_market_data import json_safe, mapping, read
from app.chat.yahoo_market_payloads import build_skill_payload
from app.models.company_model import Company


class YahooMarketAnalysisProvider:
    def __init__(
        self,
        ticker_factory: Callable[[str], Any] = yf.Ticker,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._ticker_factory = ticker_factory
        self._now = now or (lambda: datetime.now(UTC))

    async def collect(
        self,
        *,
        company: Company,
        question: str,
        skills: list[MarketAnalysisSkill],
    ) -> list[ApprovedEvidenceRecord]:
        if company.id is None:
            raise ValueError("persisted company required")
        return await asyncio.to_thread(
            self._collect,
            company,
            question,
            list(dict.fromkeys(skills)),
        )

    def _collect(
        self,
        company: Company,
        question: str,
        skills: list[MarketAnalysisSkill],
    ) -> list[ApprovedEvidenceRecord]:
        ticker = self._ticker_factory(company.symbol)
        info = mapping(read(ticker, "info", {}))
        fast_info = mapping(read(ticker, "fast_info", {}))
        observed_at = self._now()
        records = []
        for skill in skills:
            try:
                payload = build_skill_payload(
                    skill,
                    ticker=ticker,
                    ticker_factory=self._ticker_factory,
                    info=info,
                    fast_info=fast_info,
                    question=question,
                    symbol=company.symbol,
                )
            except Exception:
                logger.warning(
                    "Yahoo market-analysis collection failed for {} and {}",
                    company.symbol,
                    skill,
                )
                continue
            records.append(
                _evidence_record(
                    company=company,
                    skill=skill,
                    payload=payload,
                    observed_at=observed_at,
                )
            )
        return records


def _evidence_record(
    *,
    company: Company,
    skill: MarketAnalysisSkill,
    payload: dict[str, Any],
    observed_at: datetime,
) -> ApprovedEvidenceRecord:
    serialized = json.dumps(
        {
            "provider": "Yahoo Finance via yfinance",
            "skill": skill,
            "symbol": company.symbol,
            "retrieved_at": observed_at.isoformat(),
            "data": json_safe(payload),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    candidate = EvidenceCandidate(
        evidence_id=f"financial:yahoo:{skill}:{company.symbol}",
        source_kind="financial",
        source_id=f"{skill}:{company.symbol}",
        title=f"{company.symbol} Yahoo market analysis · {skill}",
        source_url=f"https://finance.yahoo.com/quote/{quote(company.symbol, safe='')}",
        source_anchor=skill,
        excerpt=serialized[:1_000],
        published_at=None,
        retrieved_at=observed_at,
        source_tier="trusted_secondary",
        verification="supporting",
        attributes={
            "provider": "yfinance",
            "analysis_skill": skill,
            "upstream_version": "finance-market-analysis@9.0.0",
        },
    )
    return ApprovedEvidenceRecord(
        company_id=company.id,
        candidate=candidate,
        source_text=serialized,
    )
