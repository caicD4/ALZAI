"""Tests for execution trace, structured failure categories, and GeminiClient tracing."""

import json
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from tools.execution_trace import (
    ExecutionTrace,
    FailureCategory,
    TraceEntry,
    classify_exception,
    get_trace,
    reset_trace,
)
from tools.llm_client import GeminiClient


# ---------------------------------------------------------------------------
# ExecutionTrace basic behavior
# ---------------------------------------------------------------------------

class TestExecutionTrace:
    def test_record_and_entries(self):
        trace = ExecutionTrace()
        entry = trace.record(
            stage="TestStage",
            method="generate_json",
            agent="GeminiClient",
            status="success",
            duration_ms=123.4,
        )
        assert len(trace.entries) == 1
        assert entry.stage == "TestStage"
        assert entry.status == "success"
        assert entry.duration_ms == 123.4

    def test_summary_counts(self):
        trace = ExecutionTrace()
        trace.record(stage="A", method="m", agent="a", status="success", duration_ms=100)
        trace.record(stage="B", method="m", agent="a", status="failure", duration_ms=200, failure_category="rate_limited")
        trace.record(stage="C", method="m", agent="a", status="success", duration_ms=50)
        s = trace.summary()
        assert s["total_calls"] == 3
        assert s["successes"] == 2
        assert s["failures"] == 1
        assert s["failure_categories"]["rate_limited"] == 1
        assert s["total_duration_ms"] == 350.0

    def test_clear(self):
        trace = ExecutionTrace()
        trace.record(stage="X", method="m", agent="a", status="success")
        trace.clear()
        assert len(trace.entries) == 0

    def test_summary_empty(self):
        trace = ExecutionTrace()
        s = trace.summary()
        assert s["total_calls"] == 0
        assert s["successes"] == 0
        assert s["failures"] == 0


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestModuleSingleton:
    def test_get_trace_returns_same_instance(self):
        reset_trace()
        t1 = get_trace()
        t2 = get_trace()
        assert t1 is t2

    def test_reset_clears(self):
        get_trace().record(stage="test", method="m", agent="a", status="success")
        reset_trace()
        assert len(get_trace().entries) == 0


# ---------------------------------------------------------------------------
# FailureCategory classification
# ---------------------------------------------------------------------------

class TestClassifyException:
    def test_rate_limit_429(self):
        assert classify_exception(Exception("429 RESOURCE_EXHAUSTED")) == FailureCategory.RATE_LIMITED

    def test_rate_limit_word(self):
        assert classify_exception(Exception("Rate limit exceeded")) == FailureCategory.RATE_LIMITED

    def test_timeout_504(self):
        assert classify_exception(Exception("504 Gateway Timeout")) == FailureCategory.TIMEOUT

    def test_timeout_word(self):
        assert classify_exception(Exception("deadline exceeded")) == FailureCategory.TIMEOUT

    def test_invalid_json(self):
        assert classify_exception(Exception("Expecting value: JSON decode error")) == FailureCategory.INVALID_JSON

    def test_validation_error(self):
        assert classify_exception(Exception("ValidationError: field required")) == FailureCategory.VALIDATION_ERROR

    def test_empty_response(self):
        assert classify_exception(Exception("Gemini API returned an empty or null response.")) == FailureCategory.EMPTY_RESPONSE

    def test_generic_api_error(self):
        assert classify_exception(Exception("Something went wrong")) == FailureCategory.API_ERROR


# ---------------------------------------------------------------------------
# GeminiClient tracing — mocked generate_content
# ---------------------------------------------------------------------------

def _make_mock_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


def _make_mock_client(response_text: str):
    """Create a GeminiClient with a mocked genai.Client."""
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = _make_mock_response(response_text)

    client = GeminiClient(api_key="test-key-12345")
    with patch("tools.llm_client.genai.Client", return_value=mock_client):
        yield client, mock_client


