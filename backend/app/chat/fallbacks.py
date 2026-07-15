from app.chat.intents import AgentRouteDecision
from app.chat.schemas import AnswerEvidencePack, AnswerPoint, ResearchAnswerPlan
from app.chat.validator import (
    AnswerValidationError,
    normalize_answer_plan,
    validate_answer_plan,
)


def build_evidence_fallback(
    evidence: AnswerEvidencePack,
    locale: str,
) -> ResearchAnswerPlan:
    if not evidence.records:
        plan = _empty_evidence_fallback(evidence, locale)
        validate_answer_plan(plan, evidence, locale=locale)
        return plan

    records = evidence.records[:6]
    first_id = records[0].candidate.evidence_id
    if locale == "zh-CN":
        direct_text = "现有记录支持以下证据摘要。"
        prefix = "证据摘要："
        risk_text = "证据缺失：当前资料只能覆盖部分问题。"
    else:
        direct_text = "The available records support the evidence summary below."
        prefix = "Evidence excerpt: "
        risk_text = "Evidence is missing for part of the requested analysis."
    plan = ResearchAnswerPlan(
        direct_conclusion=AnswerPoint(
            text=direct_text,
            citation_ids=[first_id],
        ),
        key_evidence=[
            AnswerPoint(
                text=f"{prefix}{record.candidate.excerpt}",
                citation_ids=[record.candidate.evidence_id],
            )
            for record in records
        ],
        risks_and_uncertainties=(
            [AnswerPoint(text=risk_text)] if evidence.evidence_gaps else []
        ),
        sources=[],
        evidence_coverage="partial" if evidence.evidence_gaps else "complete",
        web_search_used=evidence.web_search_used,
    )
    plan = normalize_answer_plan(plan, evidence, locale=locale)
    try:
        validate_answer_plan(plan, evidence, locale=locale)
    except AnswerValidationError:
        plan = _minimal_evidence_fallback(evidence, locale)
        validate_answer_plan(plan, evidence, locale=locale)
    return plan


def fast_conversation_route(
    question: str,
    locale: str,
) -> AgentRouteDecision | None:
    normalized = question.strip().casefold().strip("!！?？.。~～ ")
    if normalized not in {"hi", "hello", "hey", "你好", "您好", "嗨", "哈喽"}:
        return None
    response = (
        "你好，我可以帮你研究这家公司的业务、产业链、财报和估值。"
        if locale == "zh-CN"
        else "Hello. I can help research this company's business, supply chain, "
        "filings, and valuation."
    )
    return AgentRouteDecision(
        interaction_mode="conversation",
        is_follow_up=False,
        response=response,
    )


def routing_fallback(
    locale: str,
    *,
    question: str,
    is_follow_up: bool,
) -> AgentRouteDecision:
    if _looks_like_research_question(question):
        return AgentRouteDecision(
            interaction_mode="research",
            is_follow_up=is_follow_up,
            resolved_question=question,
        )
    response = (
        "我暂时无法判断你的研究意图。请明确想研究这家公司的业务、产业链、财报或估值。"
        if locale == "zh-CN"
        else "I could not determine the research intent. Specify whether you want to "
        "study the company's business, supply chain, filings, or valuation."
    )
    return AgentRouteDecision(
        interaction_mode="clarification",
        is_follow_up=is_follow_up,
        response=response,
    )


def _minimal_evidence_fallback(
    evidence: AnswerEvidencePack,
    locale: str,
) -> ResearchAnswerPlan:
    evidence_id = evidence.records[0].candidate.evidence_id
    direct_text = (
        "现有记录可支持一份有限的投研结论。"
        if locale == "zh-CN"
        else "The available record supports a limited research conclusion."
    )
    key_text = (
        "已引用的来源包含与该问题相关的可核验证据。"
        if locale == "zh-CN"
        else "The cited source contains verifiable evidence relevant to the question."
    )
    risk_text = (
        "证据缺失：当前资料只能覆盖部分问题。"
        if locale == "zh-CN"
        else "Evidence is missing for part of the requested analysis."
    )
    return ResearchAnswerPlan(
        direct_conclusion=AnswerPoint(
            text=direct_text,
            citation_ids=[evidence_id],
        ),
        key_evidence=[AnswerPoint(text=key_text, citation_ids=[evidence_id])],
        risks_and_uncertainties=(
            [AnswerPoint(text=risk_text)] if evidence.evidence_gaps else []
        ),
        sources=[evidence_id],
        evidence_coverage="partial" if evidence.evidence_gaps else "complete",
        web_search_used=evidence.web_search_used,
    )


def _empty_evidence_fallback(
    evidence: AnswerEvidencePack,
    locale: str,
) -> ResearchAnswerPlan:
    if locale == "zh-CN":
        direct_text = "证据不足：当前缺少回答这个具体投研问题所需的资料。"
        key_text = "所需证据目前缺失。"
    else:
        direct_text = (
            "Insufficient evidence: source records for this specific research "
            "question are unavailable."
        )
        key_text = "The required evidence is unavailable."
    return ResearchAnswerPlan(
        direct_conclusion=AnswerPoint(text=direct_text),
        key_evidence=[AnswerPoint(text=key_text)],
        risks_and_uncertainties=[],
        sources=[],
        evidence_coverage="insufficient",
        web_search_used=evidence.web_search_used,
    )


def _looks_like_research_question(question: str) -> bool:
    normalized = question.casefold()
    markers = (
        "业务",
        "财报",
        "营收",
        "收入",
        "利润",
        "现金流",
        "估值",
        "市盈率",
        "股价",
        "产业链",
        "上游",
        "下游",
        "business",
        "filing",
        "revenue",
        "earnings",
        "cash flow",
        "valuation",
        "p/e",
        "pe ratio",
        "share price",
        "supply chain",
        "supplier",
        "customer",
    )
    return any(marker in normalized for marker in markers)
