import hashlib
from dataclasses import dataclass
from typing import Protocol


class TokenCodec(Protocol):
    def encode(self, value: str) -> list[int]: ...

    def decode(self, tokens: list[int]) -> str: ...


class FilingSectionLike(Protocol):
    heading: str
    source_anchor: str
    text: str


@dataclass(frozen=True)
class SectionChunk:
    ordinal: int
    text: str
    embedding_text: str
    token_count: int
    content_hash: str


def chunk_section(
    section: FilingSectionLike,
    *,
    token_codec: TokenCodec,
    target: int = 700,
    overlap: int = 100,
    minimum_final: int = 120,
) -> list[SectionChunk]:
    _validate_bounds(target, overlap, minimum_final)
    tokens = token_codec.encode(section.text)
    if not tokens:
        return []
    boundaries = _chunk_boundaries(
        len(tokens),
        target=target,
        overlap=overlap,
        minimum_final=minimum_final,
    )
    result = []
    for ordinal, (start, end) in enumerate(boundaries):
        text = token_codec.decode(tokens[start:end])
        result.append(
            SectionChunk(
                ordinal=ordinal,
                text=text,
                embedding_text=(
                    f"{section.heading}\n{section.source_anchor}\n{text}"
                ),
                token_count=end - start,
                content_hash=hashlib.sha256(text.encode()).hexdigest(),
            )
        )
    return result


def _chunk_boundaries(
    length: int,
    *,
    target: int,
    overlap: int,
    minimum_final: int,
) -> list[tuple[int, int]]:
    if length <= target:
        return [(0, length)]
    boundaries: list[tuple[int, int]] = []
    start = 0
    while length - start > target:
        end = start + target
        next_start = end - overlap
        if length - next_start < minimum_final:
            next_start = length - minimum_final
            end = next_start + overlap
        boundaries.append((start, end))
        start = next_start
    boundaries.append((start, length))
    return boundaries


def _validate_bounds(target: int, overlap: int, minimum_final: int) -> None:
    if target < 1:
        raise ValueError("target must be positive")
    if overlap < 0 or overlap >= target:
        raise ValueError("overlap must be between zero and target")
    if minimum_final < 1 or minimum_final > target:
        raise ValueError("minimum_final must be between one and target")
