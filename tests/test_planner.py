import pytest
from pydantic import ValidationError

from agents.planner import ResearchPlanner
from core.research_plan import ResearchPlan, ResearchQuestion


def test_planner_creates_valid_research_plan():
    planner = ResearchPlanner(max_iterations=4)
    topic = "Quantum Computing in Cybersecurity"
    plan = planner.create_plan(topic)

    # Verify return type
    assert isinstance(plan, ResearchPlan)

    # Verify top-level fields
    assert plan.topic == topic
    assert plan.max_iterations == 4
    assert len(plan.goals) > 0
    assert len(plan.questions) == 3
    assert len(plan.search_queries) > 0

    # Verify structure of research questions
    for q in plan.questions:
        assert isinstance(q, ResearchQuestion)
        assert q.id.startswith("rq-")
        assert len(q.question) > 0
        assert len(q.rationale) > 0
        assert isinstance(q.priority, int)
        assert isinstance(q.search_queries, list)
        assert len(q.search_queries) > 0


def test_planner_empty_topic_raises_value_error():
    planner = ResearchPlanner()
    with pytest.raises(ValueError, match="cannot be empty"):
        planner.create_plan("   ")


def test_research_plan_validation_max_iterations():
    # Valid bounds
    plan = ResearchPlan(
        topic="AI Safety",
        goals=["Goal 1"],
        questions=[],
        search_queries=[],
        max_iterations=1,
    )
    assert plan.max_iterations == 1

    # Invalid lower bound
    with pytest.raises(ValidationError):
        ResearchPlan(
            topic="AI Safety",
            goals=["Goal 1"],
            questions=[],
            search_queries=[],
            max_iterations=0,
        )

    # Invalid upper bound
    with pytest.raises(ValidationError):
        ResearchPlan(
            topic="AI Safety",
            goals=["Goal 1"],
            questions=[],
            search_queries=[],
            max_iterations=11,
        )
