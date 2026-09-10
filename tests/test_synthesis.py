import pytest
from unittest.mock import MagicMock, patch
from agents.synthesizer import ResearchSynthesizer
from core.evidence import EvidenceItem, FetchSnapshot
from core.research_plan import ResearchPlan, ResearchQuestion
from core.request_intent import RequestIntent
from core.synthesis import (
    ClaimMap,
    ContentAngle,
    ContentStrategy,
    Finding,
    ResearchBrief,
)


@pytest.fixture
def iq_plan():
    return ResearchPlan(
        topic="write me a linkedin post on how iq can actually be increased through neuroplasticity and RFT and adaptive training",
        goals=["Evaluate RFT and adaptive training for fluid intelligence gains."],
        questions=[
            ResearchQuestion(
                id="rq-1",
                question="How does Relational Frame Theory (RFT) training target core cognitive skills to increase fluid intelligence?",
                rationale="Evaluate fluid intelligence mechanisms.",
                priority=1,
                search_queries=["Relational Frame Theory fluid intelligence IQ SMART training"],
            )
        ],
        max_search_iterations=2,
    )


# 1 & 2. Multiple similar insights collapse into one Finding & duplicate sources do not create fake consensus
def test_multiple_insights_same_domain_do_not_fake_consensus(iq_plan):
    insights = [
        EvidenceItem(
            evidence_id="ev-1",
            fetch_id="fetch-domain-a",
            locator="span:0-100",
            verbatim_quote="SMART relational training increases fluid intelligence scores by 10 points.",
            claim_summary="SMART training boosts IQ by 10 points.",
            insight_type="research_finding",
            source_role="evidence",
            attribution="Study A",
        ),
        EvidenceItem(
            evidence_id="ev-2",
            fetch_id="fetch-domain-a",  # Same fetch / domain!
            locator="span:101-200",
            verbatim_quote="Participants undergoing SMART relational training demonstrated 10 point fluid IQ increases.",
            claim_summary="10 point IQ increase in SMART participants.",
            insight_type="research_finding",
            source_role="evidence",
            attribution="Study A repeat snippet",
        ),
    ]

    synthesizer = ResearchSynthesizer(use_llm=False)
    brief = synthesizer.synthesize_research(iq_plan, insights, iq_plan.topic)

    assert len(brief.findings) >= 1
    finding = brief.findings[0]
    assert finding.independent_sources_count == 1  # Unique fetch_id count is 1!
    assert finding.status != "consensus"  # Cannot be consensus with only 1 independent source!


# 3 & 4. Supporting and contradicting insights produce mixed/contested status
def test_mixed_evidence_produces_mixed_status(iq_plan):
    insights = [
        EvidenceItem(
            evidence_id="ev-supp-1",
            fetch_id="fetch-1",
            locator="span:0-100",
            verbatim_quote="Relational skills training demonstrated significant gains in fluid IQ tests.",
            claim_summary="Significant IQ gains in relational training.",
            insight_type="research_finding",
            source_role="evidence",
        ),
        EvidenceItem(
            evidence_id="ev-contra-1",
            fetch_id="fetch-2",
            locator="span:0-100",
            verbatim_quote="Replication attempts found no significant far-transfer improvements in general intelligence after relational training.",
            claim_summary="Replication study found no far-transfer IQ improvements.",
            insight_type="limitation",
            source_role="evidence",
        ),
    ]

    synthesizer = ResearchSynthesizer(use_llm=False)
    brief = synthesizer.synthesize_research(iq_plan, insights, iq_plan.topic)

    assert len(brief.findings) >= 1
    finding = brief.findings[0]
    assert finding.status == "mixed"
    assert "ev-supp-1" in finding.supporting_insight_ids
    assert "ev-contra-1" in finding.contradicting_insight_ids


