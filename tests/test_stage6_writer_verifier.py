import pytest
from agents.outliner import ContentOutliner
from agents.revision import TargetedRevisionWorker
from agents.verifier import ContentVerifier
from agents.voice_analyzer import VoiceProfileAnalyzer
from agents.writer import HumanBrandVoiceWriter
from core.brand_voice import (
    BrandProfile,
    ContentOutline,
    DefaultVoiceProfile,
    DraftContent,
    FactualError,
    StyleError,
    VerificationReport,
    VoiceProfile,
)
from core.evidence import EvidenceItem
from core.research_plan import ResearchPlan, ResearchQuestion
from core.synthesis import (
    ClaimMap,
    ClaimMapEntry,
    ContentAngle,
    ContentStrategy,
    Finding,
    ResearchBrief,
)


@pytest.fixture
def sample_brief():
    claim_map = ClaimMap(
        safe_claims=[
            ClaimMapEntry(
                claim_text="Neuroplasticity enables the adult human brain to form new neural connections throughout life.",
                category="safe",
                reasoning="Supported by neuroscience research.",
            )
        ],
        qualified_claims=[
            ClaimMapEntry(
                claim_text="Relational Frame Theory (RFT) training can lead to significant fluid IQ increases.",
                category="qualified",
                reasoning="Observed in specific trials but requires qualification.",
                required_attribution_or_caveat="According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche",
            )
        ],
        unsupported_claims=[
            ClaimMapEntry(
                claim_text="Playing casual mobile puzzle games for 5 minutes a day will permanently double adult IQ.",
                category="unsupported",
                reasoning="Refuted by scientific consensus.",
            )
        ],
        user_premise_verdict="qualified",
        user_premise_explanation="IQ increases are supported for adaptive RFT protocols but not casual games.",
    )

    finding = Finding(
        finding_id="find-1",
        topic_area="IQ & Neuroplasticity",
        statement="RFT training yields fluid intelligence gains.",
        status="supported",
        reasoning="Multiple study insights support this.",
        supporting_insight_ids=["ev-1"],
        source_count=2,
        independent_sources_count=2,
    )

    angle = ContentAngle(
        angle_id="ang-1",
        angle_title="Why Casual Brain Apps Fail",
        central_thesis="Adaptive RFT training expands intelligence while casual games cause task-specific practice effects.",
        why_interesting="Challenges commercial app claims.",
        intended_audience="Professionals & Lifelong Learners",
        suitable_platform="LinkedIn",
    )

    strategy = ContentStrategy(
        topic="IQ & Neuroplasticity",
        content_type="linkedin_post",
        platform="LinkedIn",
        audience="Professionals & Lifelong Learners",
        objective="challenge_assumption",
        selected_angle=angle,
        thesis=angle.central_thesis,
        hook_direction="Most brain training apps don't raise IQ. Here is what cognitive science actually says.",
        key_points=["Differentiate casual games from RFT", "Explain adaptive load"],
        claims_to_include=["Neuroplasticity enables neural reorganization."],
        claims_to_avoid=["Casual games double IQ."],
        evidence_to_reference=["Cassidy et al. RFT study"],
        counterpoints=["Far-transfer gains require sustained adaptive difficulty."],
        desired_takeaway="Focus on adaptive relational training.",
    )

    return ResearchBrief(
        brief_id="brief-123",
        topic="IQ & Neuroplasticity",
        user_request_summary="LinkedIn post on IQ and RFT",
        findings=[finding],
        claim_map=claim_map,
        key_mechanisms=["Arbitrarily Applicable Relational Responding"],
        research_gaps=["Longitudinal retention > 5 years"],
        content_angles=[angle],
        recommended_strategy=strategy,
        total_raw_insights=10,
        retained_insights_count=10,
        rejected_insights_count=0,
    )


# 1. BrandProfile validation
def test_brand_profile_validation():
    brand = BrandProfile(
        name="AI Builder",
        niche="AI Engineering",
        audience="Developers & Founders",
        positioning="Technical but practical",
        topics=["LLMs", "Agents"],
    )
    assert brand.name == "AI Builder"
    assert "LLMs" in brand.topics


# 2. VoiceProfile validation
def test_voice_profile_validation():
    voice = VoiceProfile(
        profile_id="v-1",
        name="Custom Voice",
        formality="casual",
        sentence_length="short",
        avoided_phrases=["In today's world"],
        is_default_profile=False,
    )
    assert voice.is_default_profile is False
    assert "In today's world" in voice.avoided_phrases


