from app.chat.market_analysis_skills import (
    MARKET_ANALYSIS_SKILLS,
    market_analysis_playbook,
)


def test_market_analysis_catalog_contains_all_upstream_skills() -> None:
    assert set(MARKET_ANALYSIS_SKILLS) == {
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
    }


def test_playbook_contains_only_selected_market_analysis_skills() -> None:
    prompt = market_analysis_playbook(["company-valuation", "stock-liquidity"])

    assert "company-valuation" in prompt
    assert "stock-liquidity" in prompt
    assert "earnings-preview" not in prompt
    assert "DCF" in prompt
    assert "Amihud" in prompt
    assert "research and educational" in prompt
