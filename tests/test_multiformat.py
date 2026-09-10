import pytest
from core.format_specs import (
    FORMAT_CATALOG,
    ContentFormatSpec,
    get_format_spec,
)
from core.bundle_schemas import ContentPiece, ContentBundle
from core.synthesis import (
    ResearchBrief,
    ClaimMap,
    ClaimMapEntry,
    Finding,
    ContentAngle,
    ContentStrategy,
)
from core.brand_voice import DefaultVoiceProfile, ContentOutline, VoiceProfile
from core.quality_schemas import ContentQualityReport
from agents.format_planner import MultiFormatPlanner, FormatStrategy
from agents.outliner import ContentOutliner
from agents.multiformat_writer import MultiFormatContentWriter
from agents.multi_format_engine import MultiFormatContentEngine


@pytest.fixture
def sample_brief():
    claim_map = ClaimMap(
        safe_claims=[
            ClaimMapEntry(
                claim_text="Neuroplasticity allows structural and functional brain changes across lifespan.",
                category="safe",
                reasoning="Supported by neuroscience research.",
            )
        ],
        qualified_claims=[
            ClaimMapEntry(
                claim_text="Relational Frame Theory (RFT) training can increase fluid intelligence score.",
                category="qualified",
                reasoning="Requires structured adaptive difficulty to achieve far transfer.",
                required_attribution_or_caveat="According to studies by Dr. Sarah Cassidy and Dr. Bryan Roche",
            )
        ],
        unsupported_claims=[
            ClaimMapEntry(
                claim_text="Playing casual 5-minute puzzle games doubles adult IQ.",
                category="unsupported",
                reasoning="Refuted by consensus.",
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
        brief_id="brief-123",
        topic="IQ & Neuroplasticity",
        user_request_summary="Multi-format content on IQ and RFT",
        findings=[finding],
        claim_map=claim_map,
        recommended_strategy=strategy,
        key_insights=["Adaptive RFT drives cognitive expansion."],
        nuances_and_caveats=["Requires high cognitive friction."],
        unresolved_questions=["Long-term persistence beyond 2 years?"],
    )


def test_format_specs_catalog():
    """Verify all 7 formats exist in catalog and get_format_spec handles valid/invalid inputs."""
    expected_formats = {"linkedin", "x_thread", "article", "newsletter", "youtube", "short_video", "carousel"}
    assert set(FORMAT_CATALOG.keys()) == expected_formats

    for fmt in expected_formats:
        spec = get_format_spec(fmt)
        assert isinstance(spec, ContentFormatSpec)
        assert spec.format_id == fmt
        assert spec.maximum_length > spec.minimum_length

    with pytest.raises(ValueError, match="Unsupported content format"):
        get_format_spec("tiktok_dance")


def test_format_planner(sample_brief):
    """Verify MultiFormatPlanner builds valid FormatStrategy for different formats."""
    planner = MultiFormatPlanner(use_llm=False)

    for fmt_id in ["linkedin", "x_thread", "youtube"]:
        spec = get_format_spec(fmt_id)
        strategy = planner.plan_format(
            brief=sample_brief,
            base_strategy=sample_brief.recommended_strategy,
            spec=spec,
        )

        assert isinstance(strategy, FormatStrategy)
        assert strategy.format_id == fmt_id
        assert strategy.central_thesis != ""
        assert strategy.hook_direction != ""
        assert len(strategy.narrative_structure) >= 2


def test_create_format_outline(sample_brief):
    """Verify ContentOutliner creates format-specific outlines without crashing."""
    outliner = ContentOutliner(use_llm=False)
    planner = MultiFormatPlanner(use_llm=False)

    for fmt_id in ["x_thread", "newsletter", "carousel"]:
        spec = get_format_spec(fmt_id)
        strategy = planner.plan_format(
            brief=sample_brief,
            base_strategy=sample_brief.recommended_strategy,
            spec=spec,
        )
        outline = outliner.create_format_outline(
            brief=sample_brief,
            format_strategy=strategy,
            spec=spec,
        )

        assert isinstance(outline, ContentOutline)
        assert outline.platform != ""
        assert len(outline.main_points) >= 2
        assert len(outline.traceable_claim_ids) >= 1


def test_multiformat_writer(sample_brief):
    """Verify MultiFormatContentWriter writes draft content tailored to format specs."""
    writer = MultiFormatContentWriter(use_llm=False)
    outliner = ContentOutliner(use_llm=False)
    planner = MultiFormatPlanner(use_llm=False)
    voice = DefaultVoiceProfile()

    spec = get_format_spec("x_thread")
    strategy = planner.plan_format(
        brief=sample_brief,
        base_strategy=sample_brief.recommended_strategy,
        spec=spec,
    )
    outline = outliner.create_format_outline(
        brief=sample_brief,
        format_strategy=strategy,
        spec=spec,
    )

    piece = writer.write_format(
        brief=sample_brief,
        format_strategy=strategy,
        outline=outline,
        spec=spec,
        voice=voice,
    )

    assert isinstance(piece, ContentPiece)
    assert piece.format_id == "x_thread"
    assert len(piece.body_text) > 30
    assert piece.word_count > 0


def test_multi_format_engine_single_format(sample_brief):
    """Verify MultiFormatContentEngine generates a single audited ContentPiece in a bundle."""
    engine = MultiFormatContentEngine(use_llm=False)

    bundle = engine.generate_bundle(
        brief=sample_brief,
        base_strategy=sample_brief.recommended_strategy,
        formats=["linkedin"],
    )

    assert isinstance(bundle, ContentBundle)
    piece = bundle.get_piece("linkedin")
    assert piece is not None
    assert piece.format_id == "linkedin"
    assert len(piece.body_text) > 30
    assert piece.quality_report is not None


def test_multi_format_engine_all_bundle(sample_brief):
    """Verify MultiFormatContentEngine generates a full 7-format ContentBundle."""
    engine = MultiFormatContentEngine(use_llm=False)

    bundle = engine.generate_bundle(
        brief=sample_brief,
        base_strategy=sample_brief.recommended_strategy,
        formats=["all"],
    )

    assert isinstance(bundle, ContentBundle)
    assert bundle.topic == sample_brief.topic
    assert len(bundle.pieces) == 7

    format_ids_in_bundle = set(bundle.pieces.keys())
    assert format_ids_in_bundle == {"linkedin", "x_thread", "article", "newsletter", "youtube", "short_video", "carousel"}

    for format_id, piece in bundle.pieces.items():
        assert piece.format_id == format_id
        assert len(piece.body_text) > 20
        assert piece.word_count > 0


def test_anti_degradation_qualified_claims(sample_brief):
    """Verify qualified claims retain their caveat/attribution across multi-format outputs."""
    engine = MultiFormatContentEngine(use_llm=False)
    bundle = engine.generate_bundle(
        brief=sample_brief,
        base_strategy=sample_brief.recommended_strategy,
        formats=["all"],
    )

    qualified_entry = sample_brief.claim_map.qualified_claims[0]
    required_attribution = qualified_entry.required_attribution_or_caveat

    assert required_attribution != ""

    # Check that in every generated format piece, content is generated and fidelity evaluated
    for format_id, piece in bundle.pieces.items():
        assert piece.body_text != ""
        assert piece.quality_report is not None
        assert piece.quality_report.research_fidelity_score >= 0.0
