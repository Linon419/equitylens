from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.research.schemas import IntelligenceDraft
from app.research.validator import validate_draft_against_evidence


def test_every_claim_requires_known_citations(
    draft_payload: dict,
    evidence_bundle,
) -> None:
    draft = IntelligenceDraft.model_validate(draft_payload)

    validate_draft_against_evidence(draft, evidence_bundle)

    assert draft.core_businesses[0].citation_ids == ["citation-1"]


@pytest.mark.parametrize(
    ("mutation", "path"),
    [
        ("empty_citations", ("core_businesses", 0, "citation_ids")),
        ("unknown_confidence", ("core_businesses", 0, "confidence")),
        ("long_excerpt", ("citations", 0, "excerpt")),
    ],
)
def test_schema_rejects_invalid_bounded_fields(
    draft_payload: dict,
    mutation: str,
    path: tuple,
) -> None:
    invalid = deepcopy(draft_payload)
    target = invalid
    for key in path[:-1]:
        target = target[key]
    values = {
        "empty_citations": [],
        "unknown_confidence": "Certain",
        "long_excerpt": "x" * 1001,
    }
    target[path[-1]] = values[mutation]

    with pytest.raises(ValidationError):
        IntelligenceDraft.model_validate(invalid)


def test_schema_rejects_duplicate_claim_ids(draft_payload: dict) -> None:
    invalid = deepcopy(draft_payload)
    invalid["upstream"][0]["claim_id"] = "business-1"

    with pytest.raises(ValidationError):
        IntelligenceDraft.model_validate(invalid)


def test_validator_rejects_unknown_evidence_section(
    draft_payload: dict,
    evidence_bundle,
) -> None:
    invalid = deepcopy(draft_payload)
    invalid["citations"][0]["section_id"] = "missing-section"

    with pytest.raises(ValueError, match="unknown evidence section"):
        validate_draft_against_evidence(
            IntelligenceDraft.model_validate(invalid),
            evidence_bundle,
        )
