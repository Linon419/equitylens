from app.chat.intents import AgentRouteDecision
from app.chat.market_analysis_skills import infer_market_analysis_skills


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


def fast_company_overview_route(
    question: str,
    *,
    company_name: str,
    symbol: str,
    locale: str,
) -> AgentRouteDecision | None:
    normalized = question.strip().casefold().strip("!！?？.。~～ ")
    overview_questions = {
        "这个公司怎么样",
        "这家公司怎么样",
        "这个企业怎么样",
        "这家企业怎么样",
        "how is this company",
        "how is the company",
        "how's this company",
        "what do you think of this company",
        "tell me about this company",
    }
    if normalized not in overview_questions:
        return None
    resolved_question = (
        f"请综合分析 {company_name}（{symbol}）的核心业务、在产业链中的位置、"
        "近期财务表现、当前估值水平和主要风险，并给出适合个人投资者理解的结论。"
        if locale == "zh-CN"
        else f"Analyze {company_name} ({symbol}) across its core business, "
        "supply-chain "
        "position, recent financial performance, current valuation, and key risks. "
        "Give a conclusion suitable for an individual investor."
    )
    return AgentRouteDecision(
        interaction_mode="research",
        is_follow_up=False,
        analysis_skills=[],
        resolved_question=resolved_question,
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
            analysis_skills=infer_market_analysis_skills(question),
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
