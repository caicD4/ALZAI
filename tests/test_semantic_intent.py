import pytest
from core.request_intent import RequestIntent, RequestInterpreter, UserRequest
from core.research_plan import ResearchPlan
from agents.planner import ResearchPlanner
from agents.synthesizer import ResearchSynthesizer
from agents.multiformat_writer import MultiFormatContentWriter, renumber_x_thread
from agents.multi_format_engine import MultiFormatContentEngine
from agents.content_quality import ContentQualityEngine
from core.brand_voice import DraftContent, VoiceProfile
from core.synthesis import ContentStrategy


def test_intent_claim_investigation_elon_musk():
    """TEST A: Critique / claim_investigation intent type for 'why elon musk sucks'."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="why elon musk sucks")
    intent = interpreter.interpret(req)

    assert intent.intent_type in ("claim_investigation", "critique")
    assert intent.subject == "Elon Musk"
    assert intent.proposition == "why elon musk sucks"
    assert "investigate" in intent.research_goal.lower() or "criticisms" in intent.research_goal.lower()


def test_intent_claim_investigation_sam_altman():
    """TEST B: Critique / claim_investigation intent type for 'why sam altman is shady'."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="why sam altman is shady")
    intent = interpreter.interpret(req)

    assert intent.intent_type in ("claim_investigation", "critique")
    assert intent.subject == "Sam Altman"
    assert intent.proposition == "why sam altman is shady"


def test_intent_question_multiagent():
    """TEST C: Question style intent regarding AI agent architecture."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="why modern AI agent architectures are shifting from single prompts to multi-agent orchestration")
    intent = interpreter.interpret(req)

    assert intent.intent_type in ("question", "claim_investigation", "topic_request")
    assert "agent" in intent.subject.lower() or "multi-agent" in intent.research_goal.lower()
    assert "RFT" not in str(intent)
    assert "neuroplasticity" not in str(intent)


def test_intent_explanation_moe():
    """TEST D: Explanation intent for mixture of experts."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="explain mixture of experts")
    intent = interpreter.interpret(req)

    assert intent.intent_type == "explanation"
    assert "mixture of experts" in intent.subject.lower()
    assert "Explain" in intent.task or "architecture" in intent.research_goal.lower()


def test_intent_claim_investigation_remote_work():
    """TEST E: Claim investigation for remote work killing productivity."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="remote work kills productivity")
    intent = interpreter.interpret(req)

    assert intent.intent_type in ("claim_investigation", "critique")
    assert "remote work" in intent.subject.lower()
    assert intent.proposition == "remote work kills productivity"


def test_intent_comparison_claude_chatgpt():
    """TEST F: Comparison intent for Claude vs ChatGPT."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="compare claude and chatgpt for coding")
    intent = interpreter.interpret(req)

    assert intent.intent_type == "comparison"
    assert "claude" in intent.subject.lower() or "chatgpt" in intent.subject.lower()


def test_intent_how_to_discord_bot():
    """TEST G: How_to intent for Discord moderator."""
    interpreter = RequestInterpreter(use_llm=False)
    req = UserRequest(raw_prompt="how do I build an autonomous discord moderator?")
    intent = interpreter.interpret(req)

    assert intent.intent_type == "how_to"
    assert "discord" in intent.subject.lower()


def test_genericity_difference_test():
    """TEST 8: Verify that 3 prompts generate semantically distinct outputs, not identical templates."""
    engine = MultiFormatContentEngine(use_llm=False)
    planner = ResearchPlanner(use_llm=False)
    synthesizer = ResearchSynthesizer(use_llm=False)

    prompts = [
        "why elon musk sucks",
        "why remote work sucks",
        "why AI sucks",
    ]

    outputs = []
    for prompt in prompts:
        plan = planner.create_plan(prompt)
        brief = synthesizer.synthesize_research(plan, [], prompt)
        strategy = brief.recommended_strategy
        bundle = engine.generate_bundle(brief, strategy, formats=["linkedin"])
        piece = bundle.pieces["linkedin"]
        outputs.append((piece.title, piece.body_text))

    title1, body1 = outputs[0]
    title2, body2 = outputs[1]
    title3, body3 = outputs[2]

    # Verify titles are clean and distinct
    assert title1 != title2 and title2 != title3
    assert "Elon Musk" in title1
    assert "Remote Work" in title2
    assert "Ai" in title3 or "AI" in title3

    # Verify no raw prompt leaks in titles or bodies
    assert "Key Strategic Principles Behind elon musk sucks" not in title1
    assert "Key Strategic Principles Behind elon musk sucks" not in body1
    assert "Primary evidence supports core structural mechanisms" not in body1
    assert "Understanding the core operational shift" not in body1


def test_semantic_quality_engine_checks():
    """TEST 9: ContentQualityEngine correctly flags generic filler and raw prompt leaks."""
    engine = ContentQualityEngine(use_llm=False)
    
    bad_draft = DraftContent(
        draft_id="d-bad",
        topic="elon musk sucks",
        platform="LinkedIn",
        title="Key Strategic Principles Behind elon musk sucks: Strategic Perspectives",
        body_text="Understanding the core operational shift in Key Strategic Principles Behind elon musk sucks. Primary evidence supports core structural mechanisms and functional workflows associated with elon musk sucks.",
        outline_id="out-bad",
        brief_id="brief-bad",
        word_count=40,
    )
    
    from core.synthesis import ClaimMap, ContentAngle, ContentStrategy, Finding, ResearchBrief
    brief = ResearchBrief(
        brief_id="b-1",
        topic="elon musk sucks",
        user_request_summary="summary",
        findings=[],
        claim_map=ClaimMap(safe_claims=[], qualified_claims=[], unsupported_claims=[]),
        key_mechanisms=[],
        case_studies_and_examples=[],
        research_gaps=[],
        content_angles=[],
    )
    angle = ContentAngle(
        angle_id="a-bad",
        angle_title="Key Strategic Principles Behind elon musk sucks",
        central_thesis="thesis",
        why_interesting="why",
        intended_audience="audience",
        suitable_platform="LinkedIn",
    )
    strategy = ContentStrategy(
        topic="elon musk sucks",
        content_type="linkedin_post",
        platform="LinkedIn",
        audience="professionals",
        objective="educate",
        selected_angle=angle,
        thesis="thesis",
        hook_direction="hook",
        key_points=[],
        claims_to_include=[],
        claims_to_avoid=[],
        evidence_to_reference=[],
        counterpoints=[],
        desired_takeaway="takeaway",
    )

    report = engine.evaluate_quality(bad_draft, brief, strategy)
    assert report.overall_status == "needs_revision"
    sub_cats = [i.sub_category for i in report.issues]
    assert "template_filler" in sub_cats or "raw_prompt_leak" in sub_cats


def test_x_thread_numbering_sequential():
    """TEST 10: Verify X thread posts are strictly and sequentially numbered 1/, 2/, 3/, ..."""
    raw_posts_with_duplicates = "1/ First post hook\n\n2/ Second post content\n\n2/ Duplicate second post\n\n3/ Third post\n\n4/ Fourth post"
    renumbered = renumber_x_thread(raw_posts_with_duplicates)

    lines = [s.strip() for s in renumbered.split("\n\n") if s.strip()]
    assert len(lines) == 5
    assert lines[0].startswith("1/")
    assert lines[1].startswith("2/")
    assert lines[2].startswith("3/")
    assert lines[3].startswith("4/")
    assert lines[4].startswith("5/")

