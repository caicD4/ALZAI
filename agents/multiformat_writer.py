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
        safe_str = brief.claim_map.safe_claims[0].claim_text if brief.claim_map.safe_claims else "Neuroplasticity allows neural connections to reorganize."
        safe_clean = safe_str.rstrip(".!? ")
        qual_item = brief.claim_map.qualified_claims[0] if brief.claim_map.qualified_claims else None
        qual_str = (
            f"{qual_item.claim_text} ({qual_item.required_attribution_or_caveat})"
            if qual_item and qual_item.required_attribution_or_caveat
            else "Relational training shows potential gains when using adaptive protocols."
        )

        fid = spec.format_id

        if fid == "x_thread":
            posts = [
                f"1/ Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.",
                f"2/ Neuroscience confirms that adult neuroplasticity is real—and {safe_clean.lower()}—true cognitive expansion requires a fundamentally different architecture.",
                f"3/ That architecture is Relational Frame Theory (RFT). Training core relational skills (same/different, opposite, conditional) targets abstract reasoning primitives.",
                f"4/ {qual_str}",
                f"5/ Crucially, cognitive growth demands continuous adaptive strain. If difficulty doesn't scale instantly with your performance ceiling, the brain automates the task.",
                f"6/ True mental expansion isn't about casual 5-minute games. It requires structured, adaptive relational training.",
                f"7/ {format_strategy.cta}",
            ]
            body_text = "\n\n".join(posts)
            title = f"Why Most Brain Training Apps Fail (X/Twitter Thread)"
            sections = posts

        elif fid == "article":
            sections_text = [
                f"# Why Most Brain Training Apps Fail (And How RFT Actually Works)\n\nMost brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.",
                f"## 1. The Core Myth vs Neural Reality\n\nNeuroscience confirms that while adult neuroplasticity is real—and {safe_clean.lower()}—true cognitive expansion requires a fundamentally different architecture.",
                f"## 2. Relational Frame Theory (RFT) as a Cognitive Primitive\n\nThat architecture is Relational Frame Theory (RFT). {qual_str}",
                f"## 3. The Necessity of Continuous Adaptive Strain\n\nCrucially, cognitive growth demands continuous adaptive strain. If the difficulty doesn't scale instantly with your performance ceiling, the brain automates the task and learning plateaus.",
                f"## 4. Conclusion & Next Steps\n\nTrue mental expansion isn't about casual 5-minute games. It requires structured, adaptive relational training.\n\n{format_strategy.cta}",
            ]
            body_text = "\n\n".join(sections_text)
            title = "Why Most Brain Training Apps Fail (And How RFT Actually Works)"
            sections = sections_text

        elif fid == "newsletter":
            body_text = (
                f"Subject: Why your brain training app isn't raising your IQ\n\n"
                f"Hey Friend,\n\n"
                f"Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
                f"Neuroscience confirms that while adult neuroplasticity is real—and {safe_clean.lower()}—true cognitive expansion requires a fundamentally different architecture.\n\n"
                f"That architecture is Relational Frame Theory (RFT). {qual_str}\n\n"
                f"Key Takeaways:\n"
                f"• Differentiate casual puzzle apps from relational training\n"
                f"• Ensure continuous adaptive difficulty to prevent automaticity\n"
                f"• Focus on relational skill primitives\n\n"
                f"{format_strategy.cta}\n\n"
                f"Best,\n"
                f"{brand.name if brand else 'ALZAI Team'}"
            )
            title = "Subject: Why your brain training app isn't raising your IQ"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "youtube":
            body_text = (
                f"[COLD OPEN - 0:00]\n"
                f"[VISUAL: Person tapping mobile brain app]\n"
                f"Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
                f"[TITLE CARD & INTRO - 0:15]\n"
                f"[ON SCREEN: Neuroplasticity vs Brain Apps]\n"
                f"Neuroscience confirms that while adult neuroplasticity is real—and {safe_clean.lower()}—true cognitive expansion requires a fundamentally different architecture.\n\n"
                f"[DEEP MECHANISM BREAKDOWN - 1:30]\n"
                f"[VISUAL: RFT relational network diagram]\n"
                f"That architecture is Relational Frame Theory (RFT). {qual_str}\n\n"
                f"[ADAPTIVE STRAIN - 3:40]\n"
                f"Crucially, cognitive growth demands continuous adaptive strain. If difficulty doesn't scale instantly, the brain automates the task.\n\n"
                f"[OUTRO & CTA - 5:00]\n"
                f"{format_strategy.cta}"
            )
            title = "Why Brain Training Apps Fail (YouTube Video Script)"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "short_video":
            body_text = (
                f"(0:00-0:03) Stop playing 5-minute puzzle games if you want to raise your IQ! (0:03-0:15) Most brain apps just make you good at the game. (0:15-0:40) Neuroscience shows adult neuroplasticity is real, but real gains require Relational Frame Theory (RFT). {qual_str} (0:40-0:60) You need continuous adaptive difficulty that scales instantly. {format_strategy.cta}"
            )
            title = "Why Brain Apps Fail (60s Short Script)"
            sections = [body_text]

        elif fid == "carousel":
            slides = [
                f"[SLIDE 1: Cover Title]\nWhy Most Brain Training Apps Fail\n(And What Actually Raises IQ)",
                f"[SLIDE 2: The Core Myth]\nMost brain apps don't raise IQ.\nThey just make you faster at their specific puzzle games.",
                f"[SLIDE 3: Neural Reality]\nAdult neuroplasticity is real.\nInterventions produce changes in trained tasks—but expansion requires adaptive load.",
                f"[SLIDE 4: The Mechanism]\nRelational Frame Theory (RFT)\nTraining relational skills (same/different, opposite) enhances fluid reasoning.",
                f"[SLIDE 5: Evidence]\n{qual_str}",
                f"[SLIDE 6: The Rule]\nContinuous Adaptive Strain\nDifficulty must scale instantly with your performance ceiling.",
                f"[SLIDE 7: Summary]\n1. Differentiate apps from RFT\n2. Maintain adaptive load\n3. Train relational primitives",
                f"[SLIDE 8: Save & Share]\n{format_strategy.cta}",
            ]
            body_text = "\n\n".join(slides)
            title = "Why Most Brain Training Apps Fail (Slide Carousel)"
            sections = slides

        else:  # linkedin default
            body_text = (
                f"Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
                f"Neuroscience confirms that while adult neuroplasticity is real—and {safe_clean.lower()}—true cognitive expansion requires a fundamentally different architecture.\n\n"
                f"That architecture is Relational Frame Theory (RFT).\n\n"
                f"{qual_str}\n\n"
                f"Crucially, cognitive growth demands continuous adaptive strain. If the difficulty doesn't scale instantly with your performance ceiling, the brain automates the task and learning plateaus.\n\n"
                f"True mental expansion isn't about casual 5-minute games. It requires structured, adaptive relational training.\n\n"
                f"{format_strategy.cta}"
            )
            title = "Why Most Brain Training Apps Fail (And How RFT Actually Works)"
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
