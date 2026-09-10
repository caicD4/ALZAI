import json
import re
from typing import List, Optional

from core.brand_voice import BrandProfile, ContentOutline, DefaultVoiceProfile, VoiceProfile
from core.bundle_schemas import ContentPiece
from core.format_specs import FORMAT_CATALOG, ContentFormatSpec
from core.synthesis import ResearchBrief
from agents.format_planner import FormatStrategy
from tools.llm_client import GeminiClient

MULTIFORMAT_WRITER_SYSTEM_PROMPT = """You are a Lead Multi-Format Content Writer in ALZAI.
Your task is to write publication-grade, platform-adapted content directly from a ResearchBrief, ClaimMap, FormatStrategy, ContentOutline, and ContentFormatSpec.

CRITICAL MULTI-FORMAT WRITING INSTRUCTIONS:
1. DIRECT RESEARCH DERIVATION (MANDATORY):
   - You MUST write directly from the ResearchBrief and ClaimMap.
   - You MUST NOT upgrade claim strength (e.g. if research says "authors observed", do NOT say "scientists proved").
   - You MUST preserve required attributions (e.g., "According to Dr. Cassidy...", "Company X claims...").
   - You MUST NOT invent unsupported facts or numerical statistics.

2. PLATFORM-NATIVE STRUCTURE:
   - X/Twitter Thread: Generate 5-8 sequential posts. Each post must start with "1/", "2/", etc.
   - Carousel: Generate 5-8 slides. Each slide must start with "[SLIDE 1: Cover Title]", "[SLIDE 2: Problem]", etc.
   - YouTube Script: Include spoken cues and visual cues e.g. [VISUAL: ...], [PAUSE], [ON SCREEN].
   - Short Video Script: Include timestamp cues e.g. (0:00-0:03) and spoken captions.
   - Long-form Article: Use Markdown H2 (##) headers, clear section flow, and depth breakdown.
   - Newsletter: Conversational personal opening, subject line, bulleted takeaways, subscriber sign-off.
   - LinkedIn Post: Concise 200-400 words, short 1-2 sentence paragraphs, open-ended question CTA.
"""


