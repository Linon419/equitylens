from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlmodel import Session

from app.quota.repository import QuotaRepository
from app.supply_chain.contracts import (
    EntityResolver,
    OfficialSourceCollector,
    SupplyChainAgent,
    SupplyChainGraphRepository,
)
from app.supply_chain.schemas import AcceptedGraph

type GraphValidator = Callable[..., AcceptedGraph]


@dataclass
class SupplyChainPipelineServices:
    session: Session
    collector: OfficialSourceCollector
    agent: SupplyChainAgent
    resolver: EntityResolver
    repository: SupplyChainGraphRepository
    quota_repository: QuotaRepository
    validator: GraphValidator
    schema_version: str
    prompt_version: str
    model_id: str
    min_nodes: int
    max_nodes: int
    evidence_threshold: float
    now: datetime | None = None
