import hashlib

from app.core.errors import DomainError
from app.models.company_model import Company
from app.supply_chain.schemas import CompanyIdentity, OfficialSourceDocument

PUBLIC_GRAPH_STATUSES = {"completed", "insufficient_evidence"}
STAGE_ERROR_CODES = {
    "collecting": "GRAPH_SOURCE_COLLECTION_FAILED",
    "extracting": "GRAPH_EXTRACTION_FAILED",
    "resolving": "GRAPH_RESOLUTION_FAILED",
    "verifying": "GRAPH_VERIFICATION_FAILED",
    "localizing": "GRAPH_LOCALIZATION_FAILED",
}


def source_fingerprint(sources: list[OfficialSourceDocument]) -> str:
    hashes = "|".join(sorted({source.content_hash for source in sources}))
    return hashlib.sha256(hashes.encode()).hexdigest()


def company_identity(company: Company) -> CompanyIdentity:
    if company.id is None:
        raise DomainError("COMPANY_NOT_FOUND", 404)
    return CompanyIdentity(
        company_id=company.id,
        symbol=company.symbol,
        cik=company.cik,
        legal_name=company.name,
        exchange=company.exchange,
        official_hosts=("sec.gov",),
    )
