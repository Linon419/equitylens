from typing import Literal

MarketAnalysisSkill = Literal[
    "company-valuation",
    "earnings-preview",
    "earnings-recap",
    "estimate-analysis",
    "etf-premium",
    "options-payoff",
    "saas-valuation-compression",
    "sepa-strategy",
    "stock-correlation",
    "stock-liquidity",
    "yfinance-data",
]

MARKET_ANALYSIS_SKILLS: tuple[MarketAnalysisSkill, ...] = (
    "company-valuation",
    "earnings-preview",
    "earnings-recap",
    "estimate-analysis",
    "etf-premium",
    "options-payoff",
    "saas-valuation-compression",
    "sepa-strategy",
    "stock-correlation",
    "stock-liquidity",
    "yfinance-data",
)

_SKILL_SUMMARIES = {
    "company-valuation": "DCF, relative valuation, SOTP, sensitivity and scenarios",
    "earnings-preview": "upcoming earnings expectations and beat/miss history",
    "earnings-recap": "reported results, surprises, margins and price reaction",
    "estimate-analysis": "analyst estimates, revisions, growth and accuracy",
    "etf-premium": "ETF market-price premium or discount to NAV",
    "options-payoff": "option-strategy payoff, breakevens and bounded loss",
    "saas-valuation-compression": "SaaS ARR multiple changes and cause attribution",
    "sepa-strategy": "Minervini SEPA trend, pattern, entry and risk sizing",
    "stock-correlation": "return correlation, beta, regimes and pair stability",
    "stock-liquidity": "spread, volume, turnover, Amihud and market impact",
    "yfinance-data": "quotes, history, statements, actions, options and ownership",
}

_SKILL_PLAYBOOKS: dict[MarketAnalysisSkill, str] = {
    "company-valuation": """Triangulate value with DCF and relative multiples; add
SOTP only when filing evidence identifies economically distinct segments. State every
forecast assumption, bridge enterprise value to equity value, and show Bull/Base/Bear
cases plus a WACC x terminal-growth sensitivity range. Skip inapplicable multiples for
negative earnings or EBITDA. Treat sensitivity as more decision-useful than a single
price target and label confidence from the available inputs.""",
    "earnings-preview": """Build a pre-earnings brief around the next report date,
consensus EPS and revenue, estimate ranges and analyst counts, the last four surprise
results, revision direction, and the operating metrics most likely to move the thesis.
Separate published consensus from your interpretation. Explain that a likely beat can
already be reflected in price and identify the expectation with the highest
uncertainty.""",
    "earnings-recap": """Compare reported EPS and revenue with consensus, calculate
the surprise percentages when both values exist, and describe the first full-session
price reaction. Compare the latest quarter with recent revenue, gross-margin,
operating-margin and EPS trends. Identify guidance or estimate changes through current
web evidence and keep after-hours moves separate from regular-session moves.""",
    "estimate-analysis": """Compare current-quarter, next-quarter, current-year and
next-year EPS and revenue estimates. Assess 7/30/60/90-day revisions, upward versus
downward breadth, implied growth and historical surprise accuracy. Explain whether
expectations are rising, falling or dispersing, and identify small analyst samples and
stale periods as lower-confidence evidence.""",
    "etf-premium": """Calculate premium/discount as (market price - NAV) / NAV.
Compare the result with the bid-ask spread and the ETF category's normal range. For a
large move, separate NAV-driven return from excess premium and discuss
creation/redemption,
market hours, stale NAV, liquidity and options positioning. Avoid presenting intraday
indicative values as official end-of-day NAV.""",
    "options-payoff": """Extract each option leg, type, strike, premium, quantity,
expiry and long/short direction. Ask one clarification when a required leg is missing.
Calculate expiry payoff, net debit or credit, breakevens, maximum profit and maximum
loss;
use theoretical value only when IV, time and rates are available. State assignment,
liquidity, volatility and early-exercise risks. The current chat output is text and
tables,
so describe the payoff curve with key price points.""",
    "saas-valuation-compression": """Use web evidence to build a dated series of
funding valuations and ARR values, then calculate EV/ARR or valuation/ARR consistently.
Attribute changes among growth deceleration, margin or retention changes, interest-rate
regime, competitive position and narrative premium. Cite every private-market value and
ARR observation, distinguish reported from estimated figures, and compare with relevant
public SaaS multiples when available.""",
    "sepa-strategy": """Evaluate the four-stage cycle, the eight-condition trend
template, EPS and revenue acceleration, volatility-contraction quality, pivot, breakout
volume and market regime. Report each trend-template condition as pass, fail or
unavailable.
Calculate a 0-5% buy zone only from an evidenced pivot. Position sizing requires account
equity and risk percentage; show the formula and downside to the stop as a scenario
rather
than a recommendation.""",
    "stock-correlation": """Use adjusted daily returns over a stated default 1-year
lookback. Report Pearson correlation, beta, R-squared and 60-day rolling stability for
explicit pairs; use a relevant peer universe for discovery. Distinguish correlation from
causation and explain regime sensitivity, overlapping business exposure and the limits
of pair-trading inference. Name missing comparison tickers when the request is
underspecified.""",
    "stock-liquidity": """Assess quoted bid-ask spread, 20/60-day share and dollar
volume, relative volume, turnover and the Amihud illiquidity ratio. For an order-size
question, state order participation as a share of ADV and label square-root market
impact
as an estimate. Explain that Yahoo provides top-of-book and daily proxies rather than a
full order book, and flag pre-market, after-hours and stale quote effects.""",
    "yfinance-data": """Select only the Yahoo fields needed for the question. Always
state ticker, units, currency, observation period and retrieval time. Prefer adjusted
prices
for return calculations and reported statement periods for fundamentals. Treat missing
fields as unavailable, preserve the provider's period labels, and cross-check material
investment decisions with SEC filings or company investor-relations sources.""",
}

