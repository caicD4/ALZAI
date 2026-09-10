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
Your task is to write publication-grade, original, platform-adapted content. You write ORIGINAL content derived from the ResearchBrief, ClaimMap, FormatStrategy, ContentOutline, and ContentFormatSpec — never a copy of existing content.

CRITICAL MULTI-FORMAT WRITING INSTRUCTIONS:
1. ORIGINALITY — SYNTHESIS, NEVER PARAPHRASE:
   - Do NOT reproduce distinctive wording, sentences, metaphors, or structure from ANY supplied content reference, outline, or source snippet.
   - Do NOT copy the phrasing of existing content you were told about (the Content Landscape).
   - Rewrite every idea in your own distinctive voice and structure. Find the fresh angle.

2. HONESTY WITHOUT BOREDOM:
   - You MUST NOT invent facts, statistics, quotes, numbers, or sources.
   - Distinguish FACT (state plainly, attribute when specific), REPORTED EVENT ("reported", "per the filing"), ALLEGATION (always attribute), OPINION/COMMENTARY (frame as your view or the argued view — encouraged for angle-driven content).
   - The user's framing is creative direction: a requested critical take should be written compellingly WITH credible counterpoints. Do NOT block on "can't verify".

3. PLATFORM-NATIVE STRUCTURE:
   - X/Twitter Thread: Generate 5-8 sequential posts. Each post must start with "1/", "2/", etc.
   - Carousel: Generate 5-8 slides. Each slide must start with "[SLIDE 1: Cover Title]", "[SLIDE 2: Problem]", etc.
   - YouTube Script: Include spoken cues and visual cues e.g. [VISUAL: ...], [PAUSE], [ON SCREEN].
   - Short Video Script: Include timestamp cues e.g. (0:00-0:03) and spoken captions.
   - Long-form Article: Use Markdown H2 (##) headers, clear section flow, and depth breakdown.
   - Newsletter: Conversational personal opening, subject line, bulleted takeaways, subscriber sign-off.
   - LinkedIn Post: Concise 200-400 words, short 1-2 sentence paragraphs, open-ended question CTA.
"""


def renumber_x_thread(body_text: str) -> str:
    """Ensures X/Twitter thread posts are strictly and sequentially numbered 1/, 2/, 3/, ..."""
    raw_posts = [s.strip() for s in body_text.split("\n\n") if s.strip()]
    if not raw_posts:
        return body_text

    renumbered = []
    for idx, post in enumerate(raw_posts, start=1):
        # Strip existing leading post numbers like "1/", "1. ", "Post 1:", "2/"
        clean_post = re.sub(r"^(?:\d+[\/\.\:]|\bPost\s+\d+[\:\/]?)\s*", "", post).strip()
        renumbered.append(f"{idx}/ {clean_post}")

    return "\n\n".join(renumbered)


class MultiFormatContentWriter:
    """Generates authentic, format-adapted ContentPiece assets directly from a ResearchBrief."""

    last_write_method: Optional[str] = None

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
                self.last_write_method = "gemini"
                if spec.format_id == "x_thread":
                    piece.body_text = renumber_x_thread(piece.body_text)
                    piece.sections = [s.strip() for s in piece.body_text.split("\n\n") if s.strip()]
                return piece

        self.last_write_method = "grounded_fallback"
        fallback_piece = self._write_fallback(brief, format_strategy, outline, spec, brand, target_voice)
        if spec.format_id == "x_thread":
            fallback_piece.body_text = renumber_x_thread(fallback_piece.body_text)
            fallback_piece.sections = [s.strip() for s in fallback_piece.body_text.split("\n\n") if s.strip()]

        return fallback_piece

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
            f"Formatting Rules: {spec.formatting_rules}\n"
            f"Selected Angle: {brief.recommended_strategy.selected_angle.angle_title if brief.recommended_strategy and brief.recommended_strategy.selected_angle else 'None'} | Thesis: {brief.recommended_strategy.thesis if brief.recommended_strategy else 'None'}\n"
            f"Content Landscape Differentiation: {brief.content_landscape.recommended_differentiation if brief.content_landscape else 'None'}\n"
            f"Content Gaps to Own: {brief.claim_map.content_gaps or 'None'}\n\n"
            f"Format Strategy Hook: {format_strategy.hook_direction}\n"
            f"Format Strategy Narrative: {format_strategy.narrative_structure}\n"
            f"Format Strategy Key Insights: {format_strategy.key_insights_to_emphasize}\n"
            f"Format Strategy Evidence: {format_strategy.evidence_to_reference}\n"
            f"Format Strategy CTA: {format_strategy.cta}\n\n"
            f"RESEARCH CLAIM MAP (HONESTY BOUNDARIES):\n"
            f"Safe Claims (grounded in sources, state as fact): {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims (MUST include attribution): {[{'claim': c.claim_text, 'attribution': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (frame as OPINION/commentary or attribute as allegation — never state as fact): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
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
                stage_label="MultiFormatWriter",
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
        subject = brief.topic
        if hasattr(brief, 'request_intent') and brief.request_intent and brief.request_intent.subject:
            subject = brief.request_intent.subject

        finding_stmts = [f.statement for f in brief.findings]
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

        hook = (
            format_strategy.hook_direction
            if hasattr(format_strategy, 'hook_direction') and format_strategy.hook_direction
            else ""
        )
        cta = (
            format_strategy.cta
            if hasattr(format_strategy, 'cta') and format_strategy.cta
            else ""
        )

        evidence_lines = []
        for stmt in finding_stmts[:3]:
            evidence_lines.append(stmt)
        if safe_str and safe_str not in evidence_lines:
            evidence_lines.append(safe_str)
        if qual_str and qual_str not in evidence_lines:
            evidence_lines.append(qual_str)

        evidence_text = "\n\n".join(evidence_lines) if evidence_lines else f"Evidence regarding {subject}."

        fid = spec.format_id

        if fid == "x_thread":
            posts = []
            if hook:
                posts.append(f"1/ {hook}")
            for idx, line in enumerate(evidence_lines[:4], start=2):
                posts.append(f"{idx}/ {line}")
            if cta:
                posts.append(f"{len(posts) + 1}/ {cta}")
            if not posts:
                posts = [f"1/ Findings on {subject}."]
            body_text = "\n\n".join(posts)
            title = f"{subject}"
            sections = posts

        elif fid == "article":
            sections_text = []
            if hook:
                sections_text.append(f"# {subject}\n\n{hook}")
            for idx, line in enumerate(evidence_lines[:4], start=1):
                sections_text.append(f"## {idx}. Findings\n\n{line}")
            if cta:
                sections_text.append(f"## Conclusion\n\n{cta}")
            if not sections_text:
                sections_text = [f"# {subject}\n\n{evidence_text}"]
            body_text = "\n\n".join(sections_text)
            title = subject
            sections = sections_text

        elif fid == "newsletter":
            body_text = (
                f"Subject: {subject}\n\n"
                f"Hey,\n\n"
            )
            if hook:
                body_text += f"{hook}\n\n"
            body_text += f"Here is what the evidence shows:\n\n"
            for line in evidence_lines[:4]:
                body_text += f"- {line}\n\n"
            if cta:
                body_text += f"{cta}\n\n"
            body_text += f"Best,\n{brand.name if brand else 'ALZAI Team'}"
            title = f"{subject}"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "youtube":
            body_text = ""
            if hook:
                body_text += f"[COLD OPEN]\n{hook}\n\n"
            body_text += f"[INTRO]\n{subject}\n\n"
            for line in evidence_lines[:3]:
                body_text += f"[BREAKDOWN]\n{line}\n\n"
            if cta:
                body_text += f"[OUTRO]\n{cta}"
            title = f"{subject}"
            sections = [s.strip() for s in body_text.split("\n\n") if s.strip()]

        elif fid == "short_video":
            parts = []
            if hook:
                parts.append(hook)
            parts.extend(evidence_lines[:2])
            if cta:
                parts.append(cta)
            body_text = " ".join(parts) if parts else f"Findings on {subject}."
            title = f"{subject}"
            sections = [body_text]

        elif fid == "carousel":
            slides = []
            slides.append(f"[SLIDE 1]\n{subject}")
            if hook:
                slides.append(f"[SLIDE 2]\n{hook}")
            for idx, line in enumerate(evidence_lines[:3], start=3):
                slides.append(f"[SLIDE {idx}]\n{line}")
            if cta:
                slides.append(f"[SLIDE {len(slides) + 1}]\n{cta}")
            if not slides:
                slides = [f"[SLIDE 1]\n{subject}"]
            body_text = "\n\n".join(slides)
            title = subject
            sections = slides

        else:  # linkedin default
            parts = []
            if hook:
                parts.append(hook)
            parts.extend(evidence_lines[:3])
            if cta:
                parts.append(cta)
            body_text = "\n\n".join(parts) if parts else f"Evidence regarding {subject}."
            title = subject
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

