import json
from typing import Any, List, Optional

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

    last_outline_method: Optional[str] = None

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
                self.last_outline_method = "gemini"
                return outline
            self.last_outline_method = "grounded_fallback"

        self.last_outline_method = "grounded_fallback"
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
            f"Selected Angle: {strategy.selected_angle.angle_title if strategy.selected_angle else 'None'}\n"
            f"Angle Thesis: {strategy.selected_angle.central_thesis if strategy.selected_angle else 'None'}\n"
            f"Content Landscape Differentiation: {brief.content_landscape.recommended_differentiation if brief.content_landscape else 'None'}\n"
            f"Content Gaps to Own: {brief.claim_map.content_gaps or 'None'}\n"
            f"Hook Direction: {strategy.hook_direction}\n\n"
            f"Safe Claims Available: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims Available: {[c.claim_text for c in brief.claim_map.qualified_claims]}\n"
            f"Key Mechanisms: {brief.key_mechanisms}\n"
            f"Counterpoints: {strategy.counterpoints}\n\n"
            f"Required JSON Schema:\n{json.dumps(ContentOutline.model_json_schema(), indent=2)}\n\n"
            "Respond ONLY with a valid JSON object matching the ContentOutline schema. The hook and main points must deliver the selected angle AND differentiate from the crowded landscape, addressing the listed content gaps:"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=OUTLINER_SYSTEM_PROMPT,
                temperature=0.2,
                stage_label="Outliner",
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
        subject = brief.topic
        if hasattr(brief, 'request_intent') and brief.request_intent and brief.request_intent.subject:
            subject = brief.request_intent.subject

        safe_texts = [c.claim_text for c in brief.claim_map.safe_claims]
        qual_texts = [c.claim_text for c in brief.claim_map.qualified_claims]
        finding_stmts = [f.statement for f in brief.findings]
        mechanisms = brief.key_mechanisms or []
        counterpoints = brief.recommended_strategy.counterpoints if brief.recommended_strategy else []

        f1_text = finding_stmts[0] if finding_stmts else (safe_texts[0] if safe_texts else f"Evidence regarding {subject}")
        f2_text = finding_stmts[1] if len(finding_stmts) > 1 else (safe_texts[1] if len(safe_texts) > 1 else "")
        f3_text = finding_stmts[2] if len(finding_stmts) > 2 else (safe_texts[2] if len(safe_texts) > 2 else "")

        p1 = ContentOutlinePoint(
            point_id="point-1",
            title="Primary Evidence",
            key_concept=f1_text,
            supporting_claim_ids=["safe-1"] if safe_texts else [],
            evidence_ids=[f.finding_id for f in brief.findings[:1]],
            example_or_mechanism=mechanisms[0] if mechanisms else "",
        )

        p2 = ContentOutlinePoint(
            point_id="point-2",
            title="Additional Findings",
            key_concept=f2_text or qual_texts[0] if qual_texts else "",
            supporting_claim_ids=["safe-2"] if len(safe_texts) > 1 else [],
            evidence_ids=[f.finding_id for f in brief.findings[1:2]],
            example_or_mechanism=mechanisms[1] if len(mechanisms) > 1 else "",
        )

        p3 = ContentOutlinePoint(
            point_id="point-3",
            title="Context & Limitations",
            key_concept=f3_text or counterpoints[0] if counterpoints else "",
            supporting_claim_ids=[],
            evidence_ids=[f.finding_id for f in brief.findings[2:3]],
            example_or_mechanism="",
        )

        main_points = [p for p in [p1, p2, p3] if p.key_concept]
        if not main_points:
            main_points = [p1]

        return ContentOutline(
            outline_id=f"outline-{hash(brief.topic) & 0xffffffff:08x}",
            topic=brief.topic,
            platform=strategy.platform,
            hook_direction=strategy.hook_direction,
            setup_context=f"Research on {subject}.",
            main_points=main_points,
            counterpoints=counterpoints[:2] if counterpoints else [],
            conclusion=strategy.desired_takeaway or f"Summary of findings on {subject}.",
            cta=strategy.hook_direction or f"What are your observations regarding {subject}?",
            traceable_claim_ids=["safe-1", "qual-1"],
        )


    def create_format_outline(
        self,
        brief: ResearchBrief,
        format_strategy: Any,  # FormatStrategy
        spec: Any,  # ContentFormatSpec
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentOutline:
        """Constructs a format-adapted ContentOutline derived from FormatStrategy."""
        self.last_outline_method = "grounded_fallback"
        narrative = getattr(format_strategy, "narrative_structure", []) or spec.structure
        safe_claims = [c.claim_text for c in brief.claim_map.safe_claims]
        qual_claims = [c.claim_text for c in brief.claim_map.qualified_claims]

        points: List[ContentOutlinePoint] = []
        for idx, step_title in enumerate(narrative, start=1):
            claim_ids = []
            if idx == 1 and safe_claims:
                claim_ids.append("safe-1")
            elif idx == 2 and qual_claims:
                claim_ids.append("qual-1")

            concept = ""
            if idx <= len(brief.findings):
                concept = brief.findings[idx - 1].statement
            elif safe_claims and idx <= len(safe_claims):
                concept = safe_claims[idx - 1]

            points.append(
                ContentOutlinePoint(
                    point_id=f"pt-{idx}",
                    title=step_title,
                    key_concept=concept or step_title,
                    supporting_claim_ids=claim_ids,
                    evidence_ids=[brief.findings[idx - 1].finding_id] if idx <= len(brief.findings) else [],
                    example_or_mechanism=brief.key_mechanisms[0] if brief.key_mechanisms else "",
                )
            )

        angle_title = getattr(format_strategy, "central_thesis", "") or ""
        diff_signal = brief.content_landscape.recommended_differentiation if brief.content_landscape else ""
        gaps = brief.claim_map.content_gaps or []

        setup_chunks = [f"Research findings on {brief.topic}."]
        if angle_title:
            setup_chunks.append(f"Angle: {angle_title}")
        if diff_signal:
            setup_chunks.append(f"Differentiation: {diff_signal}")
        if gaps:
            setup_chunks.append(f"Own these gaps: {'; '.join(gaps[:3])}")

        return ContentOutline(
            outline_id=f"outline-{spec.format_id}-{hash(brief.topic) & 0xffffffff:08x}",
            topic=brief.topic,
            platform=spec.platform,
            hook_direction=format_strategy.hook_direction,
            setup_context=" ".join(setup_chunks),
            main_points=points,
            counterpoints=getattr(format_strategy, "counterpoints", []) or [],
            conclusion=format_strategy.desired_takeaway,
            cta=format_strategy.cta,
            traceable_claim_ids=["safe-1", "qual-1"],
        )
