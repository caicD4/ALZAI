from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class ContentQualityIssue(BaseModel):
    """Represents a specific content quality, research fidelity, style, or platform issue."""

    issue_id: str = Field(description="Unique ID for the quality issue.")
    category: Literal["research_fidelity", "content_quality", "voice_alignment", "platform_fit"] = Field(
        description="High-level evaluation dimension."
    )
    sub_category: str = Field(
        description="Specific sub-category (e.g., causal_strengthening, attribution_loss, generic_ai_filler, weak_hook, repetition, numerical_distortion, banned_phrase)."
    )
    severity: Literal["low", "medium", "high"] = Field(description="Severity level of the issue.")
    description: str = Field(description="Detailed explanation of the issue.")
    affected_text: str = Field(description="Exact snippet or line affected in the draft.")
    suggested_fix: str = Field(description="Actionable guidance to resolve the issue.")
    related_claim_id: Optional[str] = Field(default=None, description="Linked ClaimMap claim ID if applicable.")


class ContentQualityReport(BaseModel):
    """Aggregated assessment report from ContentQualityEngine evaluating all four dimensions."""

    report_id: str = Field(description="Unique ID for the quality report.")
    draft_id: str = Field(description="Target draft ID.")
    overall_status: Literal["passed", "needs_revision"] = Field(description="Final quality status.")
    overall_score: float = Field(ge=0.0, le=1.0, description="Overall aggregated quality score.")
    research_fidelity_score: float = Field(ge=0.0, le=1.0, description="Score for epistemic accuracy & claim grounding.")
    content_quality_score: float = Field(ge=0.0, le=1.0, description="Score for hook strength, flow, density, and value.")
    voice_alignment_score: float = Field(ge=0.0, le=1.0, description="Score for writing style & VoiceProfile adherence.")
    platform_fit_score: float = Field(ge=0.0, le=1.0, description="Score for platform adaptation & structure.")
    issues: List[ContentQualityIssue] = Field(default_factory=list, description="All identified quality issues.")
    strengths: List[str] = Field(default_factory=list, description="Notable strengths of the draft.")
    revision_priority: List[str] = Field(default_factory=list, description="Ordered list of high-priority fixes.")
    summary_assessment: str = Field(description="Overall qualitative assessment summary.")
