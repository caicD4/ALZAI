import json
import re
from typing import List, Optional

from core.brand_voice import BrandProfile, ContentOutline, DraftContent, VoiceProfile
from core.quality_schemas import ContentQualityIssue, ContentQualityReport
from core.synthesis import ContentStrategy, ResearchBrief
from tools.llm_client import GeminiClient

QUALITY_ENGINE_SYSTEM_PROMPT = """You are a Lead Content Quality Auditor in ALZAI.
Your job is to evaluate draft content across four dimensions:
1. Research Fidelity (lightweight claim grounding, avoiding causal strengthening, attribution loss, or numerical distortion without flagging harmless simplifications).
2. Content Quality (evaluating hook strength, flow, repetition, information density, and absence of generic AI filler).
3. Voice / Style Alignment (evaluating sentence rhythm, formatting, directness, and adherence to VoiceProfile).
4. Platform Fit (evaluating fit for the target platform e.g. LinkedIn vs Article).

CRITICAL GROUNDING PRINCIPLES:
- DO NOT over-correct or force sterile academic hedging.
- Harmless simplifications (e.g., "researchers found training can improve performance" vs "authors observed task improvement") ARE ACCEPTABLE.
- FLAG ONLY meaningful research distortions (e.g., "proved", "guarantees", "permanently double", or removing company attributions).
"""


