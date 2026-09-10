import json
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from agents.planner import ResearchPlanner
from config.gemini_config import (
    get_gemini_api_key,
    is_api_key_available,
    load_environment,
)
from core.research_plan import (
    ContrarianProbe,
    ResearchHypothesis,
    ResearchPlan,
    ResearchQuestion,
    StoppingCriteria,
)
from tools.llm_client import GeminiClient


# --- Mock JSON Payload for LLM Tests ---
MOCK_GEMINI_PLAN_JSON = json.dumps(
    {
        "topic": "AI in Healthcare",
        "goals": [
            "Assess AI diagnostic accuracy",
            "Evaluate clinical integration barriers",
        ],
        "questions": [
            {
                "id": "rq-1",
                "question": "How accurate are modern AI diagnostic models?",
                "rationale": "Understand clinical performance baseline",
                "priority": 1,
                "search_queries": ["AI medical diagnostic accuracy benchmarks"],
            },
            {
                "id": "rq-2",
                "question": "What regulatory hurdles exist for medical AI approval?",
                "rationale": "Identify compliance challenges",
                "priority": 2,
                "search_queries": ["FDA approval AI medical devices"],
            },
            {
                "id": "rq-3",
                "question": "How is patient data privacy preserved?",
                "rationale": "Examine HIPAA compliance",
                "priority": 3,
                "search_queries": ["HIPAA compliance AI healthcare"],
            },
            {
                "id": "rq-4",
                "question": "What is the cost efficiency of AI tools in hospitals?",
                "rationale": "Assess economic impact",
                "priority": 4,
                "search_queries": ["hospital AI return on investment"],
            },
            {
                "id": "rq-5",
                "question": "What is the liability framework for AI diagnostic errors?",
                "rationale": "Understand legal risks",
                "priority": 5,
                "search_queries": ["malpractice liability AI diagnostics"],
            },
        ],
        "hypotheses": [
            {
                "id": "rh-1",
                "statement": "AI diagnostics reduce misdiagnosis rates by over 20%.",
            },
            {
                "id": "rh-2",
                "statement": "Regulatory uncertainty delays AI hospital adoption by 2 years.",
            },
        ],
        "contrarian_probes": [
            {
                "id": "cp-1",
                "question": "Does AI automation increase total administrative overhead rather than reducing it?",
            },
            {
                "id": "cp-2",
                "question": "Are diagnostic AI models overfitted to synthetic laboratory datasets?",
            },
        ],
        "stopping_criteria": {
            "max_iterations": 3,
            "min_useful_evidence": 5,
            "saturation_threshold": 0.85,
        },
        "search_queries": [
            "AI medical diagnostic accuracy benchmarks",
            "FDA approval AI medical devices",
        ],
        "max_iterations": 3,
    }
)


# --- Deterministic & Schema Validation Tests ---
def test_deterministic_planner_creates_valid_research_plan():
    planner = ResearchPlanner(max_iterations=4, use_llm=False)
    topic = "Quantum Computing in Cybersecurity"
    plan = planner.create_plan(topic)

    assert isinstance(plan, ResearchPlan)
    assert plan.topic == topic
    assert plan.max_iterations == 4
    assert len(plan.goals) == 5
    assert len(plan.questions) == 5
    assert len(plan.hypotheses) >= 2
    assert len(plan.contrarian_probes) >= 2
    assert isinstance(plan.stopping_criteria, StoppingCriteria)
    assert plan.stopping_criteria.max_iterations == 4


def test_planner_empty_topic_raises_value_error():
    planner = ResearchPlanner(use_llm=False)
    with pytest.raises(ValueError, match="cannot be empty"):
        planner.create_plan("   ")


def test_research_plan_validation_max_iterations():
    plan = ResearchPlan(
        topic="AI Safety",
        goals=["Goal 1"],
        questions=[],
        stopping_criteria=StoppingCriteria(max_iterations=1),
        max_iterations=1,
    )
    assert plan.max_iterations == 1

    with pytest.raises(ValidationError):
        ResearchPlan(
            topic="AI Safety",
            goals=["Goal 1"],
            questions=[],
            max_iterations=0,
        )

    with pytest.raises(ValidationError):
        ResearchPlan(
            topic="AI Safety",
            goals=["Goal 1"],
            questions=[],
            max_iterations=11,
        )


def test_stopping_criteria_validation():
    with pytest.raises(ValidationError):
        StoppingCriteria(min_useful_evidence=0)

    with pytest.raises(ValidationError):
        StoppingCriteria(saturation_threshold=-0.1)

    with pytest.raises(ValidationError):
        StoppingCriteria(saturation_threshold=1.5)


# --- LLM Mocked & Configuration Tests ---
def test_mocked_gemini_output_creates_valid_research_plan():
    mock_client = MagicMock(spec=GeminiClient)
    mock_client.generate_json_plan.return_value = MOCK_GEMINI_PLAN_JSON

    planner = ResearchPlanner(use_llm=True, llm_client=mock_client)
    plan = planner.create_plan("AI in Healthcare")

    assert isinstance(plan, ResearchPlan)
    assert plan.topic == "AI in Healthcare"
    assert len(plan.questions) == 5
    assert len(plan.hypotheses) == 2
    assert len(plan.contrarian_probes) == 2
    assert plan.stopping_criteria.max_iterations == 3
    mock_client.generate_json_plan.assert_called_once()


def test_malformed_gemini_output_is_rejected():
    mock_client = MagicMock(spec=GeminiClient)
    mock_client.generate_json_plan.return_value = json.dumps({"topic": "Invalid Data"})

    planner = ResearchPlanner(use_llm=True, llm_client=mock_client)
    with pytest.raises(ValueError, match="Failed to parse Gemini response"):
        planner.create_plan("AI in Healthcare")


def test_missing_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr("config.gemini_config.load_dotenv", lambda **kwargs: None)

    assert is_api_key_available() is False
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        get_gemini_api_key()


def test_api_key_availability_indicator(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy_test_key")
    monkeypatch.setattr("config.gemini_config.load_dotenv", lambda **kwargs: None)

    assert is_api_key_available() is True
