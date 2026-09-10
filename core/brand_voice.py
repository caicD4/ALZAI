from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class BrandProfile(BaseModel):
    """Represents the identity, niche, and strategic positioning of a brand or content creator."""

    name: str = Field(default="ALZAI Creator", description="Name of the creator, brand, or organization.")
    niche: str = Field(default="Research & Technology", description="Primary domain or industry niche.")
    audience: str = Field(default="Thought Leaders & Professionals", description="Target audience demographics and interests.")
    positioning: str = Field(default="Research-backed insight creator", description="Market positioning statement or unique perspective.")
    topics: List[str] = Field(default_factory=list, description="Core topics covered by the brand.")
    values: List[str] = Field(default_factory=list, description="Core principles or values.")
    recurring_themes: List[str] = Field(default_factory=list, description="Themes frequently emphasized.")
    opinions_worldview: List[str] = Field(default_factory=list, description="Key perspectives or opinions.")
    expertise_level: str = Field(default="expert", description="Perceived depth of expertise.")
    preferred_formats: List[str] = Field(default_factory=list, description="Formats favored by the brand.")
    things_to_emphasize: List[str] = Field(default_factory=list, description="Key concepts to highlight.")
    things_to_avoid: List[str] = Field(default_factory=list, description="Concepts or positions to avoid.")


class VoiceProfile(BaseModel):
    """Detailed structural definition of a creator's WRITING STYLE."""

    profile_id: str = Field(default="default-voice", description="Unique identifier for the voice profile.")
    name: str = Field(default="Default Human Voice", description="Human-readable voice profile name.")
    formality: Literal["casual", "semi_formal", "formal", "academic", "direct_conversational"] = Field(
        default="direct_conversational"
    )
    sentence_length: Literal["short", "varied", "long", "punchy_short"] = Field(default="punchy_short")
    sentence_rhythm: str = Field(
        default="Rhythmic mix of short statements followed by analytical explanations.",
        description="Rhythm and cadence of sentence construction.",
    )
    vocabulary_style: str = Field(
        default="Precise, accessible tech & science terms without unnecessary buzzwords.",
        description="Choice of vocabulary and jargon level.",
    )
    technicality: Literal["low", "medium", "high", "deep_technical"] = Field(default="medium")
    humor_level: Literal["none", "subtle", "witty", "dry", "high"] = Field(default="subtle")
    sarcasm_level: Literal["none", "occasional", "frequent"] = Field(default="none")
    directness: Literal["very_direct", "balanced", "diplomatic", "nuanced"] = Field(default="very_direct")
    emotional_intensity: Literal["calm", "engaging", "passionate", "provocative"] = Field(default="engaging")
    use_of_slang: bool = Field(default=False)
    use_of_profanity: bool = Field(default=False)
    rhetorical_question_frequency: Literal["none", "rare", "occasional", "frequent"] = Field(default="occasional")
    paragraph_style: Literal["one_line_spaced", "short_paragraphs", "dense_academic"] = Field(default="short_paragraphs")
    formatting_style: str = Field(
        default="Clean bold subheaders, short line breaks, selective bullet points.",
        description="Preferred visual typography and markdown structure.",
    )
    storytelling_style: str = Field(
        default="Starts with a counterintuitive hook or real scenario, transitions directly to evidence.",
        description="Narrative framework used in writing.",
    )
    analogy_usage: Literal["rare", "occasional", "frequent"] = Field(default="occasional")
    hook_patterns: List[str] = Field(
        default_factory=lambda: ["Myth vs Reality opening", "Bold counter-claim", "Specific metric/data point"],
        description="Common opening patterns.",
    )
    closing_patterns: List[str] = Field(
        default_factory=lambda: ["Actionable takeaway", "Reframing question", "Practical summary"],
        description="Common closing patterns.",
    )
    recurring_phrases: List[str] = Field(default_factory=list, description="Signature phrases naturally used.")
    avoided_phrases: List[str] = Field(
        default_factory=lambda: [
            "In today's rapidly evolving world",
            "Let's dive in",
            "Game-changer",
            "Unlock your potential",
            "Navigating the landscape",
            "Paradigm shift",
            "Supercharge your",
        ],
        description="Phrases and AI clichés strictly prohibited.",
    )
    stylistic_examples: List[str] = Field(default_factory=list, description="Raw exemplar sentences or paragraphs.")
    is_default_profile: bool = Field(
        default=True,
        description="True if this is the fallback default profile; False if inferred from real user writing samples.",
    )


def DefaultVoiceProfile() -> VoiceProfile:
    """Factory returning explicit default writing style when no user writing samples are supplied."""
    return VoiceProfile(
        profile_id="default-voice-profile",
        name="ALZAI Crisp Professional Voice",
        formality="direct_conversational",
        sentence_length="punchy_short",
        sentence_rhythm="Punchy opening assertions followed by clear evidence-backed explanations.",
        vocabulary_style="Clean, precise terminology; avoids AI fluff and corporate buzzwords.",
        technicality="medium",
        humor_level="subtle",
        sarcasm_level="none",
        directness="very_direct",
        emotional_intensity="engaging",
        use_of_slang=False,
        use_of_profanity=False,
        rhetorical_question_frequency="occasional",
        paragraph_style="short_paragraphs",
        formatting_style="Short 1-2 sentence paragraphs, bold key terms, clean spacing.",
        storytelling_style="Contrarian hook → core mechanism → empirical evidence → clear takeaway.",
        analogy_usage="occasional",
        is_default_profile=True,
    )


