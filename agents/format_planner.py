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

    last_plan_method: Optional[str] = None

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
                self.last_plan_method = "gemini"
                return strat
            self.last_plan_method = "grounded_fallback"

        self.last_plan_method = "grounded_fallback"
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
            f"Selected Angle: {base_strategy.selected_angle.angle_title if base_strategy.selected_angle else 'None'} | Thesis: {base_strategy.thesis}\n"
            f"Content Landscape Differentiation: {brief.content_landscape.recommended_differentiation if brief.content_landscape else 'None'}\n"
            f"Content Gaps to Own: {brief.claim_map.content_gaps or 'None'}\n"
            f"Research Brief Findings: {[f.statement for f in brief.findings]}\n"
            f"Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims: {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Key Mechanisms: {brief.key_mechanisms}\n"
            f"Base Strategy Thesis: {base_strategy.thesis}\n\n"
            "Formulate the FormatStrategy. The hook, narrative, and CTA must differentiate from the crowded landscape and address the identified content gaps. Output JSON matching:\n"
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
                stage_label="FormatPlanner",
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
        finding_stmts = [f.statement for f in brief.findings]

        subject = brief.topic
        if hasattr(brief, 'request_intent') and brief.request_intent and brief.request_intent.subject:
            subject = brief.request_intent.subject

        primary_evidence = finding_stmts[0] if finding_stmts else (safe_claims[0] if safe_claims else "")
        secondary_evidence = finding_stmts[1] if len(finding_stmts) > 1 else (qual_claims[0] if qual_claims else "")
        counterpoints = base_strategy.counterpoints if base_strategy.counterpoints else []
        evidence_refs = safe_claims[:2] if safe_claims else finding_stmts[:2]

        hook_map = {
            "linkedin": base_strategy.hook_direction or f"The take on {subject} nobody has posted yet.",
            "x_thread": f"The argument about {subject} most people keep missing:",
            "article": f"{subject}: {base_strategy.central_thesis if hasattr(base_strategy, 'central_thesis') and base_strategy.central_thesis else 'The Angle'}",
            "newsletter": f"The {subject} take I couldn't stop thinking about",
            "youtube": f"[COLD OPEN] Why {subject} deserves your attention.",
            "short_video": f"The {subject} debate in 60 seconds",
            "carousel": f"{subject}: The angles everyone is getting wrong",
        }

        cta_map = {
            "linkedin": f"What's your experience with {subject} — agree or disagree?",
            "x_thread": f"Follow for original takes on {subject}.",
            "article": f"Subscribe for more deep-dives like this.",
            "newsletter": f"Hit reply: is this your experience with {subject}?",
            "youtube": f"Like, subscribe, and tell me your take on {subject} in the comments!",
            "short_video": f"Save this and follow for more hot takes!",
            "carousel": f"Save this post — and tell me where I'm wrong!",
        }

        return FormatStrategy(
            format_id=spec.format_id,
            topic=brief.topic,
            platform=spec.platform,
            audience=base_strategy.audience,
            objective=base_strategy.objective,
            central_thesis=base_strategy.thesis or primary_evidence,
            hook_direction=hook_map.get(spec.format_id, base_strategy.hook_direction),
            narrative_structure=spec.structure,
            key_insights_to_emphasize=[s for s in [primary_evidence, secondary_evidence] if s][:2],
            evidence_to_reference=evidence_refs[:2],
            counterpoints=counterpoints[:2],
            cta=cta_map.get(spec.format_id, base_strategy.desired_takeaway),
            desired_takeaway=base_strategy.desired_takeaway,
            delivery_style_notes=f"Adhere to {spec.pacing} pacing and {spec.paragraph_style}.",
        )

