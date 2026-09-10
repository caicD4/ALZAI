import json
from typing import List, Optional
from pydantic import BaseModel, Field

from core.brand_voice import BrandProfile, VoiceProfile
from core.format_specs import FORMAT_CATALOG, ContentFormatSpec
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient


class FormatStrategy(BaseModel):
    """Format-specific content strategy derived from ResearchBrief and ContentFormatSpec."""

    format_id: str = Field(..., description="Target format ID e.g. 'linkedin', 'x_thread', 'article'")
    topic: str = Field(..., description="Target topic")
    platform: str = Field(..., description="Target platform name")
    audience: str = Field(..., description="Platform-adapted target audience")
    objective: str = Field(..., description="Strategic objective for format")
    central_thesis: str = Field(..., description="Core angle or thesis statement")
    hook_direction: str = Field(..., description="Format-adapted hook strategy")
    narrative_structure: List[str] = Field(default_factory=list, description="Section or post structural flow")
    key_insights_to_emphasize: List[str] = Field(default_factory=list, description="Key research insights to highlight")
    evidence_to_reference: List[str] = Field(default_factory=list, description="Evidence or studies to cite")
    counterpoints: List[str] = Field(default_factory=list, description="Counterpoints or limitations to address")
    cta: str = Field(..., description="Format-specific call to action")
    desired_takeaway: str = Field(..., description="Core takeaway for audience")
    delivery_style_notes: str = Field(default="", description="Pacing, tone, or formatting guidelines")


FORMAT_PLANNER_SYSTEM_PROMPT = """You are a Lead Multi-Format Content Strategist in ALZAI.
Your task is to derive a platform-adapted FormatStrategy from a ResearchBrief, base ContentStrategy, BrandProfile, VoiceProfile, and ContentFormatSpec.

CRITICAL STRATEGY RULES:
1. RESEARCH GROUNDING: Adapt the research to the platform without exaggerating evidence strength or distorting claim boundaries.
2. FORMAT ADAPTATION:
   - LinkedIn: Professional insight, problem assertion hook, peer discussion CTA.
   - X Thread: Sequential curiosity, 1 core idea per post, shareable takeaway.
   - Article: Deep conceptual development, research mechanism breakdown, nuanced counterpoints.
   - Newsletter: Conversational author voice, tactical takeaways, intimate subscriber CTA.
   - YouTube: Spoken cadence, visual cold open hook, retention progression, subscribe CTA.
   - Short Video: Ultra-fast 3s hook, compressed core mechanism, rapid loop CTA.
   - Carousel: Slide-by-slide visual architecture, step-by-step clarity, save/share CTA.
"""


