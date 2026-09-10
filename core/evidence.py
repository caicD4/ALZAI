from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Source metadata representing an external webpage or document."""

    source_id: str = Field(..., description="Unique identifier for the source")
    url: str = Field(..., description="Canonical URL of the source")
    domain: str = Field(..., description="Domain name extracted from URL")
    title: str = Field(..., description="Title of the source document")
    published_at: Optional[date] = Field(default=None, description="Publication date if available")
    fetch_id: str = Field(..., description="ID referencing the immutable snapshot fetch")
    content_hash: str = Field(..., description="SHA-256 hash of cleaned source text")
    quality_tier: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Source quality tier (1=primary/official, 5=vendor/promotional)",
    )
    vested_interest: bool = Field(
        default=False,
        description="Flag indicating vendor, promotional, or agency vested interest",
    )


class FetchSnapshot(BaseModel):
    """Immutable snapshot of raw fetched and cleaned source text."""

    fetch_id: str = Field(..., description="Unique identifier for the fetch snapshot")
    url: str = Field(..., description="URL of fetched source")
    cleaned_text: str = Field(..., description="Cleaned readable text extracted from source")
    content_hash: str = Field(..., description="SHA-256 hash of cleaned_text")
    fetched_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when source was fetched",
    )


class NumberFact(BaseModel):
    """Structured representation of a numerical metric or statistic."""

    value: str = Field(..., description="Exact metric value string (e.g., '70-85%' or '11%')")
    unit: Optional[str] = Field(default=None, description="Unit of measurement if applicable")
    denominator: Optional[str] = Field(
        default=None,
        description="Scope or denominator (e.g., 'of surveyed AI projects')",
    )
    timeframe: Optional[str] = Field(default=None, description="Time Period (e.g., '2023 survey')")
    sample: Optional[str] = Field(default=None, description="Sample size or details (e.g., 'n=500 SMBs')")


class EvidenceItem(BaseModel):
    """Verbatim quote card representing an atomic unit of extracted evidence."""

    evidence_id: str = Field(..., description="Unique identifier for the evidence card")
    fetch_id: str = Field(..., description="ID referencing the source snapshot")
    locator: str = Field(..., description="Character span or chunk index locator within source text")
    verbatim_quote: str = Field(..., description="Exact verbatim text quote extracted from source")
    claim_summary: str = Field(..., description="Normalized one-sentence summary of the quote")
    evidence_type: Literal[
        "statistic",
        "anecdote",
        "expert_opinion",
        "definition",
        "causal_claim",
        "prediction",
        "promotional",
    ] = Field(..., description="Categorized type of evidence")
    attribution: Optional[str] = Field(
        default=None,
        description="Primary or secondary attribution (e.g., 'secondary citation of Gartner 2019')",
    )
    numbers: List[NumberFact] = Field(
        default_factory=list,
        description="Structured list of numerical facts contained in the evidence",
    )
    data_date: Optional[date] = Field(
        default=None,
        description="Date when the underlying data was originally collected",
    )
    quote_verified: bool = Field(
        default=False,
        description="Result of deterministic containment check against source text",
    )


class Finding(BaseModel):
    """Synthesized finding derived from multiple verified evidence items."""

    finding_id: str = Field(..., description="Unique identifier for the finding")
    sub_question_id: str = Field(..., description="ID of the research question addressed")
    statement: str = Field(..., description="Synthesized finding statement")
    evidence_ids: List[str] = Field(
        ..., description="List of supporting evidence_id values"
    )
    status: Literal["consensus", "contested", "single_source", "gap"] = Field(
        default="single_source",
        description="Consensus status of this finding across evidence",
    )


class ClaimCheck(BaseModel):
    """Fact-check verdict evaluating a written claim against evidence."""

    claim: str = Field(..., description="The atomic claim text extracted from content")
    claim_type: Literal["factual", "interpretive"] = Field(
        ..., description="Whether claim is empirical fact or author interpretation"
    )
    verdict: Literal["supported", "partial", "unsupported"] = Field(
        ..., description="Entailment check verdict against evidence store"
    )
    evidence_ids: List[str] = Field(
        default_factory=list,
        description="Matching evidence IDs evaluated during check",
    )
    note: str = Field(..., description="Explanation or required revision notes")
