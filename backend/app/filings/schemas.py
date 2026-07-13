from dataclasses import dataclass

from pydantic import BaseModel

from app.models.research_model import Filing, FilingArtifact, FilingSection


class ParsedSection(BaseModel):
    heading: str
    source_anchor: str
    ordinal: int
    text: str


@dataclass(frozen=True)
class StoredFiling:
    filing: Filing
    artifact: FilingArtifact
    sections: tuple[FilingSection, ...]
