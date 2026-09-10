from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ContentFormatSpec(BaseModel):
    """Specification defining structure, rules, and expectations for a specific content format."""

    format_id: str = Field(..., description="Unique identifier e.g. 'linkedin', 'x_thread', 'article'")
    platform: str = Field(..., description="Target platform e.g. 'LinkedIn', 'X/Twitter', 'Substack'")
    format_name: str = Field(..., description="Human-readable format name e.g. 'X/Twitter Thread'")
    target_length: str = Field(..., description="Descriptive target length e.g. '200-400 words', '5-8 posts'")
    structure: List[str] = Field(default_factory=list, description="Expected structural section flow")
    hook_style: str = Field(..., description="Format-adapted hook approach")
    pacing: str = Field(..., description="Pacing style e.g. 'concise_direct', 'sequential_curiosity', 'deep_editorial', 'spoken_rhythm'")
    paragraph_style: str = Field(..., description="Paragraph formatting guidelines")
    formatting_rules: List[str] = Field(default_factory=list, description="Rules for bullets, counters, bolding, tags")
    audience_expectation: str = Field(..., description="Expectation of target audience on platform")
    cta_style: str = Field(..., description="Call to action guidance for format")
    minimum_length: int = Field(default=1, description="Minimum words, posts, or slides")
    maximum_length: int = Field(default=1000, description="Maximum words, posts, or slides")


