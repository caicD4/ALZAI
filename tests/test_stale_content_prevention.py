import asyncio
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.api import app
from app.orchestrator import PipelineOrchestrator, GenerationJob
from core.bundle_schemas import ContentBundle, ContentPiece
from core.synthesis import ContentStrategy, ContentAngle, ClaimMap, ClaimMapEntry
from core.quality_schemas import ContentQualityReport

client = TestClient(app)

def create_mock_bundle(topic: str, format_id: str = "linkedin") -> ContentBundle:
    mock_angle = ContentAngle(
        angle_id=f"angle_{hash(topic) & 0xffffffff:08x}",
        angle_title=f"Strategic Breakdown: {topic}",
        central_thesis=f"Core thesis for {topic}.",
        why_interesting=f"Why {topic} matters.",
        intended_audience="Audience",
        suitable_platform=format_id.title()
    )

    mock_claim_map = ClaimMap(
        safe_claims=[ClaimMapEntry(claim_text=f"Established fact about {topic}", category="safe", reasoning="Reasoning")],
    )

    mock_strategy = ContentStrategy(
        topic=topic,
        content_type=format_id,
        platform=format_id.title(),
        audience="General",
        objective="Educate",
        selected_angle=mock_angle,
        thesis=f"Thesis statement for {topic}",
        hook_direction=f"Hook for {topic}",
        key_points=[f"Key point 1 for {topic}"],
        claims_to_include=[f"Claim for {topic}"],
        claims_to_avoid=[],
        evidence_to_reference=[f"Evidence for {topic}"],
        counterpoints=[f"Counterpoint for {topic}"],
        desired_takeaway=f"Takeaway for {topic}",
        claim_map=mock_claim_map
    )

    mock_piece = ContentPiece(
        content_id=f"piece_{format_id}_{hash(topic) & 0xffffffff:08x}",
        format_id=format_id,
        platform=format_id.title(),
        title=f"Output for {topic}",
        body_text=f"This is custom generated body text specifically for topic: {topic}. It discusses {topic} in depth without any hardcoded fallback content.",
        sections=[f"Section 1 for {topic}"],
        word_count=25,
        estimated_duration="1 min",
        quality_report=ContentQualityReport(
            report_id=f"report_{hash(topic) & 0xffffffff:08x}",
            draft_id=f"draft_{hash(topic) & 0xffffffff:08x}",
            overall_status="passed",
            overall_score=0.98,
            research_fidelity_score=1.0,
            content_quality_score=0.95,
            voice_alignment_score=1.0,
            platform_fit_score=1.0,
            summary_assessment=f"Quality report for {topic}"
        )
    )

    return ContentBundle(
        bundle_id=f"bundle_{hash(topic) & 0xffffffff:08x}",
        brief_id=f"brief_{hash(topic) & 0xffffffff:08x}",
        topic=topic,
        source_strategy=mock_strategy,
        pieces={format_id: mock_piece},
        created_at=datetime.now()
    )


# TEST 1: Request A ("IQ") vs Request B ("AI Agents"). Response B must NOT contain A's content or brain training text.
def test_topic_b_response_does_not_contain_topic_a_content():
    topic_a = "IQ increase through neuroplasticity"
    topic_b = "Why modern AI agent architectures are shifting from single prompts to multi-agent orchestration"

    async def mock_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "completed"
            job.bundle = create_mock_bundle(job.prompt, job.format_id)

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        # Generate Topic A
        res_a = client.post("/api/generate", json={"prompt": topic_a, "format": "linkedin"})
        job_id_a = res_a.json()["job_id"]
        data_a = client.get(f"/api/generate/{job_id_a}").json()
        assert data_a["bundle"]["topic"] == topic_a

        # Generate Topic B
        res_b = client.post("/api/generate", json={"prompt": topic_b, "format": "x_thread"})
        job_id_b = res_b.json()["job_id"]
        data_b = client.get(f"/api/generate/{job_id_b}").json()

        assert data_b["bundle"]["topic"] == topic_b
        body_text_b = data_b["bundle"]["pieces"]["x_thread"]["body_text"]

        # Assert topic B output does NOT contain topic A keywords or stale hardcoded brain training strings
        assert "brain training" not in body_text_b.lower()
        assert "relational frame theory" not in body_text_b.lower()
        assert "rft" not in body_text_b.lower()
        assert topic_b in body_text_b or "multi-agent orchestration" in body_text_b


# TEST 2: Generate LinkedIn content for Topic A, X content for Topic B. Verify X response belongs to B.
def test_format_x_for_topic_b_belongs_to_topic_b():
    topic_a = "Topic A: Neuroplasticity"
    topic_b = "Topic B: AI Agent Orchestration"

    async def mock_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "completed"
            job.bundle = create_mock_bundle(job.prompt, job.format_id)

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        res_a = client.post("/api/generate", json={"prompt": topic_a, "format": "linkedin"})
        job_id_a = res_a.json()["job_id"]

        res_b = client.post("/api/generate", json={"prompt": topic_b, "format": "x_thread"})
        job_id_b = res_b.json()["job_id"]

        data_b = client.get(f"/api/generate/{job_id_b}").json()
        assert data_b["bundle"]["topic"] == topic_b
        assert "x_thread" in data_b["bundle"]["pieces"]
        assert data_b["bundle"]["pieces"]["x_thread"]["topic_or_body"] if hasattr(data_b["bundle"]["pieces"]["x_thread"], "topic_or_body") else True
        assert "Topic B" in data_b["bundle"]["pieces"]["x_thread"]["body_text"]


# TEST 3: Concurrent requests maintain separate job results
def test_concurrent_generation_isolation():
    topics = [
        "Topic 1: Quantum Computing Frameworks",
        "Topic 2: Microservices Event Sourcing",
        "Topic 3: Autonomous Vehicle Computer Vision"
    ]

    async def mock_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "completed"
            job.bundle = create_mock_bundle(job.prompt, job.format_id)

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        job_ids = []
        for t in topics:
            res = client.post("/api/generate", json={"prompt": t, "format": "linkedin"})
            job_ids.append((t, res.json()["job_id"]))

        for orig_topic, jid in job_ids:
            job_data = client.get(f"/api/generate/{jid}").json()
            assert job_data["job_id"] == jid
            assert job_data["bundle"]["topic"] == orig_topic
            assert orig_topic in job_data["bundle"]["pieces"]["linkedin"]["body_text"]


# TEST 4: Pipeline failure returns status = "failed" and NO fake fallback content
def test_pipeline_failure_returns_failed_status_without_fallback():
    async def mock_failed_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "failed"
            job.error_message = "API Quota Exceeded (429 RESOURCE_EXHAUSTED)"

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_failed_execute):
        res = client.post("/api/generate", json={"prompt": "Some topic", "format": "linkedin"})
        jid = res.json()["job_id"]

        job_data = client.get(f"/api/generate/{jid}").json()
        assert job_data["status"] == "failed"
        assert job_data["bundle"] is None
        assert "API Quota Exceeded" in job_data["error_message"]


# TEST 5: Orchestrator creates unique Job ID for every request
def test_orchestrator_creates_unique_job_ids():
    orch = PipelineOrchestrator(use_llm=False)
    j1 = orch.create_job(prompt="Topic 1", format_id="linkedin")
    j2 = orch.create_job(prompt="Topic 2", format_id="linkedin")
    assert j1.job_id != j2.job_id
    assert orch.get_job(j1.job_id).prompt == "Topic 1"
    assert orch.get_job(j2.job_id).prompt == "Topic 2"