class TestGeminiClientTracing:
    def test_success_records_trace(self):
        reset_trace()
        json_resp = json.dumps({"result": "ok"})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(json_resp)

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            result = client.generate_json(prompt="test", stage_label="TestStage")

        assert result == json_resp
        entries = get_trace().entries
        assert len(entries) == 1
        e = entries[0]
        assert e.stage == "TestStage"
        assert e.status == "success"
        assert e.failure_category is None
        assert e.duration_ms >= 0

    def test_rate_limit_records_failure_category(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(Exception, match="429"):
                client.generate_json(prompt="test", stage_label="Extractor")

        entries = get_trace().entries
        assert len(entries) == 1
        e = entries[0]
        assert e.status == "failure"
        assert e.failure_category == FailureCategory.RATE_LIMITED
        assert e.stage == "Extractor"

    def test_invalid_json_records_failure(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response("NOT JSON {{{")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="not valid JSON"):
                client.generate_json(prompt="test", stage_label="Synthesizer")

        entries = get_trace().entries
        assert len(entries) == 1
        e = entries[0]
        assert e.status == "failure"
        assert e.failure_category == FailureCategory.INVALID_JSON

    def test_empty_response_records_failure(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response("")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(ValueError, match="empty or null"):
                client.generate_json(prompt="test", stage_label="Outliner")

        entries = get_trace().entries
        assert len(entries) == 1
        e = entries[0]
        assert e.status == "failure"
        assert e.failure_category == FailureCategory.EMPTY_RESPONSE

    def test_no_api_key_in_trace_entries(self):
        reset_trace()
        json_resp = json.dumps({"key": "value"})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(json_resp)

        client = GeminiClient(api_key="super-secret-key-12345")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            client.generate_json(prompt="test", stage_label="Test")

        for entry in get_trace().entries:
            full_text = json.dumps(entry.__dict__)
            assert "super-secret-key" not in full_text
            assert "12345" not in full_text

    def test_generate_json_plan_traces_research_planner(self):
        reset_trace()
        json_resp = json.dumps({"topic": "test", "questions": []})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(json_resp)

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            result = client.generate_json_plan("test topic", {"type": "object"})

        assert result == json_resp
        entries = get_trace().entries
        assert len(entries) == 1
        assert entries[0].stage == "ResearchPlanner"

    def test_multiple_calls_record_multiple_entries(self):
        reset_trace()
        json_resp = json.dumps({"a": 1})
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(json_resp)

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            client.generate_json(prompt="p1", stage_label="Stage1")
            client.generate_json(prompt="p2", stage_label="Stage2")
            client.generate_json(prompt="p3", stage_label="Stage3")

        entries = get_trace().entries
        assert len(entries) == 3
        assert [e.stage for e in entries] == ["Stage1", "Stage2", "Stage3"]


# ---------------------------------------------------------------------------
# Agent stage_label propagation (integration-ish)
# ---------------------------------------------------------------------------

class TestAgentStageLabels:
    """Verify that agents pass correct stage_label to generate_json."""

    def test_request_intent_stage_label(self):
        reset_trace()
        json_resp = json.dumps({
            "subject": "Test",
            "task": "Test task",
            "intent_type": "explanation",
            "research_goal": "Test goal",
        })
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = _make_mock_response(json_resp)

        from core.request_intent import RequestInterpreter, UserRequest
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            interp = RequestInterpreter(llm_client=GeminiClient(api_key="k"), use_llm=True)
            intent = interp.interpret(UserRequest(raw_prompt="explain test"))

        entries = get_trace().entries
        assert any(e.stage == "RequestIntent" for e in entries)

    def test_synthesizer_stage_label(self):
        reset_trace()
        # Force fallback path (no LLM)
        from agents.synthesizer import ResearchSynthesizer
        synth = ResearchSynthesizer(use_llm=False)
        from core.research_plan import ResearchPlan, ResearchQuestion, StoppingCriteria
        from core.evidence import EvidenceItem

        plan = ResearchPlan(
            topic="test",
            goals=["g"],
            questions=[ResearchQuestion(id="q1", question="q", rationale="r", priority=1, search_queries=[])],
            hypotheses=[],
            contrarian_probes=[],
            stopping_criteria=StoppingCriteria(max_iterations=1, min_useful_evidence=1, saturation_threshold=0.5),
            search_queries=[],
            max_iterations=1,
        )
        item = EvidenceItem(
            evidence_id="e1",
            fetch_id="f1",
            locator="0:10",
            verbatim_quote="test quote",
            claim_summary="test claim",
            insight_type="research_finding",
        )
        brief = synth.synthesize_research(plan, [item], "test topic")
        # No LLM calls in fallback mode
        entries = get_trace().entries
        assert len(entries) == 0


# ---------------------------------------------------------------------------
# Structured failure never silently swallowed
# ---------------------------------------------------------------------------

class TestFailureVisibility:
    def test_rate_limit_failure_is_recorded_not_silent(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429RESOURCE_EXHAUSTED")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(Exception):
                client.generate_json(prompt="test", stage_label="Test")

        summary = get_trace().summary()
        assert summary["failures"] == 1
        assert summary["failure_categories"].get("rate_limited", 0) == 1

    def test_timeout_failure_is_recorded(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("504 UNAVAILABLE")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(Exception):
                client.generate_json(prompt="test", stage_label="Test")

        summary = get_trace().summary()
        assert summary["failure_categories"].get("timeout", 0) == 1

    def test_api_error_failure_is_recorded(self):
        reset_trace()
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("INTERNAL_ERROR")

        client = GeminiClient(api_key="test-key")
        with patch("tools.llm_client.genai.Client", return_value=mock_client):
            with pytest.raises(Exception):
                client.generate_json(prompt="test", stage_label="Test")

        summary = get_trace().summary()
        assert summary["failure_categories"].get("api_error", 0) == 1
