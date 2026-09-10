import json
from typing import Optional

from core.brand_voice import BrandProfile, ContentOutline, DefaultVoiceProfile, DraftContent, VoiceProfile
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

WRITER_SYSTEM_PROMPT = """You are a Lead Human Content Writer in ALZAI's content creation engine.
Your task is to write authentic, original, platform-adapted, publication-ready prose. You write ORIGINAL content — you never parrot or reproduce other people's content. You use the ResearchBrief, ContentStrategy, ContentOutline, BrandProfile, and VoiceProfile as raw material, not as a script.

CRITICAL WRITING INSTRUCTIONS:
1. ORIGINALITY — SYNTHESIS, NEVER PARAPHRASE:
   - Do NOT reproduce distinctive wording, sentences, metaphors, or structure from ANY supplied content reference or source snippet.
   - Do NOT copy the phrasing of existing articles/posts you were told about (the Content Landscape).
   - Your job is to write something the reader has NOT read ten times already. Find the fresh angle, the unexpected argument, the honest tension.
   - Rewrite every idea in your own distinctive voice and structure.

2. HONESTY WITHOUT BOREDOM:
   - You MUST NOT invent facts, statistics, quotes, numbers, or sources.
   - Distinguish in your writing: FACT (state plainly, attribute when the source is specific), REPORTED EVENT ("reported", "per the filing"), ALLEGATION (always attribute: "critics allege", "the lawsuit claimed"), OPINION/INTERPRETATION/COMMENTARY (frame as your view or the view you are arguing — this is allowed and encouraged for angle-driven content).
   - Attribution keeps honesty without killing momentum. Write "critics allege X" not "X is a fact".
   - The user's framing is creative direction: if the user wants a critical take, write a compelling critical take WITH credible counterpoints. Do not block on "can't verify".

3. VOICE & WRITING STYLE:
   - Adhere strictly to the VoiceProfile's formatting_style, sentence_rhythm, paragraph_style, and directness.
   - Use the VoiceProfile's avoided_phrases list as strict PROHIBITIONS.

4. STRICT PROHIBITION ON AI FILLER & CLICHÉS:
   - NEVER use opening clichés like "In today's rapidly evolving world", "In a world where...", "Let's dive in", "Unlock your potential", "Game-changer", "Navigating the landscape", "Delve", "It's worth noting", "The landscape of".
   - Write like a real human subject-matter expert speaking directly to an intelligent audience.

5. PLATFORM ADAPTATION:
   - LinkedIn: Short 1-2 sentence paragraphs, bold accents, clean line breaks, high directness, engaging takeaway.
   - Long-form Article: Subtitles, section flow, context depth.
"""


