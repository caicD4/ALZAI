"""Tests for grounded fallback synthesis — verifying no fabricated generic research language."""

import pytest
from agents.synthesizer import ResearchSynthesizer
from core.evidence import EvidenceItem
from core.research_plan import ResearchPlan, ResearchQuestion
from core.request_intent import RequestIntent
from core.synthesis import (
    ClaimMap,
    ContentAngle,
    ContentStrategy,
    Finding,
    ResearchBrief,
)

FABRICATED_PHRASES = [
    "core operational principles",
    "functional workflows",
    "key architectural mechanisms",
    "operational trade-offs",
    "strategic leadership decisions and notable controversies",
    "boundary condition management",
    "boundary conditions and operational limits",
    "core mechanisms, empirical benchmarks, and practical implementation limits",
    "significantly improves productivity",
    "primary research documents core",
    "real-world performance depends on specific implementation parameters",
]


def _brief_text(brief: ResearchBrief) -> str:
    parts = []
    for f in brief.findings:
        parts.append(f.statement)
        parts.append(f.reasoning)
    for c in brief.claim_map.safe_claims:
        parts.append(c.claim_text)
    for c in brief.claim_map.qualified_claims:
        parts.append(c.claim_text)
    for c in brief.claim_map.unsupported_claims:
        parts.append(c.claim_text)
    for gap in brief.claim_map.content_gaps:
        parts.append(gap)
    if brief.recommended_strategy:
        parts.append(brief.recommended_strategy.hook_direction)
        parts.append(brief.recommended_strategy.thesis)
        parts.append(brief.recommended_strategy.desired_takeaway)
        for kp in brief.recommended_strategy.key_points:
            parts.append(kp)
    return " ".join(parts).lower()


def _assert_no_fabricated_phrases(brief: ResearchBrief):
    text = _brief_text(brief)
    for phrase in FABRICATED_PHRASES:
        assert phrase not in text, f"Fabricated phrase found in output: '{phrase}'"


def _assert_actual_evidence_present(brief: ResearchBrief, evidence_keywords: list):
    text = _brief_text(brief)
    found = any(kw.lower() in text for kw in evidence_keywords)
    assert found, f"Expected at least one of {evidence_keywords} to appear in brief text"


def _make_plan(topic, intent_type, subject, proposition=None):
    plan = ResearchPlan(
        topic=topic,
        goals=[f"Research on {topic}"],
        questions=[
            ResearchQuestion(
                id="rq-1",
                question=f"What evidence exists about {topic}?",
                rationale=f"Investigate {topic}",
                priority=1,
                search_queries=[topic],
            )
        ],
    )
    plan.request_intent = RequestIntent(
        subject=subject,
        task=f"Investigate {topic}",
        proposition=proposition,
        question=f"What evidence exists about {topic}?",
        intent_type=intent_type,
        key_entities=[subject],
        key_concepts=[],
        research_goal=f"Investigate evidence regarding {topic}",
    )
    return plan


