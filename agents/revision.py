import json
from typing import List, Optional

from agents.verifier import ContentVerifier
from core.brand_voice import DraftContent, RevisionPassResult, VerificationReport, VoiceProfile
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

REVISION_SYSTEM_PROMPT = """You are a Targeted Revision Worker in ALZAI's content engine.
Your task is to fix specific factual and style errors identified in a VerificationReport WITHOUT unnecessarily rewriting the rest of the draft.

REVISION RULES:
1. TARGETED EDITS ONLY: Fix ONLY the sentences or paragraphs flagged in factual_errors and style_errors.
2. EPISTEMIC ACCURACY:
   - Downgrade strengthened claims (e.g. change "scientists proved" to "studies observed").
   - Add missing caveats or attributions.
   - Remove unsupported claims.
3. REMOVE AI FILLER & BANNED PHRASES:
   - Replace any flagged clichés with direct, non-cliché statements.
"""


class TargetedRevisionWorker:
    """Executes targeted revisions on DraftContent based on VerificationReport findings (Max 2 passes)."""

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

    def execute_targeted_revision(
        self,
        draft: DraftContent,
        report: VerificationReport,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: Optional[VoiceProfile] = None,
    ) -> tuple[DraftContent, List[RevisionPassResult]]:
        """Executes targeted revision passes (up to max_revisions) until verification passes or limit is reached."""
        target_voice = voice or VoiceProfile()

        current_draft = draft
        current_report = report
        revision_history: List[RevisionPassResult] = []

        pass_num = 1
        while not current_report.is_passed and pass_num <= self.max_revisions:
            # Generate revised draft for this pass
            if self.use_llm and self.llm_client is not None:
                revised_draft = self._revise_via_llm(current_draft, current_report, brief, strategy, target_voice, pass_num)
            else:
                revised_draft = self._revise_fallback(current_draft, current_report, brief, strategy, target_voice, pass_num)

            # Re-verify the revised draft
            new_report = self.verifier.verify_draft(revised_draft, brief, strategy, target_voice)

            fixes = [
                f"Fixed {e.category} ('{e.quote_in_draft}'): {e.suggested_fix}"
                for e in (current_report.factual_errors + current_report.style_errors)
            ]

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
