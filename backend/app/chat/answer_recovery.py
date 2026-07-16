import json
from typing import Any

from app.chat.schemas import AnswerEvidencePack, ResearchAnswerPlan


def recover_research_answer_plan(
    raw_content: Any,
    evidence: AnswerEvidencePack,
) -> ResearchAnswerPlan:
    payload = _decode_json_object(_content_text(raw_content))
    direct_conclusion = _normalize_point(payload.get("direct_conclusion"))
    if direct_conclusion is None:
        raise ValueError("direct conclusion is missing")

    key_evidence = _normalize_points(payload.get("key_evidence"), limit=8)
    if not key_evidence:
        key_evidence = [direct_conclusion.copy()]

    normalized = {
        "direct_conclusion": direct_conclusion,
        "key_evidence": key_evidence,
        "risks_and_uncertainties": _normalize_points(
            payload.get("risks_and_uncertainties"),
            limit=6,
        ),
        "sources": _normalize_string_list(payload.get("sources"), limit=24),
        "evidence_coverage": _normalize_coverage(
            payload.get("evidence_coverage"),
            has_evidence=bool(evidence.records),
        ),
        "web_search_used": evidence.web_search_used,
    }
    return ResearchAnswerPlan.model_validate(normalized)


def raw_message_content(raw: Any) -> Any:
    if isinstance(raw, dict):
        return raw.get("content")
    return getattr(raw, "content", None)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        raise ValueError("raw model content is unavailable")
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and isinstance(block.get("text"), str):
            parts.append(block["text"])
    if not parts:
        raise ValueError("raw model content is unavailable")
    return "".join(parts)


def _decode_json_object(content: str) -> dict[str, Any]:
    stripped = content.strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("model content does not contain a JSON object")
    payload = json.loads(stripped[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("model JSON must be an object")
    return payload


def _normalize_points(value: Any, *, limit: int) -> list[dict[str, Any]]:
    candidates = value if isinstance(value, list) else [value]
    points: list[dict[str, Any]] = []
    for candidate in candidates:
        point = _normalize_point(candidate)
        if point is not None:
            points.append(point)
        if len(points) == limit:
            break
    return points


def _normalize_point(value: Any) -> dict[str, Any] | None:
    if isinstance(value, str):
        text = value.strip()
        return _point_payload(text, [], False) if text else None
    if not isinstance(value, dict):
        return None
    text = value.get("text")
    if not isinstance(text, str) or not text.strip():
        return None
    citation_ids = _normalize_string_list(value.get("citation_ids"), limit=8)
    inference = _normalize_boolean(value.get("inference"))
    return _point_payload(text.strip(), citation_ids, inference)


def _point_payload(
    text: str,
    citation_ids: list[str],
    inference: bool,
) -> dict[str, Any]:
    return {
        "text": text,
        "citation_ids": citation_ids,
        "inference": inference,
    }


def _normalize_string_list(value: Any, *, limit: int) -> list[str]:
    candidates = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        item = candidate.strip()
        if item and item not in normalized:
            normalized.append(item)
        if len(normalized) == limit:
            break
    return normalized


def _normalize_boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "y", "是"}
    return False


def _normalize_coverage(value: Any, *, has_evidence: bool) -> str:
    if value in {"complete", "partial", "insufficient"}:
        return value
    return "partial" if has_evidence else "insufficient"