_INFERENCE_TRIGGERS: tuple[tuple[MarketAnalysisSkill, tuple[str, ...]], ...] = (
    ("company-valuation", ("dcf", "fair value", "intrinsic value", "估值", "合理价")),
    ("earnings-preview", ("earnings preview", "reports next", "财报预期", "财报前")),
    ("earnings-recap", ("earnings recap", "beat earnings", "财报复盘", "业绩复盘")),
    (
        "estimate-analysis",
        ("estimate revision", "consensus estimate", "预期修正", "一致预期"),
    ),
    ("etf-premium", ("premium to nav", "discount to nav", "etf 溢价", "etf 折价")),
    (
        "options-payoff",
        ("option payoff", "call spread", "put spread", "期权收益", "盈亏图"),
    ),
    (
        "saas-valuation-compression",
        ("valuation compression", "arr multiple", "估值压缩"),
    ),
    ("sepa-strategy", ("sepa", "minervini", "vcp", "趋势模板")),
    ("stock-correlation", ("correlation", "pair trading", "相关性", "对冲标的")),
    ("stock-liquidity", ("liquidity", "bid-ask", "amihud", "流动性", "买卖价差")),
    ("yfinance-data", ("yfinance", "dividend history", "options chain", "雅虎数据")),
)


def market_analysis_catalog() -> str:
    return "\n".join(
        f"- {name}: {_SKILL_SUMMARIES[name]}" for name in MARKET_ANALYSIS_SKILLS
    )


def market_analysis_playbook(skills: list[MarketAnalysisSkill]) -> str:
    unique = list(dict.fromkeys(skills))
    sections = [f"## {name}\n{_SKILL_PLAYBOOKS[name]}" for name in unique]
    body = "\n\n".join(sections)
    return f"""<market_analysis_playbooks>
These trusted workflows are adapted for EquityLens from finance-market-analysis.
Use only the selected workflows and only supplied evidence. Mark missing inputs,
calculation assumptions, data dates, and provider limitations. All outputs are for
research and educational use and do not constitute financial advice.

{body}
</market_analysis_playbooks>"""


def infer_market_analysis_skills(question: str) -> list[MarketAnalysisSkill]:
    normalized = question.casefold()
    selected = [
        skill
        for skill, triggers in _INFERENCE_TRIGGERS
        if any(trigger in normalized for trigger in triggers)
    ]
    return selected[:3]