class MultiFormatContentWriter:
    """Generates authentic, format-adapted ContentPiece assets directly from a ResearchBrief."""

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

    def write_format(
        self,
        brief: ResearchBrief,
        format_strategy: FormatStrategy,
        outline: ContentOutline,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentPiece:
        """Generates a complete ContentPiece for the given spec and strategy."""
        target_voice = voice or DefaultVoiceProfile()

        if self.use_llm and self.llm_client is not None:
            piece = self._write_via_llm(brief, format_strategy, outline, spec, brand, target_voice)
            if piece:
                return piece

        return self._write_fallback(brief, format_strategy, outline, spec, brand, target_voice)

    def _write_via_llm(
        self,
        brief: ResearchBrief,
        format_strategy: FormatStrategy,
        outline: ContentOutline,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile],
        voice: VoiceProfile,
    ) -> Optional[ContentPiece]:
        """Invokes Gemini to generate format-native content."""
        if not self.llm_client:
            return None

        prompt = (
            f"Topic: {brief.topic}\n"
            f"Format ID: {spec.format_id} ({spec.format_name})\n"
            f"Platform: {spec.platform}\n"
            f"Target Length: {spec.target_length}\n"
            f"Pacing: {spec.pacing}\n"
            f"Formatting Rules: {spec.formatting_rules}\n\n"
            f"Format Strategy Hook: {format_strategy.hook_direction}\n"
            f"Format Strategy Narrative: {format_strategy.narrative_structure}\n"
            f"Format Strategy Key Insights: {format_strategy.key_insights_to_emphasize}\n"
            f"Format Strategy Evidence: {format_strategy.evidence_to_reference}\n"
            f"Format Strategy CTA: {format_strategy.cta}\n\n"
            f"RESEARCH CLAIM MAP (STRICT BOUNDARIES):\n"
            f"Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims (MUST INCLUDE CAVEATS): {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (BANNED): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
            f"VOICE & STYLE RULES:\n"
            f"Formality: {voice.formality}, Directness: {voice.directness}, Banned Phrases: {voice.avoided_phrases}\n\n"
            "Generate output JSON matching:\n"
            "{\"title\": \"...\", \"body_text\": \"...\", \"sections\": [\"...\"]}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=MULTIFORMAT_WRITER_SYSTEM_PROMPT,
                temperature=0.3,
            )
            data = json.loads(raw_json)
            body = data.get("body_text", "")
            title = data.get("title", f"{brief.topic} ({spec.format_name})")
            sections = data.get("sections", [])
            if not sections and "\n\n" in body:
                sections = [s.strip() for s in body.split("\n\n") if s.strip()]

            words = len(body.split())
            est_duration = self._estimate_duration(spec.format_id, words, len(sections))

            return ContentPiece(
                content_id=f"piece-{spec.format_id}-{hash(body) & 0xffffffff:08x}",
                format_id=spec.format_id,
                platform=spec.platform,
                title=title,
                body_text=body,
                sections=sections,
                word_count=words,
                estimated_duration=est_duration,
                brief_id=brief.brief_id,
                version=1,
            )
        except Exception:
            return None

    def _write_fallback(
        self,
        brief: ResearchBrief,
        format_strategy: FormatStrategy,
        outline: ContentOutline,
        spec: ContentFormatSpec,
        brand: Optional[BrandProfile],
        voice: VoiceProfile,
    ) -> ContentPiece:
        """Deterministic fallback generator for all 7 formats."""
        topic = brief.topic
        safe_str = brief.claim_map.safe_claims[0].claim_text if brief.claim_map.safe_claims else f"Key evidence supports fundamental principles behind {topic}."
        qual_item = brief.claim_map.qualified_claims[0] if brief.claim_map.qualified_claims else None
        qual_str = (
            f"{qual_item.claim_text} ({qual_item.required_attribution_or_caveat})"
            if qual_item and qual_item.required_attribution_or_caveat
            else f"Current findings on {topic} suggest targeted benefits when specific protocols are applied."
        )

        hook = format_strategy.hook if hasattr(format_strategy, 'hook') and format_strategy.hook else f"Understanding the core shift in {topic}."
        cta = format_strategy.cta if hasattr(format_strategy, 'cta') and format_strategy.cta else f"What are your key insights on {topic}?"

        fid = spec.format_id

        if fid == "x_thread":
            posts = [
                f"1/ {hook}",
                f"2/ Grounded research reveals that {safe_str.rstrip('.')} when examining {topic}.",
                f"3/ A central mechanism driving this area is how underlying systems structure their core workflows.",
                f"4/ {qual_str}",
                f"5/ Crucially, evaluating {topic} requires separating established consensus from overhyped assumptions.",
                f"6/ Sustainable outcomes depend on disciplined, evidence-backed implementation.",
                f"7/ {cta}",
            ]
            body_text = "\n\n".join(posts)
            title = f"{topic}: Key Strategic Insights (X/Twitter Thread)"
            sections = posts

        elif fid == "article":
            sections_text = [
                f"# {topic}: A Comprehensive Strategic Overview\n\n{hook}",
                f"## 1. Grounded Research & Evidence\n\n{safe_str} When analyzing {topic}, research emphasizes structural clarity.",
                f"## 2. Core Operational Principles\n\n{qual_str}",
                f"## 3. Practical Implications & Tradeoffs\n\nNavigating {topic} requires balancing speed with systemic rigor to avoid common implementation pitfalls.",
                f"## 4. Strategic Outlook & Next Steps\n\n{cta}",
            ]
            body_text = "\n\n".join(sections_text)
            title = f"{topic}: Strategic Overview"
            sections = sections_text

        elif fid == "newsletter":
            body_text = (
                f"Subject: Strategic Breakdown: {topic}\n\n"
                f"Hey Friend,\n\n"
                f"{hook}\n\n"
                f"Here is what the evidence shows: {safe_str}\n\n"
                f"{qual_str}\n\n"
                f"Key Takeaways:\n"
                f"• Focus on verified underlying mechanisms rather than surface hype\n"
                f"• Account for specific operational boundary conditions\n"
                f"• Align implementation with measurable outcomes\n\n"
                f"{cta}\n\n"
                f"Best,\n"
                f"{brand.name if brand else 'ALZAI Team'}"
            )
            title = f"Subject: Strategic Breakdown: {topic}"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "youtube":
            body_text = (
                f"[COLD OPEN - 0:00]\n"
                f"[VISUAL: Key concept graphic for {topic}]\n"
                f"{hook}\n\n"
                f"[TITLE CARD & INTRO - 0:15]\n"
                f"[ON SCREEN: Research Breakdown - {topic}]\n"
                f"Grounded evidence demonstrates that {safe_str.rstrip('.')}.\n\n"
                f"[DEEP MECHANISM BREAKDOWN - 1:30]\n"
                f"[VISUAL: System architecture diagram]\n"
                f"{qual_str}\n\n"
                f"[PRACTICAL TAKEAWAYS - 3:40]\n"
                f"Successful execution requires aligning core strategy with verified constraints.\n\n"
                f"[OUTRO & CTA - 5:00]\n"
                f"{cta}"
            )
            title = f"Demystifying {topic} (YouTube Video Script)"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "short_video":
            body_text = (
                f"(0:00-0:05) {hook} (0:05-0:25) Here is what research shows: {safe_str.rstrip('.')}. "
                f"(0:25-0:45) {qual_str} (0:45-0:60) {cta}"
            )
            title = f"Why {topic} Matters (60s Short Script)"
            sections = [body_text]

        elif fid == "carousel":
            slides = [
                f"[SLIDE 1: Cover Title]\n{topic}\n(Strategic Breakdown)",
                f"[SLIDE 2: The Core Shift]\n{hook}",
                f"[SLIDE 3: Evidence Grounding]\n{safe_str}",
                f"[SLIDE 4: Key Nuance & Context]\n{qual_str}",
                f"[SLIDE 5: Strategic Takeaway]\nFocus on underlying mechanisms over superficial trends.",
                f"[SLIDE 6: Actionable Framework]\nApply structured evaluation protocols to your workflow.",
                f"[SLIDE 7: Summary]\n1. Ground decisions in evidence\n2. Respect operational limits\n3. Drive measurable outcomes",
                f"[SLIDE 8: Save & Share]\n{cta}",
            ]
            body_text = "\n\n".join(slides)
            title = f"{topic} (Slide Carousel)"
            sections = slides

        else:  # linkedin default
            body_text = (
                f"{hook}\n\n"
                f"Research demonstrates that {safe_str.rstrip('.')}.\n\n"
                f"{qual_str}\n\n"
                f"When building strategies around {topic}, success comes down to focusing on core principles rather than surface-level shortcuts.\n\n"
                f"{cta}"
            )
            title = f"{topic}: Strategic Perspectives"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        words = len(body_text.split())
        est_duration = self._estimate_duration(fid, words, len(sections))

        return ContentPiece(
            content_id=f"piece-{fid}-{hash(body_text) & 0xffffffff:08x}",
            format_id=fid,
            platform=spec.platform,
            title=title,
            body_text=body_text,
            sections=sections,
            word_count=words,
            estimated_duration=est_duration,
            brief_id=brief.brief_id,
            version=1,
        )

    @staticmethod
    def _estimate_duration(format_id: str, word_count: int, num_sections: int) -> str:
        """Estimates reading/speaking duration based on format characteristics."""
        if format_id == "x_thread":
            return f"{num_sections} posts (~2 min read)"
        elif format_id == "carousel":
            return f"{num_sections} slides (~1.5 min swipe)"
        elif format_id == "short_video":
            sec = max(15, min(60, int(word_count / 2.5)))
            return f"{sec} seconds"
        elif format_id == "youtube":
            minutes = round(word_count / 140, 1)
            return f"{minutes} minutes speech"
        else:
            minutes = max(1, round(word_count / 200, 1))
            return f"{minutes} min read"
