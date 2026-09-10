import pytest
from tools.search_tool import (
    BaseSearchProvider,
    MockSearchProvider,
    SearchCache,
    SearchProviderError,
    SearchResult,
    SearchTool,
    normalize_url,
)



def test_url_normalization():
    assert normalize_url("HTTPS://EXAMPLE.COM/path/") == "https://example.com/path"
    assert normalize_url("http://domain.org") == "http://domain.org"
    assert normalize_url("") == ""


def test_search_result_model_validation():
    result = SearchResult(
        title="AI Benchmarks",
        url="https://example.com/benchmarks",
        canonical_url="https://example.com/benchmarks",
        snippet="Benchmarking AI agents",
        domain="example.com",
        query="AI benchmarks",
        rank=1,
    )
    assert result.rank == 1
    assert result.query == "AI benchmarks"
    assert result.canonical_url == "https://example.com/benchmarks"


def test_mock_search_provider_query_and_rank_preservation():
    mock_provider = MockSearchProvider()
    query = "Autonomous Coding Agents"
    sample_result = SearchResult(
        title="Coding Agents Study",
        url="https://sloan.mit.edu/paper",
        canonical_url="https://sloan.mit.edu/paper",
        snippet="Study on coding agents",
        domain="sloan.mit.edu",
        query=query,
        rank=1,
    )
    mock_provider.register_results(query, [sample_result])

    results = mock_provider.search(query, max_results=5)
    assert len(results) == 1
    assert results[0].query == query
    assert results[0].rank == 1
    assert results[0].domain == "sloan.mit.edu"


def test_search_cache_behavior():
    cache = SearchCache(ttl_seconds=3600)
    query = "Quantum Computing"
    results = [
        SearchResult(
            title="Quantum Intro",
            url="https://ibm.com/quantum",
            canonical_url="https://ibm.com/quantum",
            snippet="Intro to quantum",
            domain="ibm.com",
            query=query,
            rank=1,
        )
    ]

    assert cache.get(query) is None

    cache.set(query, results)
    # Query normalization check ("  QUANTUM computing  ")
    cached = cache.get("  QUANTUM computing  ")
    assert cached is not None
    assert len(cached) == 1
    assert cached[0].url == "https://ibm.com/quantum"

    cache.clear()
    assert cache.get(query) is None


def test_search_tool_with_mock_provider_and_cache():
    mock_provider = MockSearchProvider()
    cache = SearchCache(ttl_seconds=3600)
    tool = SearchTool(provider=mock_provider, cache=cache)

    query = "AI Safety Evaluation"
    sample_result = SearchResult(
        title="AI Safety Report",
        url="https://arxiv.org/abs/1234.5678",
        canonical_url="https://arxiv.org/abs/1234.5678",
        snippet="Arxiv paper on safety",
        domain="arxiv.org",
        query=query,
        rank=1,
    )
    mock_provider.register_results(query, [sample_result])

    # First call uses provider
    res1 = tool.search(query, max_results=5)
    assert len(res1) == 1
    assert len(mock_provider.recorded_queries) == 1

    # Second call uses cache (recorded_queries count remains 1)
    res2 = tool.search(query, max_results=5)
    assert len(res2) == 1
    assert len(mock_provider.recorded_queries) == 1


def test_search_provider_error_handling():
    class FailingProvider(BaseSearchProvider):
        def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
            raise SearchProviderError("API rate limit exceeded")

    provider = FailingProvider()
    with pytest.raises(SearchProviderError, match="rate limit exceeded"):
        provider.search("test query")

    # SearchTool catches provider errors gracefully and returns empty list without fabricating fake URLs
    tool = SearchTool(provider=provider, cache=None)
    results = tool.search("test query")
    assert results == []


