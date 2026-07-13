import re
from collections.abc import Iterator

from bs4 import BeautifulSoup, NavigableString, Tag

from app.filings.schemas import ParsedSection

SECTION_PATTERNS = (
    r"^item\s+1[\.:\-\s]+business$",
    r"^item\s+1a[\.:\-\s]+risk factors$",
    r"net sales.*products.*services",
    r"segment information",
    r"major customers?",
    r"supplier concentration",
)
COMPILED_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE) for pattern in SECTION_PATTERNS
)
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}


def parse_research_sections(
    html: bytes,
    *,
    max_section_chars: int = 120_000,
    max_total_chars: int = 300_000,
) -> list[ParsedSection]:
    soup = BeautifulSoup(html, "html.parser")
    _remove_untrusted_nodes(soup)
    headings = [tag for tag in soup.find_all(True) if _matches_section(tag)]
    sections: list[ParsedSection] = []
    total_chars = 0

    for heading in headings:
        if total_chars >= max_total_chars:
            break
        available = min(max_section_chars, max_total_chars - total_chars)
        text = _section_text(heading)[:available]
        if not text:
            continue
        title = _normalized_text(heading)
        ordinal = len(sections)
        sections.append(
            ParsedSection(
                heading=title,
                source_anchor=_source_anchor(heading, title, ordinal),
                ordinal=ordinal,
                text=text,
            )
        )
        total_chars += len(text)
    return sections


def _remove_untrusted_nodes(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript", "ix:hidden"]):
        tag.decompose()
    for tag in soup.find_all(True):
        style = str(tag.get("style", "")).replace(" ", "").lower()
        if (
            tag.has_attr("hidden")
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            tag.decompose()


def _matches_section(tag: Tag) -> bool:
    text = _normalized_text(tag)
    if not text or len(text) > 200:
        return False
    return any(pattern.search(text) for pattern in COMPILED_PATTERNS)


def _is_heading_boundary(tag: Tag) -> bool:
    return tag.name in HEADING_TAGS or _matches_section(tag)


def _section_text(heading: Tag) -> str:
    fragments: list[str] = []
    for element in _following_elements(heading):
        if isinstance(element, Tag) and _is_heading_boundary(element):
            break
        if not isinstance(element, NavigableString):
            continue
        if heading in element.parents:
            continue
        value = " ".join(str(element).split())
        if value:
            fragments.append(value)
    return " ".join(fragments)


def _following_elements(heading: Tag) -> Iterator[Tag | NavigableString]:
    yield from heading.next_elements


def _normalized_text(tag: Tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def _source_anchor(heading: Tag, title: str, ordinal: int) -> str:
    existing = str(heading.get("id", "")).strip()
    if existing:
        return existing[:255]
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return f"section-{ordinal + 1}-{slug}"[:255]
