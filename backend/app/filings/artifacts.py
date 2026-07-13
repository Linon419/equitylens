import gzip
import hashlib
from dataclasses import dataclass

from app.core.errors import DomainError

DEFAULT_MAX_FILING_BYTES = 15 * 1024 * 1024


@dataclass(frozen=True)
class CompressedFiling:
    compressed_body: bytes
    compressed_size: int
    uncompressed_size: int
    sha256: str


def compress_filing(
    body: bytes,
    *,
    max_bytes: int = DEFAULT_MAX_FILING_BYTES,
) -> CompressedFiling:
    if len(body) > max_bytes:
        raise DomainError("FILING_TOO_LARGE", 413)
    compressed = gzip.compress(body, compresslevel=6, mtime=0)
    return CompressedFiling(
        compressed_body=compressed,
        compressed_size=len(compressed),
        uncompressed_size=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
    )


def decompress_filing(compressed_body: bytes) -> bytes:
    try:
        return gzip.decompress(compressed_body)
    except (OSError, EOFError) as error:
        raise DomainError("FILING_ARTIFACT_INVALID", 500) from error
