from datetime import UTC, datetime
from typing import Any

from app.core.errors import DomainError
from app.providers.sec import FilingReference

ARCHIVE_URL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
)


def latest_10k(cik: str, payload: dict[str, Any]) -> FilingReference:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        raise DomainError("TEN_K_NOT_FOUND", 404)

    columns = {
        name: recent.get(name, [])
        for name in (
            "accessionNumber",
            "filingDate",
            "reportDate",
            "form",
            "primaryDocument",
        )
    }
    if not all(isinstance(values, list) for values in columns.values()):
        raise DomainError("SEC_SUBMISSIONS_INVALID", 502)

    references = []
    for values in zip(*columns.values(), strict=False):
        row = dict(zip(columns, values, strict=True))
        if row["form"] != "10-K":
            continue
        reference = _to_reference(cik, row)
        if reference is not None:
            references.append(reference)
    if not references:
        raise DomainError("TEN_K_NOT_FOUND", 404)
    return max(references, key=lambda filing: filing.filed_at)


def _to_reference(
    cik: str,
    row: dict[str, Any],
) -> FilingReference | None:
    try:
        numeric_cik = str(int(cik))
        accession_number = str(row["accessionNumber"])
        compact_accession = accession_number.replace("-", "")
        primary_document = str(row["primaryDocument"])
        filed_at = datetime.fromisoformat(str(row["filingDate"])).replace(
            tzinfo=UTC
        )
        report_date = str(row["reportDate"])
    except (KeyError, TypeError, ValueError):
        return None
    return FilingReference(
        accession_number=accession_number,
        form="10-K",
        filed_at=filed_at,
        report_date=report_date,
        primary_document=primary_document,
        source_url=ARCHIVE_URL.format(
            cik=numeric_cik,
            accession=compact_accession,
            document=primary_document,
        ),
    )
