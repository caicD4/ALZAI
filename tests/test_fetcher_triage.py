import asyncio
import pytest
from tools.fetcher import PageFetcher
from tools.search_tool import SearchResult, SearchTool
from tools.source_triage import SourceTriage


def test_search_tool_query_and_caching():
    tool = SearchTool(cache_ttl_seconds=3600)
    query = "Autonomous AI Agents in Software Engineering"

    results1 = tool.search(query, max_results=3)
    assert isinstance(results1, list)
    assert len(results1) > 0
    assert isinstance(results1[0], SearchResult)

    # Second call should hit cache instantly
    results2 = tool.search(query, max_results=3)
    assert len(results2) == len(results1)
    assert results2[0].url == results1[0].url


def test_source_triage_tier_ranking_and_filtering():
    triage = SourceTriage(max_per_domain=1)

    r1 = SearchResult(
        title="MIT AI Study",
        url="https://sloan.mit.edu/research/ai",
        snippet="MIT study",
        domain="sloan.mit.edu",
    )
    r2 = SearchResult(
        title="Spam Article",
        url="https://promotional-seo-spam.com/cheap-ai",
        snippet="Buy cheap AI",
        domain="promotional-seo-spam.com",
    )
    r3 = SearchResult(
        title="Tech News",
        url="https://techcrunch.com/2024/ai-trends",
        snippet="Tech trends",
        domain="techcrunch.com",
    )
    r4 = SearchResult(
        title="Duplicate Domain",
        url="https://techcrunch.com/2024/another-ai",
        snippet="Another article",
        domain="techcrunch.com",
    )

    ranked = triage.triage_and_rank([r1, r2, r3, r4])

    assert len(ranked) == 2
    assert ranked[0].domain == "sloan.mit.edu"
    assert ranked[1].domain == "techcrunch.com"


def test_page_fetcher_cleaning_and_hashing():
    raw_html = """
    <html>
        <head><title>Test Page</title><style>body { color: red; }</style></head>
        <body>
            <nav><a href="#">Home</a></nav>
            <main>
                <h1>AI Agent Case Study</h1>
                <p>Only 11% of organizations surveyed reported significant ROI from AI projects.</p>
            </main>
            <footer><p>Copyright 2024</p></footer>
            <script>console.log('test');</script>
        </body>
    </html>
    """

    cleaned = PageFetcher.clean_html(raw_html)
    assert "AI Agent Case Study" in cleaned
    assert "11% of organizations" in cleaned
    assert "console.log" not in cleaned
    assert "Copyright 2024" not in cleaned

    fetcher = PageFetcher()

    async def _run():
        return await fetcher.fetch_and_clean(
            "https://invalid-test-domain-xyz.org/page", fallback_title="Test"
        )

    snapshot = asyncio.run(_run())
    assert snapshot.fetch_id.startswith("fetch-")
    assert len(snapshot.content_hash) == 64
    assert snapshot.url == "https://invalid-test-domain-xyz.org/page"
