from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.research.schemas import (
        EvidenceBundle,
        IntelligenceDraft,
        LocalizedIntelligence,
        VerificationResult,
        VerifiedIntelligence,
    )


class IntelligenceGenerator(Protocol):
    async def generate(self, evidence: EvidenceBundle) -> IntelligenceDraft: ...

    async def verify(self, draft: IntelligenceDraft) -> VerificationResult: ...

    async def localize(
        self,
        verified: VerifiedIntelligence,
        locale: str,
    ) -> LocalizedIntelligence: ...