# 15. No VoiceProfile produces explicit default style
def test_no_voice_profile_produces_explicit_default_style():
    default_voice = DefaultVoiceProfile()
    assert default_voice.is_default_profile is True
    assert default_voice.profile_id == "default-voice-profile"
    assert "In today's rapidly evolving world" in default_voice.avoided_phrases


# 16. Writing samples can produce a structured VoiceProfile
def test_writing_samples_produce_structured_voice_profile():
    analyzer = VoiceProfileAnalyzer(use_llm=False)
    samples = [
        "Most AI startups fail because they build wrappers instead of workflows.",
        "Here is what 50 developer interviews actually taught us about agent evaluation.",
    ]
    profile = analyzer.analyze_samples(samples, author_name="TechFounder")
    assert profile.is_default_profile is False
    assert profile.name == "TechFounder's Writing Style"
    assert len(profile.stylistic_examples) == 2


# 3. ContentOutline generation
def test_content_outline_generation(sample_brief):
    outliner = ContentOutliner(use_llm=False)
    outline = outliner.create_outline(sample_brief, sample_brief.recommended_strategy)

    assert isinstance(outline, ContentOutline)
    assert outline.platform == "LinkedIn"
    assert len(outline.main_points) >= 2
    assert outline.main_points[0].title != ""


# 4 & 7. Writer uses ResearchBrief claims and retains appropriate epistemic strength
def test_writer_uses_research_brief_claims(sample_brief):
    outliner = ContentOutliner(use_llm=False)
    outline = outliner.create_outline(sample_brief, sample_brief.recommended_strategy)

    writer = HumanBrandVoiceWriter(use_llm=False)
    draft = writer.write_draft(sample_brief, sample_brief.recommended_strategy, outline)

    assert isinstance(draft, DraftContent)
    assert draft.word_count > 20
    assert "brain" in draft.body_text.lower()


# 5, 9, 10, 11, 12. Verifier catches unsupported claims, strengthened claims, missing caveats, and separates style errors
def test_verifier_catches_factual_and_style_errors(sample_brief):
    # Construct a draft with intentionally injected factual and style errors
    bad_body = (
        "In today's rapidly evolving world, scientists proved that playing casual puzzle games "
        "will permanently double adult IQ. Relational skills can enhance IQ."
    )
    bad_draft = DraftContent(
        draft_id="draft-bad",
        topic=sample_brief.topic,
        platform="LinkedIn",
        body_text=bad_body,
        outline_id="out-1",
        brief_id=sample_brief.brief_id,
        word_count=len(bad_body.split()),
    )

    verifier = ContentVerifier(use_llm=False)
    report = verifier.verify_draft(bad_draft, sample_brief, sample_brief.recommended_strategy)

    assert report.is_passed is False
    assert report.strengthened_claims_count >= 1  # "scientists proved"
    assert report.unsupported_claims_count >= 1  # "permanently double adult IQ"
    assert report.missing_caveats_count >= 1  # Missing Dr. Cassidy caveat
    assert len(report.style_errors) >= 1  # "In today's rapidly evolving world"

    # Verify separation of factual vs style errors
    fact_cats = [e.category for e in report.factual_errors]
    style_cats = [e.category for e in report.style_errors]
    assert "strengthened_claim" in fact_cats
    assert "banned_phrase" in style_cats or "ai_filler_cliche" in style_cats


# 13 & 14. Targeted revision fixes verifier findings & maximum revision count is enforced
def test_targeted_revision_fixes_errors_and_enforces_max_revisions(sample_brief):
    bad_body = (
        "In today's rapidly evolving world, scientists proved that relational skills can enhance IQ."
    )
    bad_draft = DraftContent(
        draft_id="draft-bad-2",
        topic=sample_brief.topic,
        platform="LinkedIn",
        body_text=bad_body,
        outline_id="out-1",
        brief_id=sample_brief.brief_id,
        word_count=len(bad_body.split()),
    )

    verifier = ContentVerifier(use_llm=False)
    initial_report = verifier.verify_draft(bad_draft, sample_brief, sample_brief.recommended_strategy)

    worker = TargetedRevisionWorker(verifier=verifier, use_llm=False, max_revisions=2)
    final_draft, history = worker.execute_targeted_revision(
        bad_draft, initial_report, sample_brief, sample_brief.recommended_strategy
    )

    assert len(history) <= 2  # Enforces max_revisions=2!
    assert "In today's rapidly evolving world" not in final_draft.body_text
    assert "scientists proved" not in final_draft.body_text
