import json
import re
from typing import Any, List, Literal, Optional, Set
from pydantic import BaseModel, Field

from core.evidence import EvidenceItem, ResearchInsight
from core.research_plan import ResearchPlan
from core.synthesis import (
    ClaimMap,
    ClaimMapEntry,
    ContentAngle,
    ContentStrategy,
    Finding,
    ResearchBrief,
)
from tools.llm_client import GeminiClient

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "are",
    "what", "how", "why", "with", "about", "by", "from", "as", "it", "this", "that",
    "can", "be", "do", "does", "did", "write", "me", "post", "actual", "actually"
}


class SynthesizedBriefPayload(BaseModel):
    """Raw structured LLM response payload for research synthesis."""

    findings: List[Finding] = Field(default_factory=list)
    claim_map: ClaimMap
    key_mechanisms: List[str] = Field(default_factory=list)
    case_studies_and_examples: List[str] = Field(default_factory=list)
    research_gaps: List[str] = Field(default_factory=list)
    content_angles: List[ContentAngle] = Field(default_factory=list)
    recommended_strategy: ContentStrategy


SYNTHESIZER_SYSTEM_PROMPT = """You are a Research Synthesizer and Content Strategist in ALZAI's content creation engine.
Your task is to analyze extracted research insights, construct a ClaimMap, reconcile conflicting accounts, and design compelling content strategies grounded in what was actually retrieved.

CRITICAL RULES:
1. EVERY finding and claim MUST be derived from the actual extracted insights provided below. Do NOT invent, fabricate, or hallucinate research findings.
2. Do NOT use generic filler phrasing like "core mechanisms", "functional workflows", or "operational trade-offs" unless those exact concepts appear in the provided evidence.
3. The user's request is CREATIVE DIRECTION: it tells you what content they want (e.g. critical content about Elon Musk, an explanation of Mixture of Experts). Do NOT test whether the user's framing is true; instead gather the strongest material that supports compelling content while staying honest about what sources actually say.
4. Distinguish, for the writer:
   - FACT (directly stated/measured in retrieved sources)
   - REPORTED EVENT (sources report it happened)
   - ALLEGATION (sources report an accusation)
   - OPINION / INTERPRETATION / PREDICTION / COMMENTARY (attributed or clearly interpretive)
   Use plain language in claim_map, e.g. attribution like "critics say", "reported", "per a 2023 survey" to preserve honesty WITHOUT blocking content.
5. If evidence is thin, say so in research_gaps/content_gaps so the writer can address gaps creatively with opinion and framing — do NOT refuse to create content.
6. Safe claims = direct restatements of evidence. Qualified claims = supported but need attribution. Unsupported = evidence does not support — writer must frame as opinion/commentary.
7. Preserve attribution from the original insights. Do not strip source attributions.
"""


