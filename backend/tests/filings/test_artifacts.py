import pytest

from app.core.errors import DomainError
from app.filings.artifacts import compress_filing, decompress_filing


def test_artifact_round_trips_compressed_html() -> None:
    artifact = compress_filing(b"<html><body>Business</body></html>")

    assert artifact.uncompressed_size == 34
    assert artifact.compressed_size == len(artifact.compressed_body)
    assert decompress_filing(artifact.compressed_body).startswith(b"<html>")


def test_artifact_rejects_oversized_filings() -> None:
    with pytest.raises(DomainError) as error:
        compress_filing(b"x" * 101, max_bytes=100)

    assert error.value.code == "FILING_TOO_LARGE"