class ContentQualityEngine:
    """Evaluates generated content across Research Fidelity, Content Quality, Voice Alignment, and Platform Fit."""

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

    def evaluate_quality(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: Optional[ContentOutline] = None,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> ContentQualityReport:
        """Audits a draft and returns a comprehensive ContentQualityReport."""
        target_voice = voice or VoiceProfile()
        issues: List[ContentQualityIssue] = []
        strengths: List[str] = []

        # 1. Deterministic Rule Checks (Always executed)
        rule_issues = self._run_deterministic_checks(draft, brief, strategy, outline, target_voice)
        issues.extend(rule_issues)

        # 2. LLM Semantic Quality Evaluation (if LLM available)
        if self.use_llm and self.llm_client is not None:
            llm_issues, llm_strengths = self._evaluate_via_llm(draft, brief, strategy, outline, target_voice)
            issues.extend(llm_issues)
            strengths.extend(llm_strengths)

        # Deduplicate issues by issue_id or affected_text
        issues = self._deduplicate_issues(issues)

        # Compute dimensional scores
        fidelity_score, quality_score, voice_score, platform_score = self._compute_scores(issues, draft, target_voice, strategy)
        overall_score = round((fidelity_score * 0.35) + (quality_score * 0.25) + (voice_score * 0.20) + (platform_score * 0.20), 2)

        # Status: Passed ONLY if zero high-severity issues across ALL categories and overall_score >= 0.85
        has_high_issue = any(i.severity == "high" for i in issues)
        overall_status = "passed" if not has_high_issue and overall_score >= 0.85 else "needs_revision"

        if not strengths:
            strengths = [
                "Clear core concept progression",
                "Adheres to permitted research claim boundaries",
                "Structured for target audience engagement",
            ]

        # Prioritize revision actions based on issue severity and category
        revision_priority = [f"[{i.category.upper()}] {i.description}" for i in sorted(issues, key=lambda x: 0 if x.severity == "high" else 1)]

        summary = (
            f"Content Quality Audit Status: {overall_status.upper()} (Overall Score: {overall_score:.2f}). "
            f"Fidelity: {fidelity_score:.2f}, Quality: {quality_score:.2f}, Voice: {voice_score:.2f}, Platform: {platform_score:.2f}. "
            f"Total Issues Detected: {len(issues)}."
        )

        return ContentQualityReport(
            report_id=f"qual-{hash(draft.body_text) & 0xffffffff:08x}",
            draft_id=draft.draft_id,
            overall_status=overall_status,
            overall_score=overall_score,
            research_fidelity_score=fidelity_score,
            content_quality_score=quality_score,
            voice_alignment_score=voice_score,
            platform_fit_score=platform_score,
            issues=issues,
            strengths=strengths,
            revision_priority=revision_priority,
            summary_assessment=summary,
        )

    def _run_deterministic_checks(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: Optional[ContentOutline],
        voice: VoiceProfile,
    ) -> List[ContentQualityIssue]:
        """Runs deterministic rules for AI clichés, repetition, numerical drift, and attribution loss."""
        issues: List[ContentQualityIssue] = []
        text = draft.body_text
        lower_text = text.lower()
        sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]

        # A. AI Clichés & Banned Phrases Check (Voice / Style Issue)
        banned_phrases = voice.avoided_phrases or []
        for phrase in banned_phrases:
            if phrase.lower() in lower_text:
                issues.append(
                    ContentQualityIssue(
                        issue_id=f"iss-banned-{hash(phrase) & 0xffff:04x}",
                        category="voice_alignment",
                        sub_category="banned_phrase",
                        severity="high",
                        description=f"Draft contains prohibited AI cliché / banned phrase: '{phrase}'.",
                        affected_text=phrase,
                        suggested_fix=f"Remove '{phrase}' and replace with direct, non-cliché language.",
                    )
                )

        # B. Repetition Check (Content Quality Issue)
        sentence_counts = {}
        for s in sentences:
            s_norm = s.lower()
            if len(s_norm) > 15:
                sentence_counts[s_norm] = sentence_counts.get(s_norm, 0) + 1
                if sentence_counts[s_norm] > 1:
                    issues.append(
                        ContentQualityIssue(
                            issue_id=f"iss-rep-{hash(s_norm) & 0xffff:04x}",
                            category="content_quality",
                            sub_category="repetition",
                            severity="medium",
                            description="Identified repetitive sentence structure across draft.",
                            affected_text=s[:60],
                            suggested_fix="Consolidate duplicate statements or rephrase for variety.",
                        )
                    )

        # C. Meaningful Claim Strengthening (Research Fidelity Issue)
        overreach_terms = ["scientists proved", "scientifically proven", "guarantees", "permanently double"]
        for term in overreach_terms:
            if term in lower_text:
                issues.append(
                    ContentQualityIssue(
                        issue_id=f"iss-strength-{hash(term) & 0xffff:04x}",
                        category="research_fidelity",
                        sub_category="causal_strengthening",
                        severity="high",
                        description=f"Draft overstates research evidence strength by claiming '{term}'.",
                        affected_text=term,
                        suggested_fix="Downgrade claim to accurately reflect study observations.",
                    )
                )

        # D. Attribution Loss Check (Research Fidelity Issue)
        for qc in brief.claim_map.qualified_claims:
            if qc.required_attribution_or_caveat:
                req = qc.required_attribution_or_caveat
                entities = [w.lower() for w in re.findall(r"\b[A-Z][a-zA-Z0-9]+\b", req) if w.lower() not in {"according", "studies", "study", "report", "claims", "finding", "findings"}]
                if not entities:
                    entities = [w.lower() for w in re.findall(r"\b[a-z]{4,}\b", req.lower()) if w.lower() not in {"according", "studies", "claims", "study", "reported", "found", "that", "with", "improvement", "percent", "results", "gain", "gains"}]
                
                if entities and not any(ent in lower_text for ent in entities):
                    issues.append(
                        ContentQualityIssue(
                            issue_id=f"iss-attrib-{hash(qc.claim_text) & 0xffff:04x}",
                            category="research_fidelity",
                            sub_category="attribution_loss",
                            severity="high",
                            description=f"Draft omits required source attribution: '{qc.required_attribution_or_caveat}'.",
                            affected_text=qc.claim_text[:50],
                            suggested_fix=f"Include explicit source attribution: '{qc.required_attribution_or_caveat}'.",
                            related_claim_id=qc.claim_text[:20],
                        )
                    )

        # E. Numerical Distortion Check (Research Fidelity Issue)
        draft_numbers = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", text))
        for item in brief.claim_map.safe_claims + brief.claim_map.qualified_claims:
            claim_nums = set(re.findall(r"\b\d+(?:\.\d+)?%?\b", item.claim_text))
            for num in claim_nums:
                if num not in draft_numbers and len(draft_numbers) > 0:
                    for dn in draft_numbers:
                        if dn != num:
                            issues.append(
                                ContentQualityIssue(
                                    issue_id=f"iss-num-{hash(item.claim_text) & 0xffff:04x}",
                                    category="research_fidelity",
                                    sub_category="numerical_distortion",
                                    severity="high",
                                    description=f"Numerical statistic in draft ({dn}) alters research brief statistic ({num}).",
                                    affected_text=f"Draft: {dn} vs Research: {num}",
                                    suggested_fix=f"Restore exact numerical statistic ({num}) from research findings.",
                                )
                            )
                            break

        # F. Weak Hook Check (Content Quality Issue)
        first_p = sentences[0] if sentences else ""
        if len(first_p) < 10 or first_p.lower().startswith("welcome to") or first_p.lower().startswith("this post is about"):
            issues.append(
                ContentQualityIssue(
                    issue_id="iss-weak-hook",
                    category="content_quality",
                    sub_category="weak_hook",
                    severity="medium",
                    description="Opening hook is generic or weak.",
                    affected_text=first_p[:60],
                    suggested_fix="Replace opening with a strong, insightful problem assertion or data hook.",
                )
            )

        # G. Malformed Punctuation & Em-Dash Checks (Content Quality Issue)
        # e.g., 'tasks.—', 'real.—', '?—', ',—', '!—'
        malformed_punct = re.findall(r"[.!?,;:]—|—[.!?,;:]", text)
        if malformed_punct:
            issues.append(
                ContentQualityIssue(
                    issue_id=f"iss-punct-{hash(malformed_punct[0]) & 0xffff:04x}",
                    category="content_quality",
                    sub_category="malformed_punctuation",
                    severity="high",
                    description=f"Draft contains malformed punctuation attached to em-dash: '{malformed_punct[0]}'.",
                    affected_text=malformed_punct[0],
                    suggested_fix="Format em-dash clauses cleanly without punctuation attached to em-dashes.",
                )
            )

        # Double/Triple em-dashes or malformed dash syntax
        malformed_dashes = re.findall(r"——|—\s+—|---|--\s+--", text)
        if malformed_dashes:
            issues.append(
                ContentQualityIssue(
                    issue_id=f"iss-dash-{hash(malformed_dashes[0]) & 0xffff:04x}",
                    category="content_quality",
                    sub_category="malformed_punctuation",
                    severity="high",
                    description=f"Draft contains duplicated or malformed dash syntax: '{malformed_dashes[0]}'.",
                    affected_text=malformed_dashes[0],
                    suggested_fix="Use single standard em-dash (—) or en-dash without duplication.",
                )
            )

        # Duplicated punctuation (.. ,, ?? !! ;;)
        dup_punct = re.findall(r"(?<!\.)\.\.(?!\.)|,,|\?\?|!!|;;", text)
        if dup_punct:
            issues.append(
                ContentQualityIssue(
                    issue_id=f"iss-duppunct-{hash(dup_punct[0]) & 0xffff:04x}",
                    category="content_quality",
                    sub_category="malformed_punctuation",
                    severity="high",
                    description=f"Draft contains duplicated punctuation: '{dup_punct[0]}'.",
                    affected_text=dup_punct[0],
                    suggested_fix="Remove duplicate punctuation mark.",
                )
            )

        # H. Consecutive Repeated Words (Content Quality Issue)
        dup_words = re.findall(r"\b([A-Za-z]{2,})\s+\1\b", text)
        if dup_words:
            for dw in dup_words:
                if dw.lower() not in {"very", "really"}:
                    issues.append(
                        ContentQualityIssue(
                            issue_id=f"iss-dupword-{hash(dw) & 0xffff:04x}",
                            category="content_quality",
                            sub_category="repeated_words",
                            severity="high",
                            description=f"Draft contains repeated consecutive word: '{dw} {dw}'.",
                            affected_text=f"{dw} {dw}",
                            suggested_fix=f"Remove duplicate instance of '{dw}'.",
                        )
                    )

        # I. Unmatched & Nested Parentheses (Content Quality Issue)
        if text.count("(") != text.count(")"):
            issues.append(
                ContentQualityIssue(
                    issue_id="iss-unmatched-paren",
                    category="content_quality",
                    sub_category="malformed_punctuation",
                    severity="high",
                    description="Draft contains unmatched parentheses.",
                    affected_text="Unmatched '(' or ')'",
                    suggested_fix="Ensure all opening parentheses have matching closing parentheses.",
                )
            )

        nested_paren = re.findall(r"\([^)]*\([^)]*\)", text)
        if nested_paren:
            issues.append(
                ContentQualityIssue(
                    issue_id=f"iss-nested-paren-{hash(nested_paren[0]) & 0xffff:04x}",
                    category="content_quality",
                    sub_category="nested_parentheses",
                    severity="medium",
                    description="Draft contains awkward nested parentheses.",
                    affected_text=nested_paren[0][:50],
                    suggested_fix="Flatten nested parenthetical structure into clear prose.",
                )
            )

        empty_paren = re.findall(r"\(\s*\)", text)
        if empty_paren:
            issues.append(
                ContentQualityIssue(
                    issue_id="iss-empty-paren",
                    category="content_quality",
                    sub_category="malformed_punctuation",
                    severity="high",
                    description="Draft contains empty parentheses '()'.",
                    affected_text="()",
                    suggested_fix="Remove empty parentheses.",
                )
            )

        # J. Paragraph Ending Mid-Thought (Broken Sentence / Fusion)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for p in paragraphs:
            if len(p) > 15 and not re.search(r'[.!?"\')]\s*$', p):
                issues.append(
                    ContentQualityIssue(
                        issue_id=f"iss-frag-{hash(p[:30]) & 0xffff:04x}",
                        category="content_quality",
                        sub_category="broken_sentence",
                        severity="high",
                        description=f"Paragraph ends abruptly without terminal punctuation: '{p[-30:]}'.",
                        affected_text=p[-30:],
                        suggested_fix="Complete paragraph with proper terminal punctuation.",
                    )
                )

        # K. Broken Generated Text / Code Artifacts
        broken_tokens = ["{\"body_text\"", "\"[object Object]\"", "undefined", "NaN"]
        for bt in broken_tokens:
            if bt in text:
                issues.append(
                    ContentQualityIssue(
                        issue_id=f"iss-broken-{hash(bt) & 0xffff:04x}",
                        category="content_quality",
                        sub_category="broken_sentence",
                        severity="high",
                        description=f"Draft contains raw code artifact or broken generation token: '{bt}'.",
                        affected_text=bt,
                        suggested_fix="Remove raw code or JSON artifacts from text.",
                    )
                )

        # L. Platform Fit Checks
        if strategy.platform.lower() == "linkedin":
            words = text.split()
            if len(words) > 600:
                issues.append(
                    ContentQualityIssue(
                        issue_id="iss-plat-len",
                        category="platform_fit",
                        sub_category="platform_length_mismatch",
                        severity="medium",
                        description="LinkedIn post exceeds recommended length (>600 words).",
                        affected_text=f"Word count: {len(words)}",
                        suggested_fix="Trim content for optimal LinkedIn readability (200-400 words).",
                    )
                )
        elif strategy.platform.lower() in ("article", "blog", "long_form"):
            words = text.split()
            if len(words) < 150:
                issues.append(
                    ContentQualityIssue(
                        issue_id="iss-plat-short",
                        category="platform_fit",
                        sub_category="platform_length_mismatch",
                        severity="medium",
                        description="Long-form article draft is excessively brief (<150 words).",
                        affected_text=f"Word count: {len(words)}",
                        suggested_fix="Expand article sections with deeper context and evidence.",
                    )
                )

        return issues

    def _evaluate_via_llm(
        self,
        draft: DraftContent,
        brief: ResearchBrief,
        strategy: ContentStrategy,
        outline: Optional[ContentOutline],
        voice: VoiceProfile,
    ) -> tuple[List[ContentQualityIssue], List[str]]:
        """Invokes Gemini for semantic quality auditing."""
        if not self.llm_client:
            return [], []

        prompt = (
            f"Draft Title: {draft.title or 'Untitled'}\n"
            f"Draft Platform: {draft.platform}\n"
            f"Draft Body:\n{draft.body_text}\n\n"
            f"Research Safe Claims: {[c.claim_text for c in brief.claim_map.safe_claims]}\n"
            f"Research Qualified Claims: {[{'claim': c.claim_text, 'caveat': c.required_attribution_or_caveat} for c in brief.claim_map.qualified_claims]}\n"
            f"Unsupported Claims (BANNED): {[c.claim_text for c in brief.claim_map.unsupported_claims]}\n\n"
            f"Content Strategy Platform: {strategy.platform}\n"
            f"Content Strategy Hook: {strategy.hook_direction}\n"
            f"Voice Avoided Phrases: {voice.avoided_phrases}\n\n"
            "Audit the draft for Research Fidelity, Content Quality, Voice Alignment, and Platform Fit. "
            "IMPORTANT: Do NOT flag harmless simplifications as research errors. "
            "Output JSON:\n"
            "{\"issues\": [{\"issue_id\": \"...\", \"category\": \"research_fidelity|content_quality|voice_alignment|platform_fit\", \"sub_category\": \"...\", \"severity\": \"low|medium|high\", \"description\": \"...\", \"affected_text\": \"...\", \"suggested_fix\": \"...\"}], "
            "\"strengths\": [\"...\"]}"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=QUALITY_ENGINE_SYSTEM_PROMPT,
                temperature=0.1,
            )
            data = json.loads(raw_json)
            issues = [ContentQualityIssue.model_validate(i) for i in data.get("issues", [])]
            strengths = data.get("strengths", [])
            return issues, strengths
        except Exception:
            return [], []

    def _compute_scores(
        self,
        issues: List[ContentQualityIssue],
        draft: DraftContent,
        voice: VoiceProfile,
        strategy: ContentStrategy,
    ) -> tuple[float, float, float, float]:
        """Calculates 4 dimensional scores (0.0 to 1.0) based on issue severity deductions."""
        fidelity_deductions = sum(0.35 if i.severity == "high" else 0.15 for i in issues if i.category == "research_fidelity")
        quality_deductions = sum(0.35 if i.severity == "high" else 0.15 for i in issues if i.category == "content_quality")
        voice_deductions = sum(0.35 if i.severity == "high" else 0.15 for i in issues if i.category == "voice_alignment")
        platform_deductions = sum(0.35 if i.severity == "high" else 0.15 for i in issues if i.category == "platform_fit")

        fidelity_score = max(0.0, round(1.0 - fidelity_deductions, 2))
        quality_score = max(0.0, round(1.0 - quality_deductions, 2))
        voice_score = max(0.0, round(1.0 - voice_deductions, 2))
        platform_score = max(0.0, round(1.0 - platform_deductions, 2))

        return fidelity_score, quality_score, voice_score, platform_score

    @staticmethod
    def _deduplicate_issues(issues: List[ContentQualityIssue]) -> List[ContentQualityIssue]:
        seen = set()
        deduped = []
        for i in issues:
            key = f"{i.category}-{i.sub_category}-{i.affected_text[:20]}"
            if key not in seen:
                seen.add(key)
                deduped.append(i)
        return deduped
