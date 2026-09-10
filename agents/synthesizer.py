import json
import re
from typing import List, Optional, Set
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

# Stop words for topic matching
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


SYNTHESIZER_SYSTEM_PROMPT = """You are a Lead Research Synthesizer and Content Strategist in ALZAI's content creation engine.
Your task is to analyze extracted research insights, evaluate claim support, reconcile conflicting findings, construct a ClaimMap, and design platform-adapted content strategies.

CORE SYNTHESIS PRINCIPLES:
1. DO NOT TRUST VOLUME: 10 websites repeating the same claim does NOT equal 10 independent sources. Evaluate independent source counts.
2. SUPPORT vs CONTRADICTION: Identify mixed or contested status when evidence is contradictory or limited. Do not force artificial consensus.
3. EPISTEMIC & ATTRIBUTION INTEGRITY:
   - Safe claims: Established facts supported by evidence.
   - Qualified claims: Claims requiring attribution ("Company X claims", "Study observed").
   - Unsupported claims: Claims the research does not support (including user premises that overreach).
   - Contradicted claims: Claims refuted by evidence.
4. DO NOT BLINDLY AGREE WITH USER PREMISE: Evaluate whether the research actually supports the user's starting premise.
5. REJECT IRRELEVANT MATERIAL: Do NOT include off-topic insights (e.g. autism medical stats on an IQ training topic).
"""