class ContentOutlinePoint(BaseModel):
    """Represents a single structural section or main point in a content outline."""

    point_id: str = Field(description="Unique ID for outline point (e.g. point-1).")
    title: str = Field(description="Section heading or main point title.")
    key_concept: str = Field(description="Core takeaway concept of this section.")
    supporting_claim_ids: List[str] = Field(default_factory=list, description="Linked ClaimMap claim IDs.")
    evidence_ids: List[str] = Field(default_factory=list, description="Linked ResearchInsight evidence IDs.")
    example_or_mechanism: Optional[str] = Field(default=None, description="Concrete example or mechanism to include.")


class ContentOutline(BaseModel):
    """Platform-aware structural blueprint for generating prose."""

    outline_id: str = Field(description="Unique outline identifier.")
    topic: str = Field(description="User research topic.")
    platform: str = Field(description="Target platform (e.g., LinkedIn, Article, Twitter Thread).")
    hook_direction: str = Field(description="Opening hook approach.")
    setup_context: str = Field(description="Context and problem framing.")
    main_points: List[ContentOutlinePoint] = Field(default_factory=list, description="Ordered list of outline sections.")
    counterpoints: List[str] = Field(default_factory=list, description="Nuance/counterpoints to integrate.")
    conclusion: str = Field(description="Closing section summary.")
    cta: Optional[str] = Field(default=None, description="Call to action or reframing question.")
    traceable_claim_ids: List[str] = Field(default_factory=list, description="All claim IDs mapped across outline points.")


class DraftContent(BaseModel):
    """The generated prose draft output."""

    draft_id: str = Field(description="Unique draft identifier.")
    topic: str = Field(description="User research topic.")
    platform: str = Field(description="Target platform (e.g., LinkedIn, Article).")
    title: Optional[str] = Field(default=None, description="Draft headline or post title.")
    body_text: str = Field(description="The full generated prose body text.")
    outline_id: str = Field(description="Linked outline ID.")
    brief_id: str = Field(description="Linked research brief ID.")
    word_count: int = Field(description="Word count of body text.")
    version: int = Field(default=1, description="Draft version number (1 for initial, 2+ for revisions).")


class FactualError(BaseModel):
    """Represents an epistemic or research accuracy violation in a draft."""

    error_id: str = Field(description="Unique error identifier.")
    category: Literal[
        "unsupported_claim",
        "strengthened_claim",
        "missing_caveat",
        "attribution_loss",
        "number_drift",
        "contradictory_statement",
    ] = Field(description="Category of factual failure.")
    quote_in_draft: str = Field(description="Draft snippet triggering the error.")
    explanation: str = Field(description="Explanation of why this violates research truth.")
    suggested_fix: str = Field(description="Required correction.")


class StyleError(BaseModel):
    """Represents a writing style, formatting, or voice profile violation in a draft."""

    error_id: str = Field(description="Unique error identifier.")
    category: Literal["ai_filler_cliche", "tone_mismatch", "formatting_violation", "length_violation", "banned_phrase"] = Field(
        description="Category of style failure."
    )
    quote_in_draft: str = Field(description="Draft snippet triggering the error.")
    explanation: str = Field(description="Explanation of style deviation.")
    suggested_fix: str = Field(description="Suggested style adjustment.")


class VoiceAlignmentEvaluation(BaseModel):
    """Detailed metrics evaluating how well draft prose matches a target VoiceProfile."""

    vocabulary_match: float = Field(ge=0.0, le=1.0, description="Match score for vocabulary style.")
    rhythm_match: float = Field(ge=0.0, le=1.0, description="Match score for sentence rhythm.")
    formatting_match: float = Field(ge=0.0, le=1.0, description="Match score for visual formatting.")
    directness_match: float = Field(ge=0.0, le=1.0, description="Match score for directness.")
    overall_style_score: float = Field(ge=0.0, le=1.0, description="Aggregated style alignment score.")
    feedback: str = Field(description="Qualitative style feedback.")


class VerificationReport(BaseModel):
    """Comprehensive verifier assessment report separating factual errors from style errors."""

    report_id: str = Field(description="Unique report ID.")
    draft_id: str = Field(description="Target draft ID.")
    is_passed: bool = Field(description="True if draft has zero high-severity factual errors and passes style thresholds.")
    factual_errors: List[FactualError] = Field(default_factory=list, description="Factual and epistemic errors.")
    style_errors: List[StyleError] = Field(default_factory=list, description="Writing style and formatting errors.")
    unsupported_claims_count: int = Field(default=0)
    strengthened_claims_count: int = Field(default=0)
    missing_caveats_count: int = Field(default=0)
    attribution_losses_count: int = Field(default=0)
    ai_filler_detected: bool = Field(default=False)
    voice_alignment: VoiceAlignmentEvaluation
    summary_assessment: str = Field(description="Overall evaluation summary.")


class RevisionPassResult(BaseModel):
    """Summary of a targeted revision iteration."""

    pass_number: int = Field(description="Revision pass number (1 or 2).")
    revised_draft: DraftContent
    verification_report: VerificationReport
    fixes_applied: List[str] = Field(default_factory=list)