# Central Catalog of All 7 Supported Formats
FORMAT_CATALOG: Dict[str, ContentFormatSpec] = {
    "linkedin": ContentFormatSpec(
        format_id="linkedin",
        platform="LinkedIn",
        format_name="LinkedIn Post",
        target_length="200-400 words",
        structure=["Hook", "Context", "Core Insight", "Evidence/Mechanism", "Implication", "Takeaway", "Question CTA"],
        hook_style="Bold problem assertion or counter-intuitive insight statement",
        pacing="concise_direct",
        paragraph_style="Short 1-2 sentence paragraphs with clean double line breaks",
        formatting_rules=["Use bold accents sparingly", "Clean spacing", "No generic hashtags"],
        audience_expectation="Professional, actionable, high signal-to-noise ratio",
        cta_style="Open-ended discussion question engaging industry peers",
        minimum_length=150,
        maximum_length=600,
    ),
    "x_thread": ContentFormatSpec(
        format_id="x_thread",
        platform="X/Twitter",
        format_name="X/Twitter Thread",
        target_length="5-8 posts",
        structure=["Post 1: Hook & Staking Claim", "Post 2: Problem/Myth", "Post 3: Core Mechanism", "Post 4: Key Evidence", "Post 5: Counter-Perspective", "Post 6: Takeaway", "Post 7: Summary & RT CTA"],
        hook_style="High-curiosity standalone statement promising actionable breakdown",
        pacing="sequential_curiosity",
        paragraph_style="1-3 short punchy lines per post, prefixed with post counter (e.g. 1/)",
        formatting_rules=["Include '1/' or '1/7' post numbers", "Each post must be standalone coherent", "Use short line breaks"],
        audience_expectation="Immediate value, rapid scannability, shareable insights",
        cta_style="Retweet call-to-action on first/last post plus follow prompt",
        minimum_length=4,
        maximum_length=10,
    ),
    "article": ContentFormatSpec(
        format_id="article",
        platform="Substack / Medium",
        format_name="Long-Form Article",
        target_length="800-1500 words",
        structure=["Title & Subtitle", "Introduction & Thesis", "Section 1: Foundations", "Section 2: Deep Mechanism", "Section 3: Practical Application", "Counterpoints & Tradeoffs", "Synthesis & Conclusion"],
        hook_style="Narrative framing or intellectual thesis statement establishing significance",
        pacing="deep_editorial",
        paragraph_style="Rich 3-5 sentence editorial paragraphs with H2/H3 Markdown headers",
        formatting_rules=["Use Markdown headers (##, ###)", "Use blockquotes for key findings", "Include section transitions"],
        audience_expectation="Thorough analysis, deep conceptual development, nuanced breakdown",
        cta_style="Newsletter subscription or bookmark prompt",
        minimum_length=600,
        maximum_length=2500,
    ),
    "newsletter": ContentFormatSpec(
        format_id="newsletter",
        platform="Email Newsletter",
        format_name="Email Newsletter Issue",
        target_length="400-800 words",
        structure=["Subject Line & Header", "Personal Author Opening", "Main Story / Key Insight", "Tactical Takeaways", "Curated Context", "Closing Thoughts & Sign-off"],
        hook_style="Direct, conversational greeting framing a personal or industry observation",
        pacing="conversational_editorial",
        paragraph_style="Personal 2-3 sentence conversational paragraphs with bold highlights",
        formatting_rules=["Include Subject Line suggestion", "Conversational tone", "Bulleted key takeaways"],
        audience_expectation="Intimate expert perspective, exclusive breakdown, actionable digest",
        cta_style="Reply prompt or direct subscriber action",
        minimum_length=300,
        maximum_length=1200,
    ),
    "youtube": ContentFormatSpec(
        format_id="youtube",
        platform="YouTube",
        format_name="Long Video Script",
        target_length="800-1500 words (5-10 min speech)",
        structure=["Cold Open (0-15s)", "Title Card / Intro", "The Core Problem", "Deep Mechanism Breakdown", "Real-World Case Example", "Counter-Arguments", "Actionable Takeaway", "Outro & Subscribe CTA"],
        hook_style="Visual/spoken disruption in first 10 seconds challenging viewer assumptions",
        pacing="spoken_rhythm",
        paragraph_style="Spoken prose with explicit speaker cues e.g. [VISUAL: ...], [PAUSE], [ON SCREEN]",
        formatting_rules=["Include visual & B-roll cues in brackets", "Spoken rhythm punctuation", "Clear verbal transitions"],
        audience_expectation="Engaging visual-narrative flow, clear vocal cadence, high retention progression",
        cta_style="Verbal subscribe & comment prompt linked to video topic",
        minimum_length=500,
        maximum_length=2500,
    ),
    "short_video": ContentFormatSpec(
        format_id="short_video",
        platform="YouTube Shorts / Reels / TikTok",
        format_name="Short-Form Video Script",
        target_length="120-250 words (30-60 sec speech)",
        structure=["0-3s Hook", "3-15s Problem", "15-40s Core Insight/Mechanism", "40-55s Payoff/Takeaway", "55-60s Loop CTA"],
        hook_style="Immediate 2-second auditory/visual hook confronting common mistake",
        pacing="fast_compressed",
        paragraph_style="Ultra-short spoken phrases optimized for rapid speech and onscreen captions",
        formatting_rules=["Include timestamp markers e.g. (0:00-0:03)", "Include text overlay cues", "Seamless loop ending"],
        audience_expectation="Instant hook, zero fluff, high punchiness, viral replayability",
        cta_style="Looping final phrase leading back to hook or quick follow prompt",
        minimum_length=80,
        maximum_length=350,
    ),
    "carousel": ContentFormatSpec(
        format_id="carousel",
        platform="LinkedIn / Instagram",
        format_name="Slide Carousel Outline",
        target_length="5-8 slides",
        structure=["Slide 1: Cover / Bold Title Hook", "Slide 2: The Problem / Myth", "Slide 3: Core Insight", "Slide 4: Key Mechanism", "Slide 5: Practical Step 1", "Slide 6: Practical Step 2", "Slide 7: Summary Diagram", "Slide 8: Save & Share CTA"],
        hook_style="High-impact slide title with short subtitle promising step-by-step breakdown",
        pacing="visual_slides",
        paragraph_style="Slide-by-slide layout with Slide Title, 1 main visual idea, and 2-3 bullet points",
        formatting_rules=["Header '[SLIDE X: Title]'", "Keep text under 40 words per slide", "Visual composition notes"],
        audience_expectation="Highly visual, bite-sized step-by-step guide worth saving",
        cta_style="Save this post / swipe left prompt on final slide",
        minimum_length=4,
        maximum_length=10,
    ),
}


def get_format_spec(format_id: str) -> ContentFormatSpec:
    """Retrieves ContentFormatSpec for a given format_id or raises ValueError."""
    fmt_key = format_id.lower().strip()
    if fmt_key not in FORMAT_CATALOG:
        raise ValueError(
            f"Unsupported content format '{format_id}'. Supported formats: {list(FORMAT_CATALOG.keys())}"
        )
    return FORMAT_CATALOG[fmt_key]