class HumanBrandVoiceWriter:
    """Generates authentic human-style prose adhering to research claims, brand profile, and voice profile."""

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

    def write_draft(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: ContentOutline,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> DraftContent:
        """Generates a complete DraftContent instance."""
        target_voice = voice or DefaultVoiceProfile()

        if self.use_llm and self.llm_client is not None:
            draft = self._write_via_llm(brief, strategy, outline, brand, target_voice)
            if draft:
                return draft

        return self._write_fallback(brief, strategy, outline, brand, target_voice)

    def _write_via_llm(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: ContentOutline,
        brand: Optional[BrandProfile],
        voice: VoiceProfile,
    ) -> Optional[DraftContent]:
        """Invokes Gemini to generate publication-grade draft prose."""
        if not self.llm_client:
            return None

        prompt = (
            f"Target Topic: {brief.topic}\n"
            f"Platform: {strategy.platform}\n"
            f"Audience: {strategy.audience}\n"
            f"Selected Angle: {strategy.selected_angle.angle_title if strategy.selected_angle else 'None'} | Thesis: {strategy.thesis}\n"
            f"Content Landscape Differentiation: {brief.content_landscape.recommended_differentiation if brief.content_landscape else 'None'}\n"
            f"Content Gaps to Own: {brief.claim_map.content_gaps or 'None'}\n"
            f"Outline Hook: {outline.hook_direction}\n"
            f"Outline Setup: {outline.setup_context}\n"
            f"Outline Sections: {[p.title + ': ' + p.key_concept for p in outline.main_points]}\n"
            f"Outline Conclusion: {outline.conclusion}\n"
            f"Outline CTA: {outline.cta or 'None'}\n\n"
            f"RESEARCH CLAIM MAP (HONESTY BOUNDARIES):\n"
            f"Safe Claims (grounded in sources, state as fact): {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims (MUST include attribution): {[{'claim': c.claim_text, 'attribution': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (frame as OPINION/commentary or attribute as allegation — never state as fact): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
            f"VOICE & STYLE RULES:\n"
            f"Voice Name: {voice.name} (is_default={voice.is_default_profile})\n"
            f"Formality: {voice.formality}\n"
            f"Directness: {voice.directness}\n"
            f"Paragraph Style: {voice.paragraph_style}\n"
            f"Banned Phrases: {voice.avoided_phrases}\n\n"
            "Generate the final publication-ready prose. Output JSON format matching:\n"
            "{\"title\": \"...\", \"body_text\": \"...\"}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=WRITER_SYSTEM_PROMPT,
                temperature=0.3,
                stage_label="Writer",
            )
            data = json.loads(raw_json)
            body = data.get("body_text", "")
            title = data.get("title")

            return DraftContent(
                draft_id=f"draft-{hash(brief.topic) & 0xffffffff:08x}",
                topic=brief.topic,
                platform=strategy.platform,
                title=title,
                body_text=body,
                outline_id=outline.outline_id,
                brief_id=brief.brief_id,
                word_count=len(body.split()),
                version=1,
            )
        except Exception:
            return None

    def _write_fallback(
        self,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: ContentOutline,
        brand: Optional[BrandProfile],
        voice: VoiceProfile,
    ) -> DraftContent:
        """Deterministic fallback prose generator for offline testing."""
        safe_str = (
            brief.claim_map.safe_claims[0].claim_text
            if brief.claim_map.safe_claims
            else ""
        )
        qual_item = brief.claim_map.qualified_claims[0] if brief.claim_map.qualified_claims else None
        qual_str = (
            f"{qual_item.claim_text} ({qual_item.required_attribution_or_caveat})"
            if qual_item and qual_item.required_attribution_or_caveat
            else (qual_item.claim_text if qual_item else "")
        )

        finding_stmts = [f.statement for f in brief.findings]
        counterpoint_str = ""
        if strategy and strategy.counterpoints:
            counterpoint_str = strategy.counterpoints[0]

        body_parts = []
        if strategy and strategy.hook_direction:
            body_parts.append(strategy.hook_direction)

        for stmt in finding_stmts[:3]:
            body_parts.append(stmt)

        if safe_str and safe_str not in body_parts:
            body_parts.append(safe_str)
        if qual_str and qual_str not in body_parts:
            body_parts.append(qual_str)
        if counterpoint_str:
            body_parts.append(counterpoint_str)

        if strategy and strategy.desired_takeaway:
            body_parts.append(strategy.desired_takeaway)

        body_parts = [p for p in body_parts if p]
        if not body_parts:
            body_parts = [f"Research findings regarding {brief.topic}."]

        body_text = "\n\n".join(body_parts)

        if hasattr(strategy, 'selected_angle') and strategy.selected_angle and strategy.selected_angle.angle_title:
            title = strategy.selected_angle.angle_title
        else:
            title = brief.topic

        return DraftContent(
            draft_id=f"draft-{hash(brief.topic) & 0xffffffff:08x}",
            topic=brief.topic,
            platform=strategy.platform if strategy else "LinkedIn",
            title=title,
            body_text=body_text,
            outline_id=outline.outline_id if outline else "out-fallback",
            brief_id=brief.brief_id if brief else "brief-fallback",
            word_count=len(body_text.split()),
            version=1,
        )


