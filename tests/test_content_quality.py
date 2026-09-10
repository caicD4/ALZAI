import pytest
from agents.content_quality import ContentQualityEngine
from agents.revision import TargetedRevisionWorker
from core.brand_voice import DefaultVoiceProfile, DraftContent, VoiceProfile
from core.quality_schemas import ContentQualityReport
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


# 1. Regression test for exact malformed sentence from E2E run
def test_exact_malformed_sentence_detected_and_fixed(quality_brief):
    malformed_body = (
        "Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
        "Neuroscience confirms that while adult neuroplasticity is real—targeted interventions can produce measurable cognitive changes in trained tasks.—true cognitive expansion requires a fundamentally different architecture.\n\n"
        "That architecture is Relational Frame Theory (RFT).\n\n"
        "Specific programs report cognitive gains (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche).\n\n"
        "What cognitive skills are you actively training this year?"
    )
    draft = DraftContent(
        draft_id="d-malformed-e2e",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=malformed_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(malformed_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    initial_report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    # 1. Quality Engine MUST detect the prose defect!
    assert initial_report.overall_status == "needs_revision"
    sub_cats = [i.sub_category for i in initial_report.issues]
    assert "malformed_punctuation" in sub_cats

    # 2. TargetedRevisionWorker fixes the issue
    worker = TargetedRevisionWorker(use_llm=False, max_revisions=2)
    final_draft, history = worker.execute_targeted_quality_revision(
        draft, initial_report, quality_brief, quality_brief.recommended_strategy, quality_engine=engine
    )

    assert len(history) <= 2
    assert "tasks.—" not in final_draft.body_text
    final_report = engine.evaluate_quality(final_draft, quality_brief, quality_brief.recommended_strategy)
    assert final_report.overall_status == "passed"


# Adversarial Test A: Clearly bad prose -> detected
def test_adversarial_bad_prose_detected(quality_brief):
    bad_body = (
        "Most brain brain training apps don't increase IQ score..\n\n"
        "Neuroscience confirms that adult neuroplasticity is real (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche"
    )
    draft = DraftContent(
        draft_id="d-bad-prose",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=bad_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(bad_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert report.overall_status == "needs_revision"
    sub_cats = [i.sub_category for i in report.issues]
    assert "repeated_words" in sub_cats or "malformed_punctuation" in sub_cats or "broken_sentence" in sub_cats


# Adversarial Test B: Clean conversational prose -> passes
def test_adversarial_clean_conversational_prose_passes(quality_brief):
    clean_body = (
        "Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
        "Neuroscience confirms that adult neuroplasticity allows the brain to form new neural connections. "
        "Specific programs like Relational Frame Theory (RFT) report fluid intelligence gains of up to 15 point IQ increase (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche).\n\n"
        "True cognitive expansion requires continuous adaptive strain rather than casual puzzle games."
    )
    draft = DraftContent(
        draft_id="d-clean-conv",
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
    assert report.overall_score >= 0.85
    assert len([i for i in report.issues if i.severity == "high"]) == 0


# Adversarial Test C: Strong hook -> does NOT get penalized merely for being bold
def test_adversarial_strong_hook_not_penalized(quality_brief):
    bold_body = (
        "90% of popular brain apps are selling snake oil.\n\n"
        "Neuroscience confirms that adult neuroplasticity enables neural reorganization. "
        "Relational skills training yields fluid gains (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche).\n\n"
        "True expansion requires continuous adaptive load."
    )
    draft = DraftContent(
        draft_id="d-bold-hook",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=bold_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(bold_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert not any(i.sub_category == "weak_hook" for i in report.issues)


# Adversarial Test D: Scientific caveat -> does NOT get unnecessarily rewritten
def test_adversarial_scientific_caveat_preserved(quality_brief):
    caveat_body = (
        "Most brain training apps don't increase IQ.\n\n"
        "According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche, RFT training can lead to fluid IQ gains under specific adaptive conditions."
    )
    draft = DraftContent(
        draft_id="d-caveat",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=caveat_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(caveat_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert report.overall_status == "passed"


# Adversarial Test E: Harmless simplification -> does NOT get flagged
def test_adversarial_harmless_simplification_not_flagged(quality_brief):
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


# Adversarial Test F: Claim strengthening -> detected
def test_adversarial_claim_strengthening_detected(quality_brief):
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


# Adversarial Test G: Attribution loss -> detected
def test_adversarial_attribution_loss_detected(quality_brief):
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


# Adversarial Test H: Numerical distortion -> detected
def test_adversarial_numerical_distortion_detected(quality_brief):
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


# Adversarial Test I: AI cliché -> detected
def test_adversarial_ai_cliche_detected(quality_brief):
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

    sub_cats = [i.sub_category for i in report.issues]
    assert "banned_phrase" in sub_cats


# Adversarial Test J: Platform mismatch -> detected
def test_adversarial_platform_mismatch_detected(quality_brief):
    long_body = "word " * 650
    draft = DraftContent(
        draft_id="d-long-plat",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=long_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=650,
    )

    engine = ContentQualityEngine(use_llm=False)
    report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    sub_cats = [i.sub_category for i in report.issues]
    assert "platform_length_mismatch" in sub_cats


# Adversarial Test K: Repetition -> detected
def test_adversarial_repetition_detected(quality_brief):
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


# Adversarial Test L: Good LinkedIn post -> does NOT get rewritten unnecessarily
def test_adversarial_good_linkedin_post_not_rewritten(quality_brief):
    clean_body = (
        "Most brain training apps don't increase IQ. They simply make you faster at playing their specific puzzle games.\n\n"
        "Neuroscience confirms that adult neuroplasticity allows the brain to form new neural connections. "
        "Specific programs like Relational Frame Theory (RFT) report fluid intelligence gains of up to 15 point IQ increase (according to studies by Dr. Sarah Cassidy and Dr. Bryan Roche).\n\n"
        "True cognitive expansion requires continuous adaptive strain rather than casual puzzle games."
    )
    draft = DraftContent(
        draft_id="d-good-li",
        topic=quality_brief.topic,
        platform="LinkedIn",
        body_text=clean_body,
        outline_id="out-1",
        brief_id=quality_brief.brief_id,
        word_count=len(clean_body.split()),
    )

    engine = ContentQualityEngine(use_llm=False)
    initial_report = engine.evaluate_quality(draft, quality_brief, quality_brief.recommended_strategy)

    assert initial_report.overall_status == "passed"

    worker = TargetedRevisionWorker(use_llm=False, max_revisions=2)
    final_draft, history = worker.execute_targeted_quality_revision(
        draft, initial_report, quality_brief, quality_brief.recommended_strategy, quality_engine=engine
    )

    assert len(history) == 0  # 0 revision passes executed because content is already good!
    assert final_draft.body_text == draft.body_text
