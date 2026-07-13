from copy import deepcopy

import pytest

from app.research.schemas import (
    IntelligenceDraft,
    LocalizedIntelligence,
    VerificationResult,
)
from app.research.validator import (
    apply_verification,
    validate_localization_invariants,
)


def test_unsupported_claims_are_removed(
    draft_payload: dict,
    verification_payload: dict,
) -> None:
    verification_payload["verdicts"][0]["supported"] = False

    verified = apply_verification(
        IntelligenceDraft.model_validate(draft_payload),
        VerificationResult.model_validate(verification_payload),
    )

    assert verified.core_businesses == []
    assert verified.evidence_coverage == "partial"
    assert [item.citation_id for item in verified.citations] == ["citation-2"]


def test_locales_preserve_claim_ids_numbers_and_citations(
    draft_payload: dict,
    verification_payload: dict,
) -> None:
    verified = apply_verification(
        IntelligenceDraft.model_validate(draft_payload),
        VerificationResult.model_validate(verification_payload),
    )
    english = LocalizedIntelligence(
        locale="en",
        **verified.model_dump(),
    )
    chinese_payload = deepcopy(verified.model_dump())
    chinese_payload["core_businesses"][0]["title"] = "设备与服务"
    chinese_payload["core_businesses"][0]["explanation"] = (
        "硬件业务连接服务生态，覆盖 FY2025。"
    )
    chinese = LocalizedIntelligence(locale="zh", **chinese_payload)

    validate_localization_invariants(english, chinese)

    assert english.core_businesses[0].claim_id == (
        chinese.core_businesses[0].claim_id
    )
    assert english.core_businesses[0].citation_ids == (
        chinese.core_businesses[0].citation_ids
    )


def test_localization_rejects_changed_numeric_period(
    draft_payload: dict,
    verification_payload: dict,
) -> None:
    verified = apply_verification(
        IntelligenceDraft.model_validate(draft_payload),
        VerificationResult.model_validate(verification_payload),
    )
    english = LocalizedIntelligence(locale="en", **verified.model_dump())
    changed = deepcopy(verified.model_dump())
    changed["core_businesses"][0]["revenue_period"] = "FY2024"
    chinese = LocalizedIntelligence(locale="zh", **changed)

    with pytest.raises(ValueError, match="localization invariant"):
        validate_localization_invariants(english, chinese)
