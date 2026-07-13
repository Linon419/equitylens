from app.filings.parser import parse_research_sections


def test_parser_extracts_business_risk_and_revenue_sections(
    filing_html: bytes,
) -> None:
    sections = parse_research_sections(filing_html)

    assert [section.heading for section in sections] == [
        "Item 1. Business",
        "Item 1A. Risk Factors",
        "Net Sales Disaggregated by Products and Services",
    ]
    assert sections[0].source_anchor == "item-1-business"
    assert "supply" in sections[1].text.lower()
    assert "ignore previous instructions" not in " ".join(
        section.text.lower() for section in sections
    )


def test_parser_enforces_per_section_and_total_text_bounds() -> None:
    html = b"""
    <h1>Item 1. Business</h1><p>abcdefghij</p>
    <h1>Item 1A. Risk Factors</h1><p>klmnopqrst</p>
    """

    sections = parse_research_sections(
        html,
        max_section_chars=7,
        max_total_chars=10,
    )

    assert [len(section.text) for section in sections] == [7, 3]
