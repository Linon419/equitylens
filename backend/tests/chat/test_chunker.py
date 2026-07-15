from dataclasses import dataclass

from app.chat.chunker import chunk_section


@dataclass
class Section:
    heading: str = "Item 1. Business"
    source_anchor: str = "item-1"
    text: str = ""


class WhitespaceCodec:
    def encode(self, value: str) -> list[int]:
        if not value:
            return []
        return [int(token) for token in value.split()]

    def decode(self, tokens: list[int]) -> str:
        return " ".join(str(token) for token in tokens)


def token_text(count: int) -> str:
    return " ".join(str(index) for index in range(count))


def test_chunker_rebalances_short_tail_and_preserves_overlap() -> None:
    codec = WhitespaceCodec()
    chunks = chunk_section(
        Section(text=token_text(710)),
        token_codec=codec,
        target=700,
        overlap=100,
        minimum_final=120,
    )

    assert [chunk.token_count for chunk in chunks] == [690, 120]
    assert codec.encode(chunks[0].text)[-100:] == codec.encode(chunks[1].text)[:100]
    assert all(chunk.token_count <= 700 for chunk in chunks)


def test_chunker_keeps_short_single_section_and_stable_metadata() -> None:
    codec = WhitespaceCodec()
    section = Section(text=token_text(80))

    first = chunk_section(
        section,
        token_codec=codec,
        target=700,
        overlap=100,
        minimum_final=120,
    )
    second = chunk_section(
        section,
        token_codec=codec,
        target=700,
        overlap=100,
        minimum_final=120,
    )

    assert first == second
    assert len(first) == 1
    assert first[0].ordinal == 0
    assert first[0].token_count == 80
    assert first[0].text == section.text
    assert first[0].embedding_text.startswith("Item 1. Business\nitem-1\n")
    assert len(first[0].content_hash) == 64


def test_chunker_rejects_invalid_bounds() -> None:
    codec = WhitespaceCodec()
    section = Section(text=token_text(10))

    for target, overlap, minimum in ((0, 0, 1), (100, 100, 1), (100, 10, 101)):
        try:
            chunk_section(
                section,
                token_codec=codec,
                target=target,
                overlap=overlap,
                minimum_final=minimum,
            )
        except ValueError:
            continue
        raise AssertionError("invalid chunk bounds were accepted")