class TestNoFabricatedPhrases:
    def test_elon_musk_sucks_no_fabrication(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Tesla reported a 40% decline in European sales in Q1 2025.",
                claim_summary="Tesla saw 40% European sales decline in Q1 2025.",
                insight_type="statistic", source_role="evidence", attribution="Reuters",
            ),
            EvidenceItem(
                evidence_id="ev-2", fetch_id="f-2", locator="span:0-100",
                verbatim_quote="Multiple lawsuits allege wrongful termination at SpaceX.",
                claim_summary="Wrongful termination lawsuits at SpaceX.",
                insight_type="research_finding", source_role="evidence", attribution="Washington Post",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why elon musk sucks")
        _assert_no_fabricated_phrases(brief)
        _assert_actual_evidence_present(brief, ["40%", "sales decline", "wrongful termination", "lawsuit"])

    def test_remote_work_sucks_no_fabrication(self):
        plan = _make_plan("why remote work sucks", "claim_investigation", "Remote Work", "Remote work sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Stanford study found hybrid workers were 18% less productive.",
                claim_summary="Stanford found 18% productivity decline in hybrid workers.",
                insight_type="research_finding", source_role="evidence", attribution="Stanford/Nicholas Bloom",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why remote work sucks")
        _assert_no_fabricated_phrases(brief)
        _assert_actual_evidence_present(brief, ["18%", "productivity", "hybrid"])

    def test_mixture_of_experts_no_fabrication(self):
        plan = _make_plan("explain mixture of experts", "explanation", "Mixture of Experts")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="The gating network routes each token to 2 out of 8 expert subnetworks.",
                claim_summary="Gating network routes tokens to 2 of 8 experts.",
                insight_type="mechanism", source_role="evidence", attribution="Google Research",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "explain mixture of experts")
        _assert_no_fabricated_phrases(brief)
        _assert_actual_evidence_present(brief, ["gating", "routing", "expert"])


class TestInsightPreservation:
    def test_actual_insight_text_appears_in_findings(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Tesla reported a 40% decline in European sales.",
                claim_summary="Tesla saw 40% European sales decline.",
                insight_type="statistic", source_role="evidence", attribution="Reuters",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why elon musk sucks")
        finding_text = brief.findings[0].statement.lower()
        assert "tesla" in finding_text or "40%" in finding_text, \
            f"Finding should contain actual insight text, got: {brief.findings[0].statement}"

    def test_claim_map_cites_actual_evidence_ids(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Tesla reported a 40% decline.",
                claim_summary="Tesla sales declined 40%.",
                insight_type="research_finding", source_role="evidence",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why elon musk sucks")
        all_ids = set()
        for c in brief.claim_map.safe_claims:
            all_ids.update(c.supporting_insight_ids)
        for c in brief.claim_map.qualified_claims:
            all_ids.update(c.supporting_insight_ids)
        assert "ev-1" in all_ids, "ClaimMap must reference actual evidence IDs"

    def test_limitations_preserved_in_brief(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Tesla reported a 40% decline.",
                claim_summary="Tesla sales declined 40%.",
                insight_type="research_finding", source_role="evidence",
            ),
            EvidenceItem(
                evidence_id="ev-2", fetch_id="f-2", locator="span:0-100",
                verbatim_quote="However, the sample size was limited to 50 participants.",
                claim_summary="Study had limited sample size of 50.",
                insight_type="limitation", source_role="evidence",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why elon musk sucks")
        assert brief.findings[0].status == "mixed"
        assert "ev-2" in brief.findings[0].contradicting_insight_ids


class TestEmptyEvidenceStillGeneratesContent:
    def test_empty_insights_returns_empty_findings_but_creative_direction(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, [], "why elon musk sucks")
        assert len(brief.findings) == 0
        assert brief.retained_insights_count == 0
        assert "elon musk sucks" in brief.claim_map.unsupported_claims[0].claim_text.lower() or \
            len(brief.claim_map.unsupported_claims) >= 1
        assert brief.recommended_strategy is not None
        assert brief.content_angles, "Content angles must still be produced for the writer"

    def test_empty_insights_have_no_fake_safe_claims(self):
        plan = _make_plan("test topic", "topic_request", "Test Topic")
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, [], "test topic")
        assert len(brief.claim_map.safe_claims) == 0
        assert len(brief.claim_map.qualified_claims) == 0


class TestLLMFailureVisibility:
    def test_llm_failure_recorded(self):
        plan = _make_plan("test", "topic_request", "Test")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Some test evidence with enough words.",
                claim_summary="Test evidence.",
                insight_type="research_finding", source_role="evidence",
            ),
        ]
        synth = ResearchSynthesizer(use_llm=False)
        brief = synth.synthesize_research(plan, insights, "test")
        assert synth.last_synthesis_method == "grounded_fallback"
        assert synth.last_synthesis_error is not None

    def test_empty_insights_method_recorded(self):
        plan = _make_plan("test", "topic_request", "Test")
        synth = ResearchSynthesizer(use_llm=False)
        brief = synth.synthesize_research(plan, [], "test")
        assert synth.last_synthesis_method == "grounded_fallback"
        assert len(brief.findings) == 0
        assert not brief.claim_map.safe_claims
        assert brief.claim_map.content_gaps


class TestIntentPassedToSynthesis:
    def test_request_intent_stored_on_brief(self):
        plan = _make_plan("why elon musk sucks", "claim_investigation", "Elon Musk", "Elon Musk sucks")
        insights = [
            EvidenceItem(
                evidence_id="ev-1", fetch_id="f-1", locator="span:0-100",
                verbatim_quote="Tesla reported a 40% decline.",
                claim_summary="Tesla sales declined 40%.",
                insight_type="research_finding", source_role="evidence",
            ),
        ]
        brief = ResearchSynthesizer(use_llm=False).synthesize_research(plan, insights, "why elon musk sucks")
        assert brief.request_intent is not None
        assert brief.request_intent.subject == "Elon Musk"
        assert brief.request_intent.intent_type == "claim_investigation"
