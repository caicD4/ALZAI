from datetime import datetime
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field

from core.evidence import EvidenceItem, ResearchInsight


class Finding(BaseModel):
    """Synthesized finding derived from multiple verified research insights."""

    finding_id: str = Field(..., description="Unique identifier for the finding (e.g. 'find-1')")
    topic_area: str = Field(default="", description="Topic area or sub-question area addressed")
    sub_question_id: Optional[str] = Field(default=None, description="ID of research question addressed if applicable")
    statement: str = Field(..., description="Synthesized finding statement")
    status: Literal[
        "supported",
        "mixed",
        "contested",
        "limited",
        "unclear",
        "single_source",
        "consensus",
    ] = Field(
        default="supported",
        description="Epistemic consensus/support status of this finding across evidence",
    )
    reasoning: str = Field(default="Synthesized from evidence.", description="Explicit explanation of WHY this status was determined")
    supporting_insight_ids: List[str] = Field(default_factory=list, description="List of supporting ResearchInsight IDs")
    contradicting_insight_ids: List[str] = Field(default_factory=list, description="List of contradicting or limiting ResearchInsight IDs")
    evidence_ids: List[str] = Field(default_factory=list, description="Legacy list of all evidence_ids (supporting + contradicting)")
    source_count: int = Field(default=1, description="Total number of insights referencing this finding")
    independent_sources_count: int = Field(default=1, description="Count of independent sources (domain/author level) supporting this finding")

    def model_post_init(self, __context) -> None:
        if not self.evidence_ids:
            self.evidence_ids = list(set(self.supporting_insight_ids + self.contradicting_insight_ids))


class ClaimMapEntry(BaseModel):
    """Atomic claim entry within the ClaimMap."""

    claim_text: str = Field(..., description="The atomic claim statement")
    category: Literal["safe", "qualified", "unsupported", "contradicted"] = Field(
        ..., description="Category classification: safe, qualified, unsupported, contradicted"
    )
    reasoning: str = Field(..., description="Explanation of why claim is categorized this way")
    required_attribution_or_caveat: Optional[str] = Field(
        default=None, description="Mandatory attribution or qualification phrasing for writers"
    )
    supporting_insight_ids: List[str] = Field(default_factory=list)


class ClaimMap(BaseModel):
    """Structured map of claims to guide the writer.

    This is a WRITING GUIDE, not a gate. It tells the writer which claims are
    grounded in retrieved sources versus which must be framed as opinion,
    attribution, or critical commentary. It NEVER blocks content creation.
    """

    safe_claims: List[ClaimMapEntry] = Field(
        default_factory=list, description="Claims grounded in retrieved sources the writer can state directly"
    )
    qualified_claims: List[ClaimMapEntry] = Field(
        default_factory=list, description="Claims requiring specific attribution or framing (e.g. 'critics say...', 'reported...')"
    )
    unsupported_claims: List[ClaimMapEntry] = Field(
        default_factory=list, description="Claims NOT grounded in retrieved sources — writer must frame as opinion/commentary, not fact"
    )
    contradicted_claims: List[ClaimMapEntry] = Field(
        default_factory=list, description="Claims for which retrieved sources present conflicting accounts — writer should acknowledge the dispute"
    )
    content_gaps: List[str] = Field(
        default_factory=list, description="What the retrieved research did NOT cover — writers can explore these creatively"
    )


class ContentAngle(BaseModel):
    """A compelling content angle grounded in synthesized research."""

    angle_id: str = Field(..., description="Unique identifier for angle")
    angle_title: str = Field(..., description="Catchy title or headline for the angle")
    central_thesis: str = Field(..., description="Core thesis or takeaway statement")
    why_interesting: str = Field(..., description="Why this angle resonates with readers")
    supporting_findings: List[str] = Field(default_factory=list, description="Key finding statements supporting this angle")
    counterpoints: List[str] = Field(default_factory=list, description="Nuances or counterarguments to address")
    intended_audience: str = Field(..., description="Target audience segment")
    suitable_platform: str = Field(..., description="Platform fit (e.g. LinkedIn, Blog, X/Twitter, Newsletter)")
    distinctive_angle: str = Field(
        default="",
        description="What makes this angle original / a content gap others are not covering",
    )


class ContentStrategy(BaseModel):
    """Strategic blueprint for generating platform-adapted content."""

    topic: str = Field(..., description="User's original research topic")
    content_type: str = Field(..., description="Target format (e.g. linkedin_post, blog_article, tweet_thread)")
    platform: str = Field(..., description="Target platform (e.g. LinkedIn, Substack, X/Twitter)")
    audience: str = Field(..., description="Target audience profile")
    objective: str = Field(..., description="Content objective (e.g., educate, challenge_assumption, inspire)")
    selected_angle: ContentAngle = Field(..., description="The chosen ContentAngle for writing")
    thesis: str = Field(..., description="Core thesis statement for the post")
    hook_direction: str = Field(..., description="Suggested hook direction or opening line concept")
    key_points: List[str] = Field(..., description="Main outline body points")
    claims_to_include: List[str] = Field(..., description="Safe and qualified claims to present")
    claims_to_avoid: List[str] = Field(..., description="Unsupported or contradicted claims to explicitly avoid")
    evidence_to_reference: List[str] = Field(..., description="Key statistics, quotes, or study references to cite")
    counterpoints: List[str] = Field(..., description="Nuances or caveats to include for intellectual honesty")
    desired_takeaway: str = Field(..., description="What the reader should remember/action")


class ResearchBrief(BaseModel):
    """Comprehensive synthesized model of a topic derived from extracted research insights."""

    brief_id: str = Field(..., description="Unique identifier for research brief")
    topic: str = Field(..., description="Topic or prompt being researched")
    user_request_summary: str = Field(..., description="Summary of user request goals and format")
    findings: List[Finding] = Field(default_factory=list, description="Synthesized findings grouping insights")
    claim_map: ClaimMap = Field(..., description="Structured claim map (safe, qualified, unsupported, contradicted)")
    key_mechanisms: List[str] = Field(default_factory=list, description="Key explanations or biological/technical mechanisms")
    case_studies_and_examples: List[str] = Field(default_factory=list, description="Useful examples, case studies, or anecdotes")
    research_gaps: List[str] = Field(default_factory=list, description="Unaddressed questions or missing data")
    content_angles: List[ContentAngle] = Field(default_factory=list, description="Derived content angles grounded in research")
    recommended_strategy: Optional[ContentStrategy] = Field(default=None, description="Platform-adapted content strategy")
    request_intent: Optional[Any] = Field(default=None, description="Parsed RequestIntent object if available")
    content_landscape: Optional[Any] = Field(default=None, description="ContentLandscape object if landscape retrieval/analysis ran")
    total_raw_insights: int = Field(default=0, description="Total raw insights extracted before synthesis")
    retained_insights_count: int = Field(default=0, description="Insights retained in final synthesized brief")
    rejected_insights_count: int = Field(default=0, description="Insights rejected during synthesis filtering")

