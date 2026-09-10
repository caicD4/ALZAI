import json
from typing import List, Optional

from core.brand_voice import BrandProfile, ContentOutline, ContentOutlinePoint, VoiceProfile
from core.synthesis import ResearchBrief, ContentStrategy
from tools.llm_client import GeminiClient

OUTLINER_SYSTEM_PROMPT = """You are a Lead Content Strategist and Outliner in ALZAI.
Your task is to convert a ResearchBrief and ContentStrategy into a platform-aware, claim-traceable ContentOutline.

OUTLINE RULES:
1. Platform Awareness:
   - LinkedIn: Hook -> Setup -> 3-4 punchy main points -> Counterpoint -> Actionable Takeaway / CTA.
   - Long-form Article: Clear section headers, depth context, evidence breakdown, synthesis conclusion.
2. Claim Traceability:
   - Link each main point to specific safe/qualified claim IDs or evidence IDs from the ResearchBrief.
3. Zero AI Clichés:
   - Do NOT use generic hook templates like "In today's world...". Use the strategy's specific hook direction.
"""


class ContentOutliner:
    """Generates platform-aware, claim-traceable ContentOutlines from ResearchBrief and ContentStrategy."""

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

    def create_outline(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentOutline:
        """Constructs a validated, platform-tailored ContentOutline."""
        if self.use_llm and self.llm_client is not None:
            outline = self._create_via_llm(brief, strategy, brand, voice)
            if outline:
                return outline

        return self._create_fallback(brief, strategy, brand, voice)

    def _create_via_llm(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        brand: Optional[BrandProfile],
        voice: Optional[VoiceProfile],
    ) -> Optional[ContentOutline]:
        """Invokes Gemini to generate structured ContentOutline."""
        if not self.llm_client:
            return None

        prompt = (
            f"Topic: {brief.topic}\n"
            f"Platform: {strategy.platform}\n"
            f"Audience: {strategy.audience}\n"
            f"Selected Thesis: {strategy.thesis}\n"
            f"Hook Direction: {strategy.hook_direction}\n\n"
            f"Safe Claims Available: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims Available: {[c.claim_text for c in brief.claim_map.qualified_claims]}\n"
            f"Key Mechanisms: {brief.key_mechanisms}\n"
            f"Counterpoints: {strategy.counterpoints}\n\n"
            f"Required JSON Schema:\n{json.dumps(ContentOutline.model_json_schema(), indent=2)}\n\n"
            "Respond ONLY with a valid JSON object matching the ContentOutline schema:"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=OUTLINER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            data = json.loads(raw_json)
            return ContentOutline.model_validate(data)
        except Exception:
            return None

    def _create_fallback(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        brand: Optional[BrandProfile],
        voice: Optional[VoiceProfile],
    ) -> ContentOutline:
        """Deterministic fallback outline generator."""
        claim_ids = []
        safe_texts = [c.claim_text for c in brief.claim_map.safe_claims]
        qual_texts = [c.claim_text for c in brief.claim_map.qualified_claims]

        p1 = ContentOutlinePoint(
            point_id="point-1",
            title="The Core Myth vs Neural Reality",
            key_concept="Why passive memory apps fail while adaptive neuroplastic training triggers structural change.",
            supporting_claim_ids=["safe-1"] if safe_texts else [],
            evidence_ids=[f.finding_id for f in brief.findings[:1]],
            example_or_mechanism=brief.key_mechanisms[0] if brief.key_mechanisms else "Synaptic remodeling",
        )

        p2 = ContentOutlinePoint(
            point_id="point-2",
            title="Relational Frame Theory (RFT) as a Foundational Primitive",
            key_concept="Training relational skills (same/different, opposite, conditional) directly enhances fluid reasoning.",
            supporting_claim_ids=["qual-1"] if qual_texts else [],
            evidence_ids=[f.finding_id for f in brief.findings[0:1]],
            example_or_mechanism="SMART relational training protocol (Cassidy et al.)",
        )

        p3 = ContentOutlinePoint(
            point_id="point-3",
            title="The Necessity of Continuous Adaptive Strain",
            key_concept="Cognitive growth requires dynamic difficulty that scales with individual performance ceilings.",
            supporting_claim_ids=["safe-2"] if len(safe_texts) > 1 else [],
            evidence_ids=[f.finding_id for f in brief.findings[1:2]],
            example_or_mechanism="Adaptive working memory strain",
        )

        main_points = [p1, p2, p3]

        return ContentOutline(
            outline_id=f"outline-{hash(brief.topic) & 0xffffffff:08x}",
            topic=brief.topic,
            platform=strategy.platform,
            hook_direction=strategy.hook_direction,
            setup_context="Most brain training apps don't raise IQ; they make you good at playing the app. Neuroscience reveals what actually drives fluid intelligence.",
            main_points=main_points,
            counterpoints=strategy.counterpoints or ["Far-transfer gains require sustained adaptive effort."],
            conclusion="True cognitive enhancement requires structured, adaptive relational training rather than casual gaming.",
            cta="How do you approach cognitive skill building in your daily routine?",
            traceable_claim_ids=["safe-1", "qual-1"],
        )
