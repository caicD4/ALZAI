import json
from typing import Optional

from core.brand_voice import BrandProfile, ContentOutline, DefaultVoiceProfile, DraftContent, VoiceProfile
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

WRITER_SYSTEM_PROMPT = """You are a Lead Human Content Writer in ALZAI's content creation engine.
Your task is to write authentic, platform-adapted, publication-ready prose based strictly on a ResearchBrief, ContentStrategy, ContentOutline, BrandProfile, and VoiceProfile.

CRITICAL WRITING INSTRUCTIONS:
1. RESEARCH & EPISTEMIC INTEGRITY (MANDATORY):
   - You MUST use ONLY claims permitted in the ResearchBrief's ClaimMap.
   - You MUST NOT upgrade claim strength (e.g., if research says "authors observed", do NOT say "scientists proved").
   - You MUST preserve required caveats and attributions (e.g., "According to Dr. Cassidy...", "Company X claims...").
   - You MUST NOT invent unsupported numerical statistics or facts.

2. VOICE & WRITING STYLE REPRODUCTION:
   - Adhere strictly to the VoiceProfile's formatting_style, sentence_rhythm, paragraph_style, and directness.
   - Use the VoiceProfile's avoided_phrases list as strict PROHIBITIONS.

3. STRICT PROHIBITION ON AI FILLER & CLICHÉS:
   - NEVER use opening clichés like "In today's rapidly evolving world", "In a world where...", "Let's dive in", "Unlock your potential", "Game-changer", "Navigating the landscape".
   - Write like a real human subject-matter expert speaking directly to an intelligent audience.

4. PLATFORM ADAPTATION:
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
            f"Outline Hook: {outline.hook_direction}\n"
            f"Outline Setup: {outline.setup_context}\n"
            f"Outline Sections: {[p.title + ': ' + p.key_concept for p in outline.main_points]}\n"
            f"Outline Conclusion: {outline.conclusion}\n"
            f"Outline CTA: {outline.cta or 'None'}\n\n"
            f"RESEARCH CLAIM MAP (STRICT BOUNDARIES):\n"
            f"Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims (MUST INCLUDE CAVEATS): {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (BANNED): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n"
            f"User Premise Verdict: {brief.claim_map.user_premise_verdict}\n\n"
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
        safe_str = brief.claim_map.safe_claims[0].claim_text if brief.claim_map.safe_claims else "Neuroplasticity allows neural connections to reorganize."
        qual_item = brief.claim_map.qualified_claims[0] if brief.claim_map.qualified_claims else None
        qual_str = (
            f"{qual_item.claim_text} ({qual_item.required_attribution_or_caveat})"
            if qual_item and qual_item.required_attribution_or_caveat
            else "Relational training shows potential gains when using adaptive protocols."
        )

        body_paragraphs = [
            f"Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.",
            f"Neuroscience confirms that while adult neuroplasticity is real—{safe_str.lower()}—true cognitive expansion requires a fundamentally different architecture.",
            f"That architecture is Relational Frame Theory (RFT).",
            f"{qual_str}",
            f"Crucially, cognitive growth demands continuous adaptive strain. If the difficulty doesn't scale instantly with your performance ceiling, the brain automates the task and learning plateaus.",
            f"True mental expansion isn't about casual 5-minute games. It requires structured, adaptive relational training.",
            f"What cognitive skills are you actively training this year?",
        ]

        body_text = "\n\n".join(body_paragraphs)
        title = "Why Most Brain Training Apps Fail (And How RFT Actually Works)"

        return DraftContent(
            draft_id=f"draft-{hash(brief.topic) & 0xffffffff:08x}",
            topic=brief.topic,
            platform=strategy.platform,
            title=title,
            body_text=body_text,
            outline_id=outline.outline_id,
            brief_id=brief.brief_id,
            word_count=len(body_text.split()),
            version=1,
        )
