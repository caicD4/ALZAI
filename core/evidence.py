from datetime import date, datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Source metadata representing an external webpage or document."""

    source_id: str = Field(..., description="Unique identifier for the source")
    url: str = Field(..., description="Original URL of the source")
    canonical_url: str = Field(default="", description="Normalized canonical URL")
    domain: str = Field(..., description="Domain name extracted from URL")
    title: str = Field(..., description="Title of the source document")
    query: Optional[str] = Field(default=None, description="Originating search query that discovered this source")
    serp_rank: Optional[int] = Field(default=None, description="1-indexed rank in search engine results")
    published_at: Optional[date] = Field(default=None, description="Publication date if available")
    fetch_id: str = Field(..., description="ID referencing the immutable snapshot fetch")
    content_hash: str = Field(..., description="SHA-256 hash of cleaned source text")
    quality_tier: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Source quality tier heuristic (1=primary/official, 5=vendor/promotional)",
    )
    vested_interest: bool = Field(
        default=False,
        description="Flag indicating vendor, promotional, or agency vested interest",
    )

    def model_post_init(self, __context) -> None:
        if not self.canonical_url:
            self.canonical_url = self.url



class FetchSnapshot(BaseModel):
    """Immutable snapshot of raw fetched and cleaned source text."""

    fetch_id: str = Field(..., description="Unique identifier for the fetch snapshot")
    url: str = Field(..., description="Original requested URL")
    final_url: str = Field(default="", description="Final URL after following HTTP redirects")
    title: Optional[str] = Field(default=None, description="Document title extracted from page header/HTML")
    cleaned_text: str = Field(..., description="Cleaned readable text extracted from source")
    content_hash: str = Field(..., description="SHA-256 hash of cleaned_text")
    content_type: str = Field(default="text/html", description="MIME content type of fetched response")
    http_status: int = Field(default=200, description="HTTP status code of fetch response")
    fetched_at: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when source was fetched",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if fetch or cleaning encountered a failure",
    )

    def model_post_init(self, __context) -> None:
        if not self.final_url:
            self.final_url = self.url



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


INSIGHT_TYPES = (
    "research_finding",
    "statistic",
    "expert_claim",
    "company_claim",
    "example",
    "case_study",
    "anecdote",
    "mechanism",
    "opinion",
    "prediction",
    "marketing_claim",
    "definition",
    "trend",
    "limitation",
    "contradiction",
    "causal_claim",
    "expert_opinion",
    "promotional",
)

SOURCE_ROLES = (
    "evidence",
    "context",
    "discovery",
    "primary_source",
    "expert_perspective",
    "example",
    "company_claim",
    "anecdotal",
    "marketing",
)


class EvidenceItem(BaseModel):
    """Verbatim insight card representing an atomic unit of extracted research material."""

    evidence_id: str = Field(..., description="Unique identifier for the evidence/insight card")
    fetch_id: str = Field(..., description="ID referencing the source snapshot")
    locator: str = Field(..., description="Character span or chunk index locator within source text")
    verbatim_quote: str = Field(..., description="Exact verbatim text quote extracted from source")
    claim_summary: str = Field(..., description="Normalized one-sentence summary of the quote")
    insight_type: str = Field(
        default="research_finding",
        description="Categorized insight type (e.g., research_finding, statistic, expert_claim, company_claim, example, anecdote, mechanism, opinion, prediction, marketing_claim, definition, trend, limitation, contradiction)",
    )
    evidence_type: Optional[str] = Field(
        default=None,
        description="Legacy evidence type alias mapped to insight_type for backward compatibility",
    )
    source_role: str = Field(
        default="evidence",
        description="Architectural role of source material (e.g. evidence, context, discovery, primary_source, expert_perspective, example, company_claim, anecdotal, marketing)",
    )
    source_tier: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Source quality tier heuristic (1=primary/academic, 5=marketing/blog)",
    )
    attribution: Optional[str] = Field(
        default=None,
        description="Explicit entity/author attribution for the claim (e.g., 'Gartner 2023 survey', 'Company X spokesperson')",
    )
    suggested_writer_phrasing: Optional[str] = Field(
        default=None,
        description="Recommended phrasing for future content writer that preserves epistemic and attribution boundaries without upgrading claim strength",
    )
    limitations: Optional[str] = Field(
        default=None,
        description="Explicit caveats, sample limits, methodological bounds, or study disclaimers in source text",
    )
    substantive: bool = Field(
        default=True,
        description="Whether material contains substantive research value (False for generic marketing fluff or intros)",
    )
    relevance_explanation: Optional[str] = Field(
        default=None,
        description="Explicit explanation of why this insight answers or informs the research question",
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

    def model_post_init(self, __context) -> None:
        if self.evidence_type and not self.insight_type:
            self.insight_type = self.evidence_type
        elif self.insight_type and not self.evidence_type:
            self.evidence_type = self.insight_type


# Type alias for the Insight / Claim Interpretation Layer
ResearchInsight = EvidenceItem


def __getattr__(name: str):
    if name == "Finding":
        from core.synthesis import Finding
        return Finding
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")



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
