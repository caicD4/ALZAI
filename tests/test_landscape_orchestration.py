import asyncio
from unittest.mock import patch
from fastapi.testclient import TestClient

from agents.landscape_analyzer import LandscapeAnalyzer
from agents.planner import ResearchPlanner
from app.api import app
from app.orchestrator import PipelineOrchestrator
from core.content_landscape import ContentReference
from core.evidence import FetchSnapshot
from tools.search_tool import MockSearchProvider, SearchTool


def _fake_snapshot(url: str, text: str) -> FetchSnapshot:
    return FetchSnapshot(
        fetch_id=f"fetch-{abs(hash(url) & 0xffffffff):08x}",
        url=url,
        final_url=url,
        title="Fetched page",
        cleaned_text=text,
        content_hash=f"hash-{abs(hash(url) & 0xffffffff):08x}",
    )


def test_landscape_analyzer_offline_flow_never_invents_engagement():
    analyzer = LandscapeAnalyzer(
        use_llm=False,
        search_tool=SearchTool(provider=MockSearchProvider()),
        max_queries=4,
        max_results_per_query=3,
    )
    plan = ResearchPlanner(use_llm=False).create_plan("why sam altman is evil")
    intent = plan.request_intent
    assert intent is not None and intent.intent_type in ("critique", "claim_investigation")

    queries = analyzer.generate_landscape_queries(intent)
    assert any(("criticism" in q or "controversy" in q) for q in queries)

    refs = analyzer.search_landscape(queries)
    assert len(refs) > 0
    # engagement must NEVER be invented in offline fallback search results
    assert all(r.engagement is None for r in refs)
    # dedupe by canonical_url
    urls = [r.url for r in refs]
    assert len(set(urls)) == len(urls)

    landscape = analyzer.analyze(intent, refs)
    assert landscape.reference_ids
    assert landscape.content_gaps
    assert landscape.recommended_differentiation
    assert analyzer.last_analysis_method == "grounded_fallback"


def test_landscape_analyzer_empty_references_returns_gaps_not_gate():
    analyzer = LandscapeAnalyzer(
        use_llm=False,
        search_tool=SearchTool(provider=MockSearchProvider()),
    )
    plan = ResearchPlanner(use_llm=False).create_plan("explain mixture of experts")
    intent = plan.request_intent
    landscape = analyzer.analyze(intent, [])
    assert landscape.reference_ids == []
    assert any("No existing content references" in g for g in landscape.content_gaps)


def test_orchestrator_runs_landscape_and_passes_landscape_into_brief():
    orch = PipelineOrchestrator(use_llm=False)
    job = orch.create_job(prompt="why sam altman is evil", format_id="linkedin")

    async def fake_fetch(url):
        return _fake_snapshot(url, "Sam Altman co-founded OpenAI in 2015 and later returned as CEO after being briefly removed.")

    with (
        patch("app.orchestrator.SearchTool", lambda *a, **k: SearchTool(provider=MockSearchProvider())),
        patch("agents.landscape_analyzer.SearchTool", lambda *a, **k: SearchTool(provider=MockSearchProvider())),
        patch("tools.fetcher.PageFetcher.fetch_and_clean", fake_fetch),
    ):
        asyncio.run(orch.execute_job(job.job_id))

    done = orch.get_job(job.job_id)
    assert done.status == "completed"
    assert done.generation_mode in ("gemini", "fallback", "none")
    assert done.brief_summary is not None
    # landscape research ran and flowed into the brief summary
    assert done.brief_summary["content_landscape"] is not None
    assert done.brief_summary["content_landscape"]["topic"] == "Sam Altman"
    assert "content_gaps" in done.brief_summary
    assert done.brief_summary["angles"]
    assert done.brief_summary["selected_angle"] is not None
    # per-piece honest mode + revision count on the final bundle
    piece = done.bundle.pieces["linkedin"]
    assert piece.generation_mode in ("gemini", "fallback", "none")
    assert piece.revision_count >= 0
    assert piece.body_text  # content always produced (no gate)


def test_api_history_and_trace_endpoints():
    client = TestClient(app)

    history = client.get("/api/history")
    assert history.status_code == 200
    assert "history" in history.json()

    trace_no_trace = client.get(f"/api/generate/{'job-x'}/trace")
    assert trace_no_trace.status_code == 404


def test_api_trace_requires_opt_in():
    client = TestClient(app)

    async def mock_execute(job_id, brand=None, voice=None):
        from app.api import orchestrator
        job = orchestrator.get_job(job_id)
        if job:
            job.status = "completed"

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        resp = client.post("/api/generate", json={"prompt": "why elon musk sucks", "format": "linkedin"})
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

    job = client.get(f"/api/generate/{job_id}")
    assert job.json()["status"] == "completed"

    trace = client.get(f"/api/generate/{job_id}/trace")
    assert trace.status_code == 409  # included in history, trace requires include_trace opt-in

    with patch("app.orchestrator.PipelineOrchestrator.execute_job", side_effect=mock_execute):
        resp2 = client.post("/api/generate", json={
            "prompt": "why elon musk sucks",
            "format": "all",
            "include_trace": True,
        })
        assert resp2.status_code == 200
        job_id2 = resp2.json()["job_id"]
        assert client.get(f"/api/generate/{job_id2}").json()["include_trace"] is True

    # history should list both jobs with health fields
    hist = client.get("/api/history").json()["history"]
    assert any(h["job_id"] == job_id for h in hist)
    assert any(h["job_id"] == job_id2 for h in hist)
    assert all("generation_mode" in h for h in hist)