import pytest
from agents.content_quality import ContentQualityEngine
from agents.outliner import ContentOutliner
from agents.revision import TargetedRevisionWorker
from core.brand_voice import BrandProfile, ContentOutline, DefaultVoiceProfile, DraftContent, VoiceProfile
from core.quality_schemas import ContentQualityIssue, ContentQualityReport
from core.synthesis import ClaimMap, ClaimMapEntry, ContentAngle, ContentStrategy, Finding, ResearchBrief


@pytest.fixture
def quality_brief():
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
                claim_text="Relational Frame Theory (RFT) training can lead to an average 15 point fluid IQ gain in adult trials.",
                category="qualified",
                reasoning="Observed in specific trials but requires qualification.",
                required_attribution_or_caveat="According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche",
            ),
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
        brief_id="brief-qual-123",
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


# 1. Clean draft passes
def test_clean_draft_passes(quality_brief):
    clean_body = (
        "Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
        "Neuroscience confirms that adult neuroplasticity allows the brain to form new neural connections. "
        "Specific programs like Relational Frame Theory (RFT) report fluid intelligence gains of up to 15 point IQ increase (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche).\n\n"
        "True cognitive expansion requires continuous adaptive strain rather than casual puzzle games."
    )
    draft = DraftContent(
        draft_id="d-clean",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=clean_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(clean_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert report.overall_status == "passed"
    assert report.overall_score >= 0.70
    assert not any(i.severity == "high" for i in report.issues)


# 2. Meaningful claim strengthening is detected
def test_meaningful_claim_strengthening_detected(quality_brief):
    draft_body = (
        "Most brain training apps don't raise IQ.\n\n"
        "However, scientists proved that Relational Frame Theory guarantees a double IQ score in all adults."
    )
    draft = DraftContent(
        draft_id="d-strength",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert report.overall_status == "needs_revision"
    sub_cats = [i.sub_category for i in report.issues]
    assert "causal_strengthening" in sub_cats


# 3. Attribution loss is detected
def test_attribution_loss_detected(quality_brief):
    attrib_brief = quality_brief.model_copy(deep=True)
    attrib_brief.claim_map.qualified_claims.append(
        ClaimMapEntry(
            claim_text="Company X software delivers a 40% efficiency improvement.",
            category="qualified",
            reasoning="Vendor claim requiring explicit attribution.",
            required_attribution_or_caveat="Company X claims 40% improvement",
        )
    )

    draft_body = (
        "Most brain training apps don't raise IQ.\n\n"
        "According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche, RFT training can lead to an average 15 point fluid IQ gain.\n\n"
        "The software delivers a 40% efficiency improvement across all users."
    )
    draft = DraftContent(
        draft_id="d-attrib",
        topic=attrib_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=attrib_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, attrib_brief, attrib_brief.recommended_strategy)

    sub_cats = [i.sub_category for i in report.issues]
    assert "attribution_loss" in sub_cats


# 4. Numerical distortion is detected
def test_numerical_distortion_detected(quality_brief):
    draft_body = (
        "Most brain training apps don't raise IQ.\n\n"
        "According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche, RFT studies demonstrated a 50 point IQ gain in participants."
    )
    draft = DraftContent(
        draft_id="d-num",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    sub_cats = [i.sub_category for i in report.issues]
    assert "numerical_distortion" in sub_cats


# 5. Harmless simplification does NOT get falsely flagged
def test_harmless_simplification_not_falsely_flagged(quality_brief):
    simplified_body = (
        "Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
        "The adult brain can reorganize its neural pathways when exposed to adaptive difficulty.\n\n"
        "Research (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche) suggests that relational skills training can enhance fluid reasoning."
    )
    draft = DraftContent(
        draft_id="d-simple",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=simplified_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(simplified_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    fidelity_high_issues = [i for i in report.issues if i.category == "research_fidelity" and i.severity == "high"]
    assert len(fidelity_high_issues) == 0


# 6. Generic AI filler is detected
def test_generic_ai_filler_detected(quality_brief):
    draft_body = (
        "In today's rapidly evolving world, unlocking your potential is essential.\n\n"
        "Let's dive in to explore how neuroplasticity changes everything."
    )
    draft = DraftContent(
        draft_id="d-filler",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    categories = [i.category for i in report.issues]
    sub_cats = [i.sub_category for i in report.issues]
    assert "voice_alignment" in categories
    assert "banned_phrase" in sub_cats


# 7. Repetition is detected
def test_repetition_detected(quality_brief):
    draft_body = (
        "Most brain training apps don't increase IQ score.\n\n"
        "Most brain training apps don't increase IQ score.\n\n"
        "Cognitive training requires adaptive difficulty."
    )
    draft = DraftContent(
        draft_id="d-rep",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    sub_cats = [i.sub_category for i in report.issues]
    assert "repetition" in sub_cats


# 8. Weak hook is detected
def test_weak_hook_detected(quality_brief):
    draft_body = (
        "Welcome to my post about brain training and IQ.\n\n"
        "Neuroplasticity shows the brain can reorganize."
    )
    draft = DraftContent(
        draft_id="d-hook",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    sub_cats = [i.sub_category for i in report.issues]
    assert "weak_hook" in sub_cats


# 9, 10, 11. Separation of research issue and style issue
def test_research_issue_and_style_issue_separated(quality_brief):
    draft_body = (
        "In today's rapidly evolving world, scientists proved that playing casual puzzle games "
        "will permanently double adult IQ."
    )
    draft = DraftContent(
        draft_id="d-sep",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=draft_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(draft_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    categories = set(i.category for i in report.issues)
    assert "research_fidelity" in categories
    assert "voice_alignment" in categories


# 12, 13, 14. Targeted revision fixes flagged issues & max 2 passes enforced
def test_targeted_revision_fixes_issues_and_enforces_max_passes(quality_brief):
    bad_body = (
        "In today's rapidly evolving world, scientists proved that relational skills can enhance IQ."
    )
    bad_draft = DraftContent(
        draft_id="d-bad-qual",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=bad_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(bad_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    initial_report = engine.evaluate_quality(bad_draft, quality_brief, quality_brief.recommended_strategy)

    worker = TargetedRevisionWorker(use_llm=False, max_revisions=2)
    final_draft, history = worker.execute_targeted_quality_revision(
        bad_draft, initial_report, quality_brief, quality_brief.recommended_strategy, quality_engine=engine
    )

    assert len(history) <= 2  # Enforces max 2 passes!
    assert "In today's rapidly evolving world" not in final_draft.body_text
    assert "scientists proved" not in final_draft.body_text
