import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.api import app
from core.bundle_schemas import ContentBundle, ContentPiece
from core.synthesis import ContentStrategy, ContentAngle, ClaimMap, ClaimMapEntry
from core.quality_schemas import ContentQualityReport
from app.orchestrator import GenerationJob

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "ALZAI" in data["service"]

def test_formats_endpoint():
    response = client.get("/api/formats")
    assert response.status_code == 200
    data = response.json()
    assert "formats" in data
    assert len(data["formats"]) > 0
    assert "supported_ids" in data
    assert "all" in data["supported_ids"]
    assert "linkedin" in data["supported_ids"]
    assert "x_thread" in data["supported_ids"]

def test_generate_invalid_format():
    response = client.post("/api/generate", json={"prompt": "test prompt", "format": "invalid_format"})
    assert response.status_code == 400
    assert "Unsupported format" in response.json()["detail"]

def test_generate_empty_prompt():
    response = client.post("/api/generate", json={"prompt": "a", "format": "linkedin"})
    # Pydantic min_length=3 validation fails with 422
    assert response.status_code == 422

def test_get_nonexistent_job():
    response = client.get("/api/generate/nonexistent-id")
    assert response.status_code == 404

def test_generate_job_lifecycle():
    mock_angle = ContentAngle(
        angle_id="angle_1",
        angle_title="Title",
        central_thesis="Thesis",
        why_interesting="Why",
        intended_audience="Audience",
        suitable_platform="LinkedIn"
    )

    mock_claim_map = ClaimMap(
        safe_claims=[ClaimMapEntry(claim_text="Claim 1", category="safe", reasoning="Reason")],
    )

    mock_strategy = ContentStrategy(
        topic="Neuroplasticity",
        content_type="linkedin_post",
        platform="LinkedIn",
        audience="General",
        objective="Educate",
        selected_angle=mock_angle,
        thesis="Neuroplasticity is real.",
        hook_direction="Did you know?",
        key_points=["Point 1"],
        claims_to_include=["Claim 1"],
        claims_to_avoid=[],
        evidence_to_reference=["Evidence 1"],
        counterpoints=["Counterpoint 1"],
        desired_takeaway="Brain is adaptable.",
        claim_map=mock_claim_map
    )

    mock_piece = ContentPiece(
        content_id="piece_1",
        format_id="linkedin",
        platform="LinkedIn",
        title="Post Title",
        body_text="Mock LinkedIn post content for neuroplasticity.",
        sections=["Mock LinkedIn post content for neuroplasticity."],
        word_count=10,
        estimated_duration="30s",
        quality_report=ContentQualityReport(
            report_id="report_1",
            draft_id="draft_1",
            overall_status="passed",
            overall_score=0.95,
            research_fidelity_score=1.0,
            content_quality_score=0.9,
            voice_alignment_score=1.0,
            platform_fit_score=1.0,
            summary_assessment="Excellent quality."
        )
    )

    mock_bundle = ContentBundle(
        bundle_id="bundle_1",
        brief_id="brief_1",
        topic="Neuroplasticity",
        source_strategy=mock_strategy,
        pieces={"linkedin": mock_piece},
        created_at=datetime.now()
    )

    async def mock_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "completed"
            job.bundle = mock_bundle

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        response = client.post("/api/generate", json={
            "prompt": "write me a post on neuroplasticity",
            "format": "linkedin"
        })
        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["job_id"]
        assert job_id is not None

        res = client.get(f"/api/generate/{job_id}")
        data = res.json()
        assert data["status"] == "completed"
        assert data["bundle"] is not None
        assert data["bundle"]["topic"] == "Neuroplasticity"
        assert "linkedin" in data["bundle"]["pieces"]
