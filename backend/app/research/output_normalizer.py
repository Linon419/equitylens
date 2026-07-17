import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.research.schemas import (
    CATEGORY_FIELDS,
    EvidenceBundle,
    IntelligenceContent,
    IntelligenceDraft,
)


def normalize_json_result(
    schema: type[BaseModel],
    result: Any,
    payload: str,
) -> Any:
    if issubclass(schema, IntelligenceContent):
        result = _drop_unreferenced_citations(result)
    if schema is IntelligenceDraft:
        result = _expand_short_citations(result, payload)
        result = _drop_claims_without_exact_evidence(result, payload)
    return result


def _drop_claims_without_exact_evidence(result: Any, payload: str) -> Any:
    if not isinstance(result, dict):
        return result
    evidence = _parse_evidence(payload)
    citations = result.get("citations")
    if evidence is None or not isinstance(citations, list):
        return result
    sections = {section.section_id: section.text for section in evidence.sections}
    valid_citations = {
        citation.get("citation_id"): citation
        for citation in citations
        if _citation_matches_evidence(citation, sections)
    }
    normalized = dict(result)
    referenced: set[str] = set()
    for field in CATEGORY_FIELDS:
        claims = result.get(field)
        if not isinstance(claims, list):
            continue
        valid_claims = [
            claim
            for claim in claims
            if _claim_has_exact_citations(claim, valid_citations)
        ]
        normalized[field] = valid_claims
        referenced.update(
            citation_id
            for claim in valid_claims
            for citation_id in claim["citation_ids"]
        )
    normalized["citations"] = [
        citation
        for citation_id, citation in valid_citations.items()
        if citation_id in referenced
    ]
    return normalized


def _claim_has_exact_citations(
    claim: Any,
    valid_citations: dict[Any, dict],
) -> bool:
    if not isinstance(claim, dict):
        return False
    citation_ids = claim.get("citation_ids")
    return bool(citation_ids) and all(
        citation_id in valid_citations for citation_id in citation_ids
    )


def _citation_matches_evidence(
    citation: Any,
    sections: dict[str, str],
) -> bool:
    if not isinstance(citation, dict):
        return False
    excerpt = citation.get("excerpt")
    section = sections.get(citation.get("section_id"))
    if not isinstance(excerpt, str) or not section:
        return False
    return _normalize(excerpt) in _normalize(section)


def _expand_short_citations(result: Any, payload: str) -> Any:
    if not isinstance(result, dict):
        return result
    evidence = _parse_evidence(payload)
    citations = result.get("citations")
    if evidence is None or not isinstance(citations, list):
        return result
    sections = {section.section_id: section.text for section in evidence.sections}
    normalized = dict(result)
    normalized["citations"] = [
        _expand_citation(citation, sections) for citation in citations
    ]
    return normalized


def _parse_evidence(payload: str) -> EvidenceBundle | None:
    try:
        return EvidenceBundle.model_validate_json(payload)
    except (ValidationError, ValueError):
        return None


def _expand_citation(citation: Any, sections: dict[str, str]) -> Any:
    if not isinstance(citation, dict):
        return citation
    excerpt = citation.get("excerpt")
    section_text = sections.get(citation.get("section_id"))
    if not isinstance(excerpt, str) or len(excerpt) >= 20 or not section_text:
        return citation
    expanded = _expand_exact_excerpt(excerpt, section_text)
    if expanded == excerpt:
        return citation
    normalized = dict(citation)
    normalized["excerpt"] = expanded
    return normalized


def _expand_exact_excerpt(excerpt: str, section_text: str) -> str:
    normalized_chars: list[str] = []
    source_offsets: list[int] = []
    for token in re.finditer(r"\S+", section_text):
        if normalized_chars:
            normalized_chars.append(" ")
            source_offsets.append(token.start())
        normalized_chars.extend(token.group())
        source_offsets.extend(range(token.start(), token.end()))
    normalized_excerpt = _normalize(excerpt)
    position = "".join(normalized_chars).find(normalized_excerpt)
    if position < 0 or not normalized_excerpt:
        return excerpt
    start = source_offsets[position]
    end = source_offsets[position + len(normalized_excerpt) - 1] + 1
    start = max(0, start - 40)
    end = min(len(section_text), end + 40)
    while start and not section_text[start - 1].isspace():
        start -= 1
    while end < len(section_text) and not section_text[end].isspace():
        end += 1
    return _normalize(section_text[start:end])


def _drop_unreferenced_citations(result: Any) -> Any:
    if not isinstance(result, dict):
        return result
    referenced = {
        citation_id
        for field in CATEGORY_FIELDS
        for claim in result.get(field, [])
        if isinstance(claim, dict)
        for citation_id in claim.get("citation_ids", [])
        if isinstance(citation_id, str)
    }
    citations = result.get("citations")
    if not isinstance(citations, list):
        return result
    normalized = dict(result)
    normalized["citations"] = [
        citation
        for citation in citations
        if isinstance(citation, dict)
        and citation.get("citation_id") in referenced
    ]
    return normalized


def _normalize(value: str) -> str:
    return " ".join(value.split())
