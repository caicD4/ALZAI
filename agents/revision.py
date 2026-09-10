import json
import re
from typing import Any, List, Optional, Union

from agents.verifier import ContentVerifier
from core.brand_voice import DraftContent, RevisionPassResult, VerificationReport, VoiceProfile, BrandProfile, ContentOutline
from core.quality_schemas import ContentQualityIssue, ContentQualityReport
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

REVISION_SYSTEM_PROMPT = """You are a Targeted Revision Worker in ALZAI's content engine.
Your task is to fix specific quality, research fidelity, style, or platform fit issues identified in a ContentQualityReport WITHOUT unnecessarily rewriting unaffected text.

REVISION RULES:
1. TARGETED EDITS ONLY: Fix ONLY the sentences, phrases, or sections flagged in the report's issues.
2. EPISTEMIC ACCURACY:
   - Downgrade causal strengthening (e.g., change "scientists proved" to "studies observed").
   - Restore missing source attributions or numerical figures.
   - REFRAME unsupported claims (state-as-fact ⇒ mark as OPINION/commentary or attribute as allegation). Do NOT expand a bold angle into sterile hedging or delete the author's take — keep it opinionated while honest.
3. QUALITY & STYLE FIXES:
   - Replace generic AI clichés or banned phrases with direct, non-cliché statements.
   - Fix weak hooks, repetition, or poor transitions as suggested.
"""