# 9 & 10. CDC autism prevalence material is EXCLUDED from IQ research topic
def test_cdc_autism_prevalence_excluded_from_iq_topic(iq_plan):
    insights = [
        EvidenceItem(
            evidence_id="ev-cdc-autism",
            fetch_id="fetch-cdc-123",
            locator="span:4247-4612",
            verbatim_quote="The Centers for Disease Control and Prevention (CDC) reports a prevalence of one in 31 children with autism spectrum disorder.",
            claim_summary="CDC reports 3.2% autism prevalence.",
            insight_type="statistic",
            source_role="evidence",
            attribution="CDC ADDM Network",
        ),
        EvidenceItem(
            evidence_id="ev-iq-valid",
            fetch_id="fetch-iq-456",
            locator="span:100-200",
            verbatim_quote="Relational frame theory training produces measurable improvements in fluid reasoning tasks.",
            claim_summary="RFT training improves fluid reasoning.",
            insight_type="research_finding",
            source_role="evidence",
        ),
    ]

    synthesizer = ResearchSynthesizer(use_llm=False)
    brief = synthesizer.synthesize_research(iq_plan, insights, iq_plan.topic)

    # Verify CDC autism item was rejected during synthesis filtering
    assert brief.rejected_insights_count >= 1
    assert brief.retained_insights_count == 1

    # Ensure CDC autism is not in findings or claim map
    brief_text = str(brief.model_dump()).lower()
    assert "autism" not in brief_text
    assert "cdc" not in brief_text


# 7 & 16. ClaimMap categorizes safe vs qualified vs unsupported claims using actual insight types
def test_claim_map_categorization_and_content_gaps(iq_plan):
    insights = [
        EvidenceItem(
            evidence_id="ev-1",
            fetch_id="fetch-1",
            locator="span:0-100",
            verbatim_quote="Relational skills training improves performance on trained relational tasks and working memory capacity.",
            claim_summary="Relational training improves trained task performance.",
            insight_type="research_finding",
            source_role="evidence",
        ),
        EvidenceItem(
            evidence_id="ev-2",
            fetch_id="fetch-2",
            locator="span:0-100",
            verbatim_quote="According to Dr. Smith, relational training has broad cognitive benefits.",
            claim_summary="Expert claims broad cognitive benefits of relational training.",
            insight_type="expert_claim",
            source_role="expert_perspective",
            attribution="Dr. Smith",
        ),
        EvidenceItem(
            evidence_id="ev-3",
            fetch_id="fetch-3",
            locator="span:0-100",
            verbatim_quote="Replication studies found no significant far-transfer improvements.",
            claim_summary="Replication found no far-transfer improvements.",
            insight_type="limitation",
            source_role="evidence",
        ),
    ]

    synthesizer = ResearchSynthesizer(use_llm=False)
    brief = synthesizer.synthesize_research(iq_plan, insights, iq_plan.topic)

    claim_map = brief.claim_map
    assert isinstance(claim_map, ClaimMap)
    assert len(claim_map.safe_claims) >= 1, "Safe claims should be derived from research_finding insights"
    assert len(claim_map.qualified_claims) >= 1, "Qualified claims should be derived from expert_claim insights"
    assert len(claim_map.content_gaps) >= 1, "Content gaps should document thin/contested evidence"
    for claim in claim_map.unsupported_claims:
        assert claim.category == "unsupported"

    # All claims must reference actual insight IDs, not be fabricated
    for sc in claim_map.safe_claims:
        assert len(sc.supporting_insight_ids) > 0, f"Safe claim must cite evidence: {sc.claim_text}"
    for qc in claim_map.qualified_claims:
        assert len(qc.supporting_insight_ids) > 0, f"Qualified claim must cite evidence: {qc.claim_text}"


# 11, 14, 15. Useful mechanisms become findings, research gaps are identified, and content angles are grounded
def test_mechanisms_gaps_and_content_angles_generated(iq_plan):
    insights = [
        EvidenceItem(
            evidence_id="ev-mech-1",
            fetch_id="fetch-mech-1",
            locator="span:0-100",
            verbatim_quote="Continuous difficulty-scaled working memory load prevents automaticity and triggers synaptic remodeling.",
            claim_summary="Adaptive load prevents automaticity and triggers synaptic remodeling.",
            insight_type="mechanism",
            source_role="evidence",
        )
    ]

    synthesizer = ResearchSynthesizer(use_llm=False)
    brief = synthesizer.synthesize_research(iq_plan, insights, iq_plan.topic)

    assert len(brief.key_mechanisms) >= 1
    assert len(brief.research_gaps) >= 1
    assert len(brief.content_angles) >= 1

    angle = brief.content_angles[0]
    assert isinstance(angle, ContentAngle)
    assert angle.suitable_platform == "LinkedIn"
    assert len(angle.central_thesis) > 10

    strategy = brief.recommended_strategy
    assert isinstance(strategy, ContentStrategy)
    assert strategy.platform == "LinkedIn"
    assert len(strategy.key_points) >= 1
    assert len(strategy.claims_to_avoid) >= 1
