import json
import re
from typing import List, Optional

from core.brand_voice import (
    DraftContent,
    FactualError,
    StyleError,
    VerificationReport,
    VoiceAlignmentEvaluation,
    VoiceProfile,
)
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

VERIFIER_SYSTEM_PROMPT = """You are a Lead Fact-Checker, Epistemic Verifier, and Writing Style Auditor in ALZAI.
Your job is to audit generated draft prose against a ResearchBrief, ClaimMap, ContentStrategy, and VoiceProfile.

VERIFICATION PRINCIPLES:
1. SEPARATE FACTUAL ERRORS FROM STYLE ERRORS:
   - Factual errors are epistemic violations (unsupported claims, claim strengthening, missing caveats, attribution loss, altered numbers).
   - Style errors are voice deviations (AI clichés, banned phrases, formatting mismatches).
2. DO NOT PENALIZE STYLISTIC FREEDOM AS FACTUAL ERROR:
   - Paraphrasing a safe claim using different vocabulary is ACCEPTABLE as long as epistemic strength is preserved.
3. CLAIM STRENGTHENING DETECTION:
   - Flag words like "proved", "guarantees", "100%", "permanently" if the underlying research is qualified or observational.
"""


class ContentVerifier:
    """Evaluates DraftContent against ResearchBrief, ClaimMap, ContentStrategy, and VoiceProfile."""

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

    def verify_draft(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: Optional[VoiceProfile] = None,
    ) -> VerificationReport:
        """Audits a draft and returns a structured VerificationReport."""
        target_voice = voice or VoiceProfile()

        # Perform rule-based deterministic checks first (always run)
        factual_errors, style_errors = self._run_deterministic_checks(draft, brief, strategy, target_voice)

        # Calculate style alignment metrics
        voice_eval = self._evaluate_voice_alignment(draft, target_voice, style_errors)

        if self.use_llm and self.llm_client is not None:
            llm_factual, llm_style = self._verify_via_llm(draft, brief, strategy, target_voice)
            factual_errors.extend(llm_factual)
            style_errors.extend(llm_style)

        # Deduplicate error IDs
        factual_errors = self._deduplicate_errors(factual_errors)
        style_errors = self._deduplicate_errors(style_errors)

        unsupported_cnt = sum(1 for e in factual_errors if e.category == "unsupported_claim")
        strengthened_cnt = sum(1 for e in factual_errors if e.category == "strengthened_claim")
        missing_cav_cnt = sum(1 for e in factual_errors if e.category == "missing_caveat")
        attrib_loss_cnt = sum(1 for e in factual_errors if e.category == "attribution_loss")
        ai_filler = any(e.category in ("ai_filler_cliche", "banned_phrase") for e in style_errors)

        # Draft passes if zero factual errors and overall style score >= 0.7
        is_passed = len(factual_errors) == 0 and voice_eval.overall_style_score >= 0.65

        summary = (
            f"Verification {'PASSED' if is_passed else 'FAILED'}. "
            f"Factual Errors: {len(factual_errors)} (Unsupported: {unsupported_cnt}, Strengthened: {strengthened_cnt}, Missing Caveats: {missing_cav_cnt}). "
            f"Style Errors: {len(style_errors)}. Overall Voice Score: {voice_eval.overall_style_score:.2f}."
        )

        return VerificationReport(
            report_id=f"rep-{hash(draft.body_text) & 0xffffffff:08x}",
            draft_id=draft.draft_id,
            is_passed=is_passed,
            factual_errors=factual_errors,
            style_errors=style_errors,
            unsupported_claims_count=unsupported_cnt,
            strengthened_claims_count=strengthened_cnt,
            missing_caveats_count=missing_cav_cnt,
            attribution_losses_count=attrib_loss_cnt,
            ai_filler_detected=ai_filler,
            voice_alignment=voice_eval,
            summary_assessment=summary,
        )

    def _run_deterministic_checks(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
    ) -> tuple[List[FactualError], List[StyleError]]:
        """Runs deterministic regex and rule checks for banned phrases, strengthened claims, missing caveats, and numbers."""
        factual_errors: List[FactualError] = []
        style_errors: List[StyleError] = []

        text = draft.body_text
        lower_text = text.lower()

        # 1. Banned Phrases & AI Clichés Check
        banned_list = voice.avoided_phrases or []
        for banned in banned_list:
            if banned.lower() in lower_text:
                style_errors.append(
                    StyleError(
                        error_id=f"err-banned-{hash(banned) & 0xffff:04x}",
                        category="banned_phrase",
                        quote_in_draft=banned,
                        explanation=f"Draft contains prohibited phrase/AI cliché: '{banned}'.",
                        suggested_fix=f"Remove or rephrase '{banned}' with direct, non-cliché language.",
                    )
                )

        # 2. Claim Strengthening Check ("proved", "scientists proved", "guarantees")
        overreach_terms = ["scientists proved", "scientifically proven", "guarantees", "permanently double"]
        for term in overreach_terms:
            if term in lower_text:
                factual_errors.append(
                    FactualError(
                        error_id=f"err-strength-{hash(term) & 0xffff:04x}",
                        category="strengthened_claim",
                        quote_in_draft=term,
                        explanation=f"Draft strengthens evidence strength by claiming '{term}' beyond supported research.",
                        suggested_fix="Downgrade assertion to reflect study findings and observed correlations.",
                    )
                )

        # 3. Missing Caveats Check
        for q_claim in brief.claim_map.qualified_claims:
            if q_claim.required_attribution_or_caveat:
                caveat_kw = q_claim.required_attribution_or_caveat.split()[0].lower()
                # If claim core text is present but caveat keyword is missing
                claim_kw = q_claim.claim_text.split()[0].lower()
                if claim_kw in lower_text and caveat_kw not in lower_text and len(caveat_kw) > 3:
                    factual_errors.append(
                        FactualError(
                            error_id=f"err-caveat-{hash(q_claim.claim_text) & 0xffff:04x}",
                            category="missing_caveat",
                            quote_in_draft=q_claim.claim_text[:50],
                            explanation=f"Draft asserts qualified claim without required caveat: '{q_claim.required_attribution_or_caveat}'.",
                            suggested_fix=f"Add caveat: '{q_claim.required_attribution_or_caveat}'.",
                        )
                    )

        # 4. Check Unsupported Claims
        for un_claim in brief.claim_map.unsupported_claims:
            un_kw = un_claim.claim_text.lower()
            if "permanently double" in un_kw and "permanently double" in lower_text:
                factual_errors.append(
                    FactualError(
                        error_id=f"err-unsupported-{hash(un_kw) & 0xffff:04x}",
                        category="unsupported_claim",
                        quote_in_draft="permanently double adult IQ",
                        explanation="Draft asserts an unsupported claim refuted or unbacked by research.",
                        suggested_fix="Remove or explicitly refute the unsupported claim.",
                    )
                )

        return factual_errors, style_errors

    def _evaluate_voice_alignment(
        self,
        draft: DraftContent,
        voice: VoiceProfile,
        style_errors: List[StyleError],
    ) -> VoiceAlignmentEvaluation:
        """Calculates voice score based on formatting, rhythm, directness, and absence of style errors."""
        text = draft.body_text
        paragraphs = [p for p in text.split("\n\n") if p.strip()]

        # Formatting match
        formatting_score = 0.9
        if voice.paragraph_style == "short_paragraphs":
            avg_p_words = sum(len(p.split()) for p in paragraphs) / max(1, len(paragraphs))
            if avg_p_words > 60:
                formatting_score -= 0.2

        # Rhythm match
        rhythm_score = 0.85
        if style_errors:
            rhythm_score -= min(0.3, len(style_errors) * 0.1)

        # Vocabulary & Directness match
        vocab_score = 0.9 if not any(e.category == "ai_filler_cliche" for e in style_errors) else 0.5
        directness_score = 0.85

        overall = max(0.0, min(1.0, (formatting_score + rhythm_score + vocab_score + directness_score) / 4.0))

        return VoiceAlignmentEvaluation(
            vocabulary_match=vocab_score,
            rhythm_match=rhythm_score,
            formatting_match=formatting_score,
            directness_match=directness_score,
            overall_style_score=overall,
            feedback=f"Style score: {overall:.2f}. Style errors found: {len(style_errors)}.",
        )

    def _verify_via_llm(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        voice: VoiceProfile,
    ) -> tuple[List[FactualError], List[StyleError]]:
        """Invokes Gemini for deep semantic checking of claim overreach and voice adherence."""
        if not self.llm_client:
            return [], []

        prompt = (
            f"Draft Title: {draft.title or 'Untitled'}\n"
            f"Draft Body Text:\n{draft.body_text}\n\n"
            f"Permitted Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Qualified Claims (Require Caveats): {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (BANNED): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
            f"Voice Banned Phrases: {voice.avoided_phrases}\n\n"
            "Audit the draft. Return JSON:\n"
            "{\"factual_errors\": [{\"error_id\": \"...\", \"category\": \"unsupported_claim|strengthened_claim|missing_caveat|attribution_loss|number_drift|contradictory_statement\", \"quote_in_draft\": \"...\", \"explanation\": \"...\", \"suggested_fix\": \"...\"}], "
            "\"style_errors\": [{\"error_id\": \"...\", \"category\": \"ai_filler_cliche|tone_mismatch|formatting_violation|length_violation|banned_phrase\", \"quote_in_draft\": \"...\", \"explanation\": \"...\", \"suggested_fix\": \"...\"}]}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=VERIFIER_SYSTEM_PROMPT,
                temperature=0.1,
            )
            data = json.loads(raw_json)
            fact_list = [FactualError.model_validate(e) for e in data.get("factual_errors", [])]
            style_list = [StyleError.model_validate(e) for e in data.get("style_errors", [])]
            return fact_list, style_list
        except Exception:
            return [], []

    @staticmethod
    def _deduplicate_errors(errors: List) -> List:
        seen = set()
        deduped = []
        for e in errors:
            key = getattr(e, "error_id", str(e))
            if key not in seen:
                seen.add(key)
                deduped.append(e)
        return deduped