class MultiFormatPlanner:
    """Plans format-adapted strategies for individual content formats directly from a ResearchBrief."""

    def __init__(
        self,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
    ) -> None:
        self.use_llm = use_llm
        if use_llm:
            self.llm_client = llm_client or GeminiClient()
        else:
            self.llm_client = None

    def plan_format(
        self,
        brief: ResearchBrief,
        base_strategy: ContentStrategy,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> FormatStrategy:
        """Derives a FormatStrategy for a given ContentFormatSpec directly from the ResearchBrief."""
        if self.use_llm and self.llm_client is not None:
            strat = self._plan_via_llm(brief, base_strategy, spec, brand, voice)
            if strat:
                return strat

        return self._plan_fallback(brief, base_strategy, spec)

    def _plan_via_llm(
        self,
        brief: ResearchBrief,
        base_strategy: ContentStrategy,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile],
        voice: Optional[VoiceProfile],
    ) -> Optional[FormatStrategy]:
        """Invokes Gemini to construct a platform-adapted FormatStrategy."""
        if not self.llm_client:
            return None

        prompt = (
            f"Topic: {brief.topic}\n"
            f"Format ID: {spec.format_id} ({spec.format_name})\n"
            f"Target Platform: {spec.platform}\n"
            f"Target Length: {spec.target_length}\n"
            f"Structure Template: {spec.structure}\n"
            f"Hook Style: {spec.hook_style}\n"
            f"Pacing: {spec.pacing}\n"
            f"CTA Style: {spec.cta_style}\n\n"
            f"Research Brief Findings: {[f.statement for f in brief.findings]}\n"
            f"Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims: {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Key Mechanisms: {brief.key_mechanisms}\n"
            f"Base Strategy Thesis: {base_strategy.thesis}\n\n"
            "Formulate the FormatStrategy. Output JSON matching:\n"
            "{\"format_id\": \"...\", \"topic\": \"...\", \"platform\": \"...\", \"audience\": \"...\", \"objective\": \"...\", "
            "\"central_thesis\": \"...\", \"hook_direction\": \"...\", \"narrative_structure\": [...], "
            "\"key_insights_to_emphasize\": [...], \"evidence_to_reference\": [...], \"counterpoints\": [...], "
            "\"cta\": \"...\", \"desired_takeaway\": \"...\", \"delivery_style_notes\": \"...\"}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=FORMAT_PLANNER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            data = json.loads(raw_json)
            return FormatStrategy.model_validate(data)
        except Exception:
            return None

    def _plan_fallback(
        self,
        brief: ResearchBrief,
        base_strategy: ContentStrategy,
        spec: ContentFormatSpec,
    ) -> FormatStrategy:
        """Deterministic fallback planner for offline/rate-limited execution."""
        safe_claims = [c.claim_text for c in brief.claim_map.safe_claims]
        qual_claims = [c.claim_text for c in brief.claim_map.qualified_claims]

        hook_map = {
            "linkedin": f"Understanding the core operational shift in {brief.topic}. Here is what the research synthesis reveals.",
            "x_thread": f"Key research findings and strategic implications regarding {brief.topic} (1/{spec.maximum_length}):",
            "article": f"{brief.topic}: A Comprehensive Strategic & Evidence-Based Overview",
            "newsletter": f"Strategic Breakdown: Key research perspectives on {brief.topic}",
            "youtube": f"[VISUAL: Key concepts graphic] Exploring the fundamental mechanisms driving {brief.topic}.",
            "short_video": f"Here is what research reveals about {brief.topic} in 60 seconds (0:00-0:05)",
            "carousel": f"{brief.topic}: A Grounded Strategic Overview",
        }

        cta_map = {
            "linkedin": f"What key observations do you have on {brief.topic}?",
            "x_thread": f"If you found this breakdown on {brief.topic} useful, repost and follow for more strategic insights.",
            "article": f"Subscribe for weekly deep-dives into research-backed content strategies.",
            "newsletter": f"Hit reply and let me know: What is your approach to {brief.topic}?",
            "youtube": f"Subscribe and drop your thoughts on {brief.topic} in the comments below!",
            "short_video": "Save this short and follow for daily 60-second cognitive science breakdowns!",
            "carousel": "Save this post for your next training session and swipe left to share!",
        }

        return FormatStrategy(
            format_id=spec.format_id,
            topic=brief.topic,
            platform=spec.platform,
            audience=base_strategy.audience,
            objective=base_strategy.objective,
            central_thesis=base_strategy.thesis or f"Adaptive training expands cognitive skills while casual apps yield task-specific practice effects.",
            hook_direction=hook_map.get(spec.format_id, base_strategy.hook_direction),
            narrative_structure=spec.structure,
            key_insights_to_emphasize=safe_claims[:2] if safe_claims else [brief.topic],
            evidence_to_reference=qual_claims[:1] if qual_claims else ["Cassidy et al. RFT trials"],
            counterpoints=["Far-transfer gains require sustained adaptive load past automaticity."],
            cta=cta_map.get(spec.format_id, base_strategy.desired_takeaway),
            desired_takeaway=base_strategy.desired_takeaway,
            delivery_style_notes=f"Adhere to {spec.pacing} pacing and {spec.paragraph_style}.",
        )