class ResearchSynthesizer:
    """Synthesizes raw research insights into structured ResearchBrief, ClaimMap, and ContentStrategy models.

    Synthesis NEVER blocks content creation for "insufficient evidence". It guides
    the writer on what is grounded (fact/attribution) versus what is commentary.
    """

    last_synthesis_method: Optional[str] = None
    last_synthesis_error: Optional[str] = None

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

    def synthesize_research(
        self,
        plan: ResearchPlan,
        raw_insights: List[EvidenceItem],
        user_topic: str,
        content_landscape: Optional[Any] = None,
    ) -> ResearchBrief:
        total_raw = len(raw_insights) if raw_insights else 0

        retained_insights = self._filter_relevant_insights(raw_insights, user_topic, plan)
        rejected_count = total_raw - len(retained_insights)

        if self.use_llm and self.llm_client is not None:
            brief, error = self._synthesize_via_llm(plan, retained_insights, user_topic, total_raw, rejected_count, content_landscape)
            if brief:
                self.last_synthesis_method = "gemini"
                self.last_synthesis_error = None
                return brief
            self.last_synthesis_method = "grounded_fallback"
            self.last_synthesis_error = error or "Unknown LLM error"
            print(f"[Synthesis] Gemini failed ({self.last_synthesis_error}); using grounded deterministic fallback")

        else:
            self.last_synthesis_method = "grounded_fallback"
            self.last_synthesis_error = "LLM disabled" if not self.use_llm else "No LLM client"

        return self._synthesize_fallback(plan, retained_insights, user_topic, total_raw, rejected_count, content_landscape)

    def _filter_relevant_insights(
        self,
        insights: List[EvidenceItem],
        topic: str,
        plan: ResearchPlan,
    ) -> List[EvidenceItem]:
        if not insights:
            return []

        topic_context = f"{topic} {' '.join([q.question for q in (plan.questions or [])])}".lower()
        raw_words = set(re.findall(r"\w+", topic_context))
        topic_terms = {w for w in raw_words if len(w) > 2 and w not in STOP_WORDS}

        intent = plan.request_intent
        if intent:
            if intent.subject:
                for w in re.findall(r"\w+", intent.subject.lower()):
                    if len(w) > 2 and w not in STOP_WORDS:
                        topic_terms.add(w)
            for entity in (intent.key_entities or []):
                for w in re.findall(r"\w+", entity.lower()):
                    if len(w) > 2 and w not in STOP_WORDS:
                        topic_terms.add(w)
            for concept in (intent.key_concepts or []):
                for w in re.findall(r"\w+", concept.lower()):
                    if len(w) > 2 and w not in STOP_WORDS:
                        topic_terms.add(w)

        if not topic_terms:
            return insights

        intent = plan.request_intent
        is_investigation = intent and intent.intent_type in ("claim_investigation", "critique")

        filtered: List[EvidenceItem] = []
        for item in insights:
            combined = f"{item.verbatim_quote} {item.claim_summary} {item.relevance_explanation or ''}".lower()

            if ("autism" in combined or "autism spectrum" in combined or "cdc" in combined) and "neuroplasticity" not in topic.lower():
                if "iq" in topic.lower() or "neuroplasticity" in topic.lower() or "rft" in topic.lower():
                    continue

            if is_investigation:
                filtered.append(item)
                continue

            matched = False
            for term in topic_terms:
                t_stem = term.rstrip("s") if len(term) > 3 else term
                if t_stem in combined or term in combined:
                    matched = True
                    break

            if matched:
                filtered.append(item)

        return filtered

    def _build_llm_prompt(
        self,
        plan: ResearchPlan,
        insights: List[EvidenceItem],
        topic: str,
        content_landscape: Optional[Any] = None,
    ) -> str:
        intent = plan.request_intent

        intent_block = ""
        if intent:
            intent_block = (
                f"REQUEST INTENT (from semantic interpreter):\n"
                f"  Subject: {intent.subject}\n"
                f"  Intent Type: {intent.intent_type}\n"
                f"  Proposition: {intent.proposition or 'None'}\n"
                f"  Research Goal: {intent.research_goal}\n"
                f"  Stance: {intent.stance}\n"
                f"  Key Entities: {', '.join(intent.key_entities) if intent.key_entities else 'None'}\n"
                f"  Key Concepts: {', '.join(intent.key_concepts) if intent.key_concepts else 'None'}\n"
            )
            if intent.proposition:
                intent_block += (
                    f"\nUSER FRAMING (CREATIVE DIRECTION):\n"
                    f"The user framed the request as: \"{intent.proposition}\"\n"
                    f"This is the angle/opinion the user wants content to argue, explore, or respond to.\n"
                    f"Your task: gather the strongest research material supporting that direction, PLUS honest "
                    f"counterpoints/nuance. Do NOT treat the framing as a scientific truth claim to adjudicate, "
                    f"but DO keep facts honest: attribute, distinguish fact from allegation/opinion, and never "
                    f"fabricate evidence.\n"
                )

        landscape_block = ""
        if content_landscape is not None and getattr(content_landscape, "reference_ids", []):
            landscape_block = (
                f"\nCONTENT LANDSCAPE (existing content found in the wild — DO NOT repeat these angles verbatim):\n"
                f"  References analyzed: {content_landscape.total_references}\n"
                f"  Dominant angles: {', '.join(content_landscape.dominant_angles)}\n"
                f"  Saturated angles: {', '.join(content_landscape.saturated_angles)}\n"
                f"  Content gaps: {', '.join(content_landscape.content_gaps)}\n"
                f"  Possible original angles: {', '.join(content_landscape.possible_original_angles)}\n"
                f"  Recommended differentiation: {content_landscape.recommended_differentiation}\n"
            )

        insight_summaries = []
        for idx, item in enumerate(insights[:25], start=1):
            insight_summaries.append(
                f"[{idx}] (ID: {item.evidence_id}) Quote: \"{item.verbatim_quote[:200]}\" | "
                f"Summary: {item.claim_summary} | Type: {item.insight_type} | Role: {item.source_role} | "
                f"Attribution: {item.attribution or 'None'} | Phrasing: {item.suggested_writer_phrasing or 'None'}"
                + (f" | Limitations: {item.limitations}" if item.limitations else "")
            )

        prompt = (
            f"User Research Topic: {topic}\n\n"
            f"{intent_block}\n"
            f"Research Plan Goals: {', '.join(plan.goals or [])}\n"
            f"Research Questions: {', '.join([q.question for q in (plan.questions or [])])}\n"
            f"{landscape_block}\n"
            f"Extracted Insights Pool ({len(insights)} items):\n"
            + "\n".join(insight_summaries)
            + f"\n\nRequired JSON Schema:\n{json.dumps(SynthesizedBriefPayload.model_json_schema(), indent=2)}\n\n"
            "Respond ONLY with the valid JSON object adhering strictly to the schema. "
            "Every finding and claim MUST cite actual insight evidence_ids."
        )
        return prompt

    def _synthesize_via_llm(
        self,
        plan: ResearchPlan,
        insights: List[EvidenceItem],
        topic: str,
        total_raw: int,
        rejected_count: int,
        content_landscape: Optional[Any] = None,
    ) -> tuple[Optional[ResearchBrief], Optional[str]]:
        if not self.llm_client:
            return None, "No LLM client available"

        prompt = self._build_llm_prompt(plan, insights, topic, content_landscape)

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=SYNTHESIZER_SYSTEM_PROMPT,
                temperature=0.2,
                stage_label="Synthesizer",
            )
            data = json.loads(raw_json)
            payload = SynthesizedBriefPayload.model_validate(data)

            brief = ResearchBrief(
                brief_id=f"brief-{hash(topic) & 0xffffffff:08x}",
                topic=topic,
                request_intent=plan.request_intent,
                user_request_summary=f"Research synthesis and content strategy for '{topic}'",
                findings=payload.findings,
                claim_map=payload.claim_map,
                key_mechanisms=payload.key_mechanisms,
                case_studies_and_examples=payload.case_studies_and_examples,
                research_gaps=payload.research_gaps,
                content_angles=payload.content_angles,
                recommended_strategy=payload.recommended_strategy,
                content_landscape=content_landscape,
                total_raw_insights=total_raw,
                retained_insights_count=len(insights),
                rejected_insights_count=rejected_count,
            )
            return brief, None

        except json.JSONDecodeError as e:
            return None, f"Invalid JSON from LLM: {e}"
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)[:200]
            if "rate" in error_msg.lower() or "429" in error_msg:
                return None, f"Rate limit: {error_msg}"
            if "api" in error_msg.lower() or "connect" in error_msg.lower():
                return None, f"API error: {error_msg}"
            if "validat" in error_msg.lower() or "pydantic" in error_msg.lower():
                return None, f"Schema validation failed: {error_msg}"
            return None, f"{error_type}: {error_msg}"

    def _synthesize_fallback(
        self,
        plan: ResearchPlan,
        insights: List[EvidenceItem],
        topic: str,
        total_raw: int,
        rejected_count: int,
        content_landscape: Optional[Any] = None,
    ) -> ResearchBrief:
        """Grounded deterministic synthesis.

        Content creation is NEVER blocked here — even with zero insights the
        synthesizer returns a brief that tells the writer to compose honestly
        (opinion/commentary framing, flagged gaps) rather than fabricate facts.
        """
        intent = plan.request_intent
        if not intent:
            from core.request_intent import RequestInterpreter, UserRequest
            intent = RequestInterpreter(use_llm=False).interpret(UserRequest(raw_prompt=topic))

        subject = intent.subject

        landscape_gaps = (content_landscape.content_gaps if content_landscape else []) or []
        landscape_angles = (content_landscape.possible_original_angles if content_landscape else []) or []

        supporting_ids = [i.evidence_id for i in insights if i.insight_type in ("research_finding", "statistic", "mechanism", "causal_claim")]
        limiting_ids = [i.evidence_id for i in insights if i.insight_type in ("limitation", "contradiction", "opinion")]

        safe_claims = []
        qualified_claims = []
        unsupported_claims = []

        for item in insights:
            if item.insight_type in ("research_finding", "statistic", "mechanism", "causal_claim"):
                claim_text = item.claim_summary
                if item.attribution:
                    claim_text = f"{item.attribution}: {item.claim_summary}"
                safe_claims.append(ClaimMapEntry(
                    claim_text=claim_text,
                    category="safe",
                    reasoning=f"Directly derived from verified insight {item.evidence_id} (type: {item.insight_type}).",
                    supporting_insight_ids=[item.evidence_id],
                ))
            elif item.insight_type in ("expert_claim", "company_claim", "expert_opinion"):
                claim_text = item.claim_summary
                if item.attribution:
                    claim_text = f"{item.attribution} claims: {item.claim_summary}"
                qualified_claims.append(ClaimMapEntry(
                    claim_text=claim_text,
                    category="qualified",
                    reasoning=f"Attributed claim from insight {item.evidence_id} requires source attribution.",
                    required_attribution_or_caveat=f"Attribution: {item.attribution or 'Source not specified'}",
                    supporting_insight_ids=[item.evidence_id],
                ))
            elif item.insight_type in ("limitation", "contradiction"):
                unsupported_claims.append(ClaimMapEntry(
                    claim_text=item.claim_summary,
                    category="unsupported",
                    reasoning=f"Contradicting/limiting insight {item.evidence_id} indicates this claim is contested.",
                    supporting_insight_ids=[item.evidence_id],
                ))

        if not safe_claims and insights:
            best = insights[0]
            safe_claims.append(ClaimMapEntry(
                claim_text=best.claim_summary,
                category="safe",
                reasoning=f"Derived from insight {best.evidence_id}.",
                supporting_insight_ids=[best.evidence_id],
            ))

        # The user's framing is creative direction, not something to verify.
        if not unsupported_claims and intent.proposition:
            unsupported_claims.append(ClaimMapEntry(
                claim_text=f"The framing \"{intent.proposition}\" is opinion/commentary for the writer to argue or explore — not a verified fact.",
                category="unsupported",
                reasoning="The retrieved evidence does not directly verify the user's framing; the writer should present it as critical opinion/commentary with honest attribution.",
            ))

        evidence_gaps = []
        if not supporting_ids:
            evidence_gaps.append(f"No directly supportive sources were retrieved for {subject}; the writer must frame claims as opinion/commentary or mark them as unreported.")
        if len(insights) < 5:
            evidence_gaps.append(f"Retrieved evidence for {subject} is thin ({len(insights)} insight(s)); the writer should lean on gaps, framing, and opinion rather than over-asserting facts.")

        content_gap_lists = list(evidence_gaps) + list(landscape_gaps)
        if not content_gap_lists:
            content_gap_lists = [f"Existing content on {subject} is crowded; an original angle or personal take will differentiate the piece."]

        claim_map = ClaimMap(
            safe_claims=safe_claims[:5],
            qualified_claims=qualified_claims[:3],
            unsupported_claims=unsupported_claims[:3],
            contradicted_claims=[],
            content_gaps=content_gap_lists,
        )

        def _normalize_claim(text: str) -> str:
            return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

        def _stmt(item: EvidenceItem) -> str:
            s = item.claim_summary
            if item.attribution:
                s = f"{item.attribution}: {s}"
            return s

        # Rank claims by how often they recur across the evidence pool so the
        # primary finding represents the consensus, not the first chunk scanned.
        from collections import Counter
        occurrence = Counter(_normalize_claim(i.claim_summary) for i in insights)
        ranked_insights: List[EvidenceItem] = []
        seen_claims = set()
        for item in insights:
            key = _normalize_claim(item.claim_summary)
            if key and key not in seen_claims:
                seen_claims.add(key)
                ranked_insights.append(item)
        ranked_insights.sort(key=lambda i: -occurrence.get(_normalize_claim(i.claim_summary), 0))

        finding_statements = [_stmt(i) for i in ranked_insights[:5]]

        f1 = None
        additional_findings = []
        if finding_statements:
            primary_finding = finding_statements[0]
            domains = {i.fetch_id for i in insights}
            independent_count = max(1, len(domains))

            if supporting_ids and limiting_ids:
                status = "mixed"
            elif not supporting_ids:
                status = "limited"
            elif independent_count == 1:
                status = "single_source"
            elif len(supporting_ids) >= 3:
                status = "consensus"
            else:
                status = "supported"

            f1 = Finding(
                finding_id="find-1",
                topic_area=subject[:50],
                statement=primary_finding,
                status=status,
                reasoning=f"Derived from {len(supporting_ids)} supporting insight(s) across {independent_count} source(s). All claims derived from actual extracted evidence.",
                supporting_insight_ids=supporting_ids,
                contradicting_insight_ids=limiting_ids,
                source_count=len(insights),
                independent_sources_count=independent_count,
            )
            for idx, stmt in enumerate(finding_statements[1:3], start=2):
                additional_findings.append(Finding(
                    finding_id=f"find-{idx}",
                    topic_area=subject[:50],
                    statement=stmt,
                    status="single_source",
                    reasoning="Derived from extracted evidence.",
                    source_count=1,
                    independent_sources_count=1,
                ))

        key_points = []
        for item in insights[:3]:
            kp = item.claim_summary
            if item.attribution:
                kp = f"{item.attribution}: {item.claim_summary}"
            key_points.append(kp)

        # Content-focused angle naming — never "Evidence-Based Assessment of X" filler.
        intent_type = intent.intent_type
        if intent_type == "critique" or intent_type == "claim_investigation":
            angle_title = f"Why {subject} Deserves a Critical Look"
            dominant_thesis = (finding_statements[0] if finding_statements else
                               f"The documented criticisms of {subject} are more layered than one headline — and the counterarguments make it interesting.")
        elif intent_type == "explanation":
            angle_title = f"How {subject} Actually Works"
            dominant_thesis = finding_statements[0] if finding_statements else f"A clear, honest explanation of {subject}."
        elif intent_type == "content_request":
            angle_title = f"The {subject} Take Nobody Has Posted Yet"
            dominant_thesis = (landscape_angles[0] if landscape_angles else
                               (finding_statements[0] if finding_statements else f"An original, opinionated take on {subject} that stands out from the crowd."))
        else:
            angle_title = f"What Actually Matters About {subject}"
            dominant_thesis = finding_statements[0] if finding_statements else f"The essentials of {subject}, honestly explained."

        counterarguments = [item.claim_summary for item in insights if item.insight_type in ("limitation", "contradiction")][:2]
        if intent.stance == "critical" and not counterarguments:
            counterarguments = [f"The strongest counterarguments to the critical case on {subject} belong in the piece for credibility."]

        why_interesting = f"Grounded in {len(insights)} retrieved insight(s)" if insights else "Opinion/commentary-led original take"
        if landscape_angles:
            why_interesting += f"; differentiates from crowded existing content ({content_landscape.total_references} references analyzed)"

        angle_1 = ContentAngle(
            angle_id="angle-1",
            angle_title=angle_title,
            central_thesis=dominant_thesis,
            why_interesting=why_interesting,
            supporting_findings=(finding_statements[:3] or landscape_angles[:2] or
                                 [f"The landscape on {subject} is saturated; an original take is the differentiation."]),
            counterpoints=counterarguments,
            intended_audience="General audience",
            suitable_platform="LinkedIn",
            distinctive_angle=(landscape_angles[0] if landscape_angles else
                               (content_gap_lists[0] if content_gap_lists else "")),
        )

        evidence_refs = []
        for item in insights[:3]:
            ref = item.claim_summary
            if item.attribution:
                ref = f"{item.attribution}: {item.claim_summary}"
            evidence_refs.append(ref)

        strategy = ContentStrategy(
            topic=subject,
            content_type="linkedin_post",
            platform="LinkedIn",
            audience="General audience",
            objective="engage",
            selected_angle=angle_1,
            thesis=angle_1.central_thesis,
            hook_direction=(landscape_angles[0] if landscape_angles else
                            f"Open with the tension that makes {subject} worth talking about — not a generic research summary."),
            key_points=key_points or ([f"Original, opinionated analysis of {subject}"] + content_gap_lists[:2]),
            claims_to_include=[c.claim_text for c in safe_claims + qualified_claims],
            claims_to_avoid=[c.claim_text for c in unsupported_claims] + ["Never present opinion as verified fact."],
            evidence_to_reference=evidence_refs or [],
            counterpoints=counterarguments,
            desired_takeaway=f"A compelling, original piece on {subject} the reader hasn't already read ten times.",
        )

        return ResearchBrief(
            brief_id=f"brief-{hash(topic) & 0xffffffff:08x}",
            topic=topic,
            request_intent=intent,
            user_request_summary=f"Research synthesis (grounded fallback) for '{topic}'",
            findings=[find for find in [f1] + additional_findings if find is not None],
            claim_map=claim_map,
            key_mechanisms=[item.claim_summary for item in insights if item.insight_type == "mechanism"][:3] or [],
            case_studies_and_examples=[item.claim_summary for item in insights if item.insight_type in ("case_study", "example")][:3] or [],
            research_gaps=evidence_gaps or [],
            content_angles=[angle_1],
            recommended_strategy=strategy,
            content_landscape=content_landscape,
            total_raw_insights=total_raw,
            retained_insights_count=len(insights),
            rejected_insights_count=rejected_count,
        )