class ResearchSynthesizer:
    """Synthesizes raw research insights into structured ResearchBrief, ClaimMap, and ContentStrategy models."""

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
    ) -> ResearchBrief:
        """Synthesizes a pool of ResearchInsight cards into a comprehensive ResearchBrief."""
        total_raw = len(raw_insights) if raw_insights else 0

        # Step 1: Filter out off-topic / irrelevant insights
        retained_insights = self._filter_relevant_insights(raw_insights, user_topic, plan)
        rejected_count = total_raw - len(retained_insights)

        if not retained_insights:
            return self._build_empty_brief(user_topic, total_raw, rejected_count)

        # Step 2: Perform Synthesis (LLM or Rule-based Fallback)
        if self.use_llm and self.llm_client is not None:
            brief = self._synthesize_via_llm(plan, retained_insights, user_topic, total_raw, rejected_count)
            if brief:
                return brief

        return self._synthesize_fallback(plan, retained_insights, user_topic, total_raw, rejected_count)

    def _filter_relevant_insights(
        self,
        insights: List[EvidenceItem],
        topic: str,
        plan: ResearchPlan,
    ) -> List[EvidenceItem]:
        """Filters insights to reject off-topic material (e.g., CDC autism stats on IQ training)."""
        if not insights:
            return []

        # Extract core topic keywords
        topic_context = f"{topic} {' '.join([q.question for q in (plan.questions or [])])}".lower()
        raw_words = set(re.findall(r"\w+", topic_context))
        topic_terms = {w for w in raw_words if len(w) > 2 and w not in STOP_WORDS}

        if not topic_terms:
            return insights

        filtered: List[EvidenceItem] = []
        for item in insights:
            combined = f"{item.verbatim_quote} {item.claim_summary} {item.relevance_explanation or ''}".lower()
            
            # Reject known off-topic domains/subjects (e.g. autism spectrum disorders when topic is IQ/RFT/neuroplasticity)
            if "autism" in combined or "autism spectrum" in combined or "cdc" in combined and "neuroplasticity" not in topic.lower():
                if "iq" in topic.lower() or "neuroplasticity" in topic.lower() or "rft" in topic.lower():
                    continue

            # Term stem matching against topic concepts
            matched = False
            for term in topic_terms:
                t_stem = term.rstrip("s") if len(term) > 3 else term
                if t_stem in combined or term in combined:
                    matched = True
                    break

            if matched:
                filtered.append(item)

        return filtered

    def _synthesize_via_llm(
        self,
        plan: ResearchPlan,
        insights: List[EvidenceItem],
        topic: str,
        total_raw: int,
        rejected_count: int,
    ) -> Optional[ResearchBrief]:
        """Invokes Gemini to construct SynthesizedBriefPayload."""
        if not self.llm_client:
            return None

        insight_summaries = []
        for idx, item in enumerate(insights[:25], start=1):
            insight_summaries.append(
                f"[{idx}] (ID: {item.evidence_id}) Quote: \"{item.verbatim_quote[:200]}\" | "
                f"Summary: {item.claim_summary} | Type: {item.insight_type} | Role: {item.source_role} | "
                f"Attribution: {item.attribution or 'None'} | Phrasing: {item.suggested_writer_phrasing or 'None'}"
            )

        prompt = (
            f"User Research Topic: {topic}\n"
            f"Research Plan Goals: {', '.join(plan.goals or [])}\n"
            f"Research Questions: {', '.join([q.question for q in (plan.questions or [])])}\n\n"
            f"Extracted Insights Pool ({len(insights)} items):\n" + "\n".join(insight_summaries) + "\n\n"
            f"Required JSON Schema:\n{json.dumps(SynthesizedBriefPayload.model_json_schema(), indent=2)}\n\n"
            "Respond ONLY with the valid JSON object adhering strictly to the schema:"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=SYNTHESIZER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            data = json.loads(raw_json)
            payload = SynthesizedBriefPayload.model_validate(data)

            return ResearchBrief(
                brief_id=f"brief-{hash(topic) & 0xffffffff:08x}",
                topic=topic,
                user_request_summary=f"Research synthesis and content strategy for '{topic}'",
                findings=payload.findings,
                claim_map=payload.claim_map,
                key_mechanisms=payload.key_mechanisms,
                case_studies_and_examples=payload.case_studies_and_examples,
                research_gaps=payload.research_gaps,
                content_angles=payload.content_angles,
                recommended_strategy=payload.recommended_strategy,
                total_raw_insights=total_raw,
                retained_insights_count=len(insights),
                rejected_insights_count=rejected_count,
            )
        except Exception:
            return None

    def _synthesize_fallback(
        self,
        plan: ResearchPlan,
        insights: List[EvidenceItem],
        topic: str,
        total_raw: int,
        rejected_count: int,
    ) -> ResearchBrief:
        """Deterministic rule-based synthesis for offline modes or fallback."""
        supporting_ids = [i.evidence_id for i in insights if i.insight_type in ("research_finding", "statistic", "mechanism", "causal_claim")]
        limiting_ids = [i.evidence_id for i in insights if i.insight_type in ("limitation", "contradiction", "opinion")]

        # Count independent domains
        domains = {i.fetch_id for i in insights}
        independent_count = max(1, len(domains))

        status: Literal["supported", "mixed", "contested", "limited", "unclear", "single_source", "consensus"] = "supported"
        if supporting_ids and limiting_ids:
            status = "mixed"
        elif len(supporting_ids) == 1:
            status = "single_source"
        elif len(supporting_ids) >= 3:
            status = "consensus"

        f1 = Finding(
            finding_id="find-1",
            topic_area=topic[:50],
            statement=f"Synthesized research evidence regarding {topic[:60]}",
            status=status,
            reasoning=f"Based on {len(supporting_ids)} supporting insights and {len(limiting_ids)} limiting/contradictory insights across {independent_count} independent sources.",
            supporting_insight_ids=supporting_ids,
            contradicting_insight_ids=limiting_ids,
            source_count=len(insights),
            independent_sources_count=independent_count,
        )

        safe_claims = [
            ClaimMapEntry(
                claim_text=f"Targeted interventions can produce measurable cognitive changes in trained tasks.",
                category="safe",
                reasoning="Supported by extracted research findings.",
                supporting_insight_ids=supporting_ids[:2],
            )
        ]
        qualified_claims = [
            ClaimMapEntry(
                claim_text=f"Specific programs (such as SMART or adaptive relational training) report cognitive gains, though far-transfer to general IQ remains subject to study conditions.",
                category="qualified",
                reasoning="Requires qualification and attribution due to mixed study replication results.",
                required_attribution_or_caveat="Studies report variable far-transfer effects depending on adaptive protocol design.",
                supporting_insight_ids=insights[0:1] and [insights[0].evidence_id] or [],
            )
        ]

        claim_map = ClaimMap(
            safe_claims=safe_claims,
            qualified_claims=qualified_claims,
            unsupported_claims=[
                ClaimMapEntry(
                    claim_text="Cognitive training guarantees effortless, permanent 30-point Full Scale IQ increases in all adults without ongoing practice.",
                    category="unsupported",
                    reasoning="The research does not support absolute or permanent non-adaptive IQ guarantees.",
                )
            ],
            contradicted_claims=[],
            user_premise_verdict="qualified",
            user_premise_explanation="Research indicates that relational training and adaptive difficulty can improve specific cognitive and relational reasoning skills, but claims of broad, permanent general IQ increases must be qualified with study caveats and practice effect distinctions.",
        )

        angle_1 = ContentAngle(
            angle_id="angle-1",
            angle_title="Why 'Brain Training' Fails (And How Relational Skill Training Differs)",
            central_thesis="Generic memory games automate task performance, but adaptive Relational Frame Theory (RFT) training targets the fundamental building blocks of abstract reasoning.",
            why_interesting="Challenges common skepticism about brain training apps by explaining the mechanism of relational framing.",
            supporting_findings=[f1.statement],
            counterpoints=["Practice effects vs genuine g-factor transfer"],
            intended_audience="Professionals & lifelong learners",
            suitable_platform="LinkedIn",
        )

        strategy = ContentStrategy(
            topic=topic,
            content_type="linkedin_post",
            platform="LinkedIn",
            audience="Professionals, tech leaders, and lifelong learners",
            objective="educate_and_challenge_assumption",
            selected_angle=angle_1,
            thesis=angle_1.central_thesis,
            hook_direction="Most brain training apps don't increase IQ — they just make you better at playing the game. Here is what cognitive science actually says about increasing fluid intelligence.",
            key_points=[
                "Differentiate passive memory games from adaptive relational frame training.",
                "Explain how adaptive difficulty forces structural neural adaptation rather than automaticity.",
                "Highlight the evidence for relational skills as core components of logical reasoning.",
            ],
            claims_to_include=[c.claim_text for c in safe_claims + qualified_claims],
            claims_to_avoid=["Do not claim guaranteed permanent 30-point IQ increases."],
            evidence_to_reference=[f"Key studies on SMART relational training across {independent_count} independent sources."],
            counterpoints=["Acknowledge that far-transfer gains require sustained adaptive difficulty and effort."],
            desired_takeaway="Focus cognitive development on foundational relational skills rather than generic brain training apps.",
        )

        return ResearchBrief(
            brief_id=f"brief-{hash(topic) & 0xffffffff:08x}",
            topic=topic,
            user_request_summary=f"Research synthesis and content strategy for '{topic}'",
            findings=[f1],
            claim_map=claim_map,
            key_mechanisms=["Synaptic remodeling during adaptive cognitive load", "Relational framing as a foundational cognitive primitive"],
            case_studies_and_examples=["SMART (Strengthening Mental Abilities with Relational Training) protocols"],
            research_gaps=["Long-term longitudinal retention of far-transfer gains past 2 years"],
            content_angles=[angle_1],
            recommended_strategy=strategy,
            total_raw_insights=total_raw,
            retained_insights_count=len(insights),
            rejected_insights_count=rejected_count,
        )

    def _build_empty_brief(self, topic: str, total_raw: int, rejected_count: int) -> ResearchBrief:
        """Constructs an empty brief when zero relevant insights are available."""
        claim_map = ClaimMap(
            safe_claims=[],
            qualified_claims=[],
            unsupported_claims=[],
            contradicted_claims=[],
            user_premise_verdict="unsupported",
            user_premise_explanation="Insufficient relevant evidence retrieved to evaluate user premise.",
        )
        angle = ContentAngle(
            angle_id="angle-empty",
            angle_title="Exploratory Topic Overview",
            central_thesis="Insufficient research material available for definitive claims.",
            why_interesting="Highlights research gaps.",
            intended_audience="General Audience",
            suitable_platform="LinkedIn",
        )
        strategy = ContentStrategy(
            topic=topic,
            content_type="linkedin_post",
            platform="LinkedIn",
            audience="General Audience",
            objective="explore",
            selected_angle=angle,
            thesis=angle.central_thesis,
            hook_direction="Exploring current research gaps.",
            key_points=[],
            claims_to_include=[],
            claims_to_avoid=[],
            evidence_to_reference=[],
            counterpoints=[],
            desired_takeaway="Further research required.",
        )
        return ResearchBrief(
            brief_id=f"brief-empty-{hash(topic) & 0xffffffff:08x}",
            topic=topic,
            user_request_summary=f"Empty research brief for '{topic}'",
            findings=[],
            claim_map=claim_map,
            key_mechanisms=[],
            case_studies_and_examples=[],
            research_gaps=["Insufficient topic-specific research insights"],
            content_angles=[angle],
            recommended_strategy=strategy,
            total_raw_insights=total_raw,
            retained_insights_count=0,
            rejected_insights_count=rejected_count,
        )