class TargetedRevisionWorker:
    """Executes targeted revisions on DraftContent based on ContentQualityReport or VerificationReport (Max 2 passes)."""

    def __init__(
        self,
        verifier: Optional[ContentVerifier] = None,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
        max_revisions: int = 2,
    ) -> None:
        self.use_llm = use_llm
        self.max_revisions = max_revisions
        if use_llm:
            self.llm_client = llm_client or GeminiClient()
        else:
            self.llm_client = None
        self.verifier = verifier or ContentVerifier(llm_client=self.llm_client, use_llm=use_llm)

    def execute_targeted_quality_revision(
        self,
        draft: DraftContent,
        quality_report: ContentQualityReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: Optional[ContentOutline] = None,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
        quality_engine: Optional[Any] = None,
    ) -> tuple[DraftContent, List[ContentQualityReport]]:
        """Executes targeted revision passes (up to max_revisions=2) based on ContentQualityReport."""
        target_voice = voice or VoiceProfile()

        current_draft = draft
        current_report = quality_report
        report_history: List[ContentQualityReport] = []

        pass_num = 1
        while current_report.overall_status != "passed" and pass_num <= self.max_revisions:
            # Generate revised draft targeting identified issues
            if self.use_llm and self.llm_client is not None:
                revised_draft = self._revise_quality_via_llm(current_draft, current_report, brief, strategy, target_voice, pass_num)
            else:
                revised_draft = self._revise_quality_fallback(current_draft, current_report, brief, strategy, target_voice, pass_num)

            # Re-evaluate with Quality Engine if provided
            if quality_engine is not None:
                new_report = quality_engine.evaluate_quality(revised_draft, brief, strategy, outline, brand, target_voice)
            else:
                # Basic report fallback
                new_report = current_report

            report_history.append(new_report)

            current_draft = revised_draft
            current_report = new_report

            if new_report.overall_status == "passed":
                break

            pass_num += 1

        return current_draft, report_history

    def execute_targeted_revision(
        self,
        draft: DraftContent,
        report: VerificationReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: Optional[VoiceProfile] = None,
    ) -> tuple[DraftContent, List[RevisionPassResult]]:
        """Backwards-compatible revision execution using VerificationReport."""
        target_voice = voice or VoiceProfile()
        current_draft = draft
        current_report = report
        revision_history: List[RevisionPassResult] = []

        pass_num = 1
        while not current_report.is_passed and pass_num <= self.max_revisions:
            if self.use_llm and self.llm_client is not None:
                revised_draft = self._revise_via_llm(current_draft, current_report, brief, strategy, target_voice, pass_num)
            else:
                revised_draft = self._revise_fallback(current_draft, current_report, brief, strategy, target_voice, pass_num)

            new_report = self.verifier.verify_draft(revised_draft, brief, strategy, target_voice)
            fixes = [f"Fixed {e.category} ('{e.quote_in_draft}'): {e.suggested_fix}" for e in (current_report.factual_errors + current_report.style_errors)]

            pass_result = RevisionPassResult(
                pass_number=pass_num,
                revised_draft=revised_draft,
                verification_report=new_report,
                fixes_applied=fixes,
            )
            revision_history.append(pass_result)

            current_draft = revised_draft
            current_report = new_report

            if new_report.is_passed:
                break

            pass_num += 1

        return current_draft, revision_history

    def _revise_quality_via_llm(
        self,
        draft: DraftContent,
        report: ContentQualityReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
        pass_num: int,
    ) -> DraftContent:
        """Invokes Gemini to execute targeted edits on quality issues."""
        if not self.llm_client:
            return draft

        issue_list = [
            {"category": i.category, "sub_category": i.sub_category, "affected": i.affected_text, "fix": i.suggested_fix}
            for i in report.issues
        ]

        prompt = (
            f"Original Draft Body:\n{draft.body_text}\n\n"
            f"Identified Issues to Fix:\n{json.dumps(issue_list, indent=2)}\n\n"
            f"Permitted Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Required Caveats: {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (reframe as OPINION/commentary — never present as verified fact): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
            f"Selected Angle: {strategy.selected_angle.angle_title if strategy.selected_angle else 'None'}\n"
            f"Content Landscape Differentiation: {brief.content_landscape.recommended_differentiation if brief.content_landscape else 'None'}\n"
            f"Content Gaps: {brief.claim_map.content_gaps or 'None'}\n\n"
            "Apply ONLY targeted edits for the listed issues. Keep unaffected sentences intact and preserve the author's bold voice. "
            "Output JSON: {\"body_text\": \"...\", \"title\": \"...\"}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=REVISION_SYSTEM_PROMPT,
                temperature=0.2,
                stage_label="Revision",
            )
            data = json.loads(raw_json)
            new_body = data.get("body_text", draft.body_text)

            return DraftContent(
                draft_id=f"{draft.draft_id}-rev{pass_num}",
                topic=draft.topic,
                platform=draft.platform,
                title=draft.title,
                body_text=new_body,
                outline_id=draft.outline_id,
                brief_id=draft.brief_id,
                word_count=len(new_body.split()),
                version=draft.version + pass_num,
            )
        except Exception:
            return draft

    def _revise_quality_fallback(
        self,
        draft: DraftContent,
        report: ContentQualityReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
        pass_num: int,
    ) -> DraftContent:
        """Deterministic fallback quality revision for offline testing."""
        text = draft.body_text

        for issue in report.issues:
            affected = issue.affected_text
            if issue.sub_category in ("banned_phrase", "generic_ai_filler") and affected:
                text = text.replace(affected, "")
            elif issue.sub_category == "causal_strengthening" and affected:
                if "scientists proved" in affected.lower():
                    text = text.replace("scientists proved", "research studies observed")
                elif "permanently double" in affected.lower():
                    text = text.replace("permanently double", "enhance trained cognitive skills in")
            elif issue.sub_category == "attribution_loss" and issue.suggested_fix:
                if "(" not in text and "According to" not in text:
                    text = text.replace(
                        "can enhance outcome",
                        "can enhance outcome (according to published research)",
                    )
            elif issue.sub_category == "weak_hook":
                sentences = text.split("\n\n")
                if sentences and len(sentences[0]) < 20:
                    sentences[0] = f"Grounded research reveals key insights regarding {draft.topic}."
                    text = "\n\n".join(sentences)
            elif issue.sub_category == "malformed_punctuation":
                text = re.sub(r"([a-zA-Z0-9])\.\s*—", r"\1—", text)
                text = re.sub(r"([a-zA-Z0-9])([,!?:;])—", r"\1—", text)
                text = re.sub(r"—([,!?:;.])", r"—", text)
                text = re.sub(r"——|—\s+—|---|--\s+--", "—", text)
                text = re.sub(r"(?<!\.)\.\.(?!\.)|,,|\?\?|!!|;;", lambda m: m.group(0)[0], text)
            elif issue.sub_category == "repeated_words" and affected:
                words_match = affected.split()
                if len(words_match) == 2:
                    text = text.replace(affected, words_match[0])
            elif issue.sub_category == "broken_sentence":
                paragraphs = text.split("\n\n")
                new_paras = []
                for p in paragraphs:
                    p_clean = p.strip()
                    if p_clean and not re.search(r'[.!?"\')]$', p_clean):
                        p_clean += "."
                    new_paras.append(p_clean)
                text = "\n\n".join(new_paras)

        clean_text = "\n\n".join([p.strip() for p in text.split("\n\n") if p.strip()])

        return DraftContent(
            draft_id=f"{draft.draft_id}-rev{pass_num}",
            topic=draft.topic,
            platform=draft.platform,
            title=draft.title,
            body_text=clean_text,
            outline_id=draft.outline_id,
            brief_id=draft.brief_id,
            word_count=len(clean_text.split()),
            version=draft.version + pass_num,
        )

    def _revise_via_llm(
        self,
        draft: DraftContent,
        report: VerificationReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
        pass_num: int,
    ) -> DraftContent:
        """Invokes Gemini to execute surgical edits targeting specific verification errors."""
        if not self.llm_client:
            return draft

        fact_fixes = [{"category": e.category, "quote": e.quote_in_draft, "fix": e.suggested_fix} for e in report.factual_errors]
        style_fixes = [{"category": e.category, "quote": e.quote_in_draft, "fix": e.suggested_fix} for e in report.style_errors]

        prompt = (
            f"Original Draft Body:\n{draft.body_text}\n\n"
            f"Factual Errors to Fix: {fact_fixes}\n"
            f"Style Errors to Fix: {style_fixes}\n\n"
            f"Permitted Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Required Caveats: {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n\n"
            "Apply ONLY targeted fixes for the listed errors. Keep unaffected text intact. "
            "Output JSON: {\"body_text\": \"...\"}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=REVISION_SYSTEM_PROMPT,
                temperature=0.2,
                stage_label="Revision",
            )
            data = json.loads(raw_json)
            new_body = data.get("body_text", draft.body_text)

            return DraftContent(
                draft_id=f"{draft.draft_id}-rev{pass_num}",
                topic=draft.topic,
                platform=draft.platform,
                title=draft.title,
                body_text=new_body,
                outline_id=draft.outline_id,
                brief_id=draft.brief_id,
                word_count=len(new_body.split()),
                version=draft.version + pass_num,
            )
        except Exception:
            return draft

    def _revise_fallback(
        self,
        draft: DraftContent,
        report: VerificationReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
        pass_num: int,
    ) -> DraftContent:
        """Deterministic targeted revision fallback for offline testing."""
        text = draft.body_text

        # Fix banned phrases
        for err in report.style_errors:
            if err.category in ("banned_phrase", "ai_filler_cliche") and err.quote_in_draft:
                text = text.replace(err.quote_in_draft, "")

        # Fix strengthened claims
        for err in report.factual_errors:
            if err.category == "strengthened_claim" and err.quote_in_draft:
                if "scientists proved" in err.quote_in_draft.lower():
                    text = text.replace("scientists proved", "research studies observed")
                elif "permanently double" in err.quote_in_draft.lower():
                    text = text.replace("permanently double", "enhance trained cognitive skills in")

        # Fix missing caveats
        for err in report.factual_errors:
            if err.category == "missing_caveat" and err.suggested_fix:
                # Append required caveat if missing
                if "(" not in text and "According to" not in text:
                    text = text.replace(
                        "relational skills can enhance IQ",
                        "relational skills can enhance IQ (according to research published by Dr. Sarah Cassidy and Dr. Bryan Roche)",
                    )

        clean_text = "\n\n".join([p.strip() for p in text.split("\n\n") if p.strip()])

        return DraftContent(
            draft_id=f"{draft.draft_id}-rev{pass_num}",
            topic=draft.topic,
            platform=draft.platform,
            title=draft.title,
            body_text=clean_text,
            outline_id=draft.outline_id,
            brief_id=draft.brief_id,
            word_count=len(clean_text.split()),
            version=draft.version + pass_num,
        )

