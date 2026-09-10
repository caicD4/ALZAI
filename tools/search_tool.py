from abc import ABC, abstractmethod
import time
from typing import Dict, List, Optional
from urllib.parse import urlparse, urlunparse
from pydantic import BaseModel, Field


# --- Typed Exceptions ---
class SearchError(Exception):
    """Base exception for search operations."""
    pass


class SearchProviderError(SearchError):
    """Raised when a search provider API encounters an error or fails."""
    pass


class SearchTimeoutError(SearchProviderError):
    """Raised when a search provider request times out."""
    pass


# --- Helper Utilities ---
def normalize_url(url: str) -> str:
    """Normalizes a URL to a canonical format for deduplication."""
    if not url:
        return ""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if not path:
        path = ""
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


# --- Search Result Model ---
class SearchResult(BaseModel):
    """Structured representation of a single search engine result preserving full provenance."""

    title: str = Field(..., description="Title of the search result page")
    url: str = Field(..., description="Original target URL of the page")
    canonical_url: str = Field(..., description="Normalized canonical URL for deduplication")
    snippet: str = Field(..., description="Text snippet / description from search engine")
    domain: str = Field(..., description="Extracted domain name of the URL")
    query: str = Field(..., description="Originating search query that generated this result")
    rank: int = Field(..., ge=1, description="1-indexed rank order in search engine results")


# --- Provider Interface ---
class BaseSearchProvider(ABC):
    """Abstract base class for search providers."""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """Executes a search query and returns structured SearchResult items.

        Raises:
            SearchProviderError: If the search provider fails or encounters an error.
        """
        pass


# --- DuckDuckGo Provider ---
class DuckDuckGoSearchProvider(BaseSearchProvider):
    """Production Search Provider using ddgs."""

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        results = self._execute_ddgs_search(clean_query, max_results)
        
        # If a long query (>4 words) yielded 0 results, retry with top significant terms
        if not results:
            terms = [
                w for w in re.findall(r"\w+", clean_query)
                if len(w) > 2 and w.lower() not in {"what", "how", "why", "the", "for", "and", "with", "about"}
            ]
            if len(terms) > 4:
                simplified_query = " ".join(terms[:4])
                results = self._execute_ddgs_search(simplified_query, max_results)

        return results

    def _execute_ddgs_search(self, query_str: str, max_results: int) -> List[SearchResult]:
        results: List[SearchResult] = []
        try:
            from ddgs import DDGS

            with DDGS() as ddgs:
                ddg_results = list(ddgs.text(query_str, max_results=max_results))
                for rank, item in enumerate(ddg_results, start=1):
                    raw_url = item.get("href", "") or item.get("link", "")
                    if not raw_url:
                        continue
                    canon_url = normalize_url(raw_url)
                    domain = urlparse(raw_url).netloc.lower()
                    results.append(
                        SearchResult(
                            title=item.get("title", "Untitled").strip(),
                            url=raw_url,
                            canonical_url=canon_url,
                            snippet=(item.get("body", "") or item.get("snippet", "")).strip(),
                            domain=domain,
                            query=query_str,
                            rank=rank,
                        )
                    )
        except Exception as err:
            raise SearchProviderError(f"DuckDuckGo search provider failed for query '{query_str}': {err}") from err

        return results


# --- Mock Search Provider (for offline tests & reproducible runs) ---
class MockSearchProvider(BaseSearchProvider):
    """Deterministic Mock Search Provider for testing."""

    def __init__(self, mock_data: Optional[Dict[str, List[SearchResult]]] = None) -> None:
        self.mock_data: Dict[str, List[SearchResult]] = mock_data or {}
        self.recorded_queries: List[str] = []

    def register_results(self, query: str, results: List[SearchResult]) -> None:
        clean_q = query.strip().lower()
        self.mock_data[clean_q] = results

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        clean_q = query.strip().lower()
        self.recorded_queries.append(clean_q)

        if clean_q in self.mock_data:
            results = self.mock_data[clean_q]
            updated_results = []
            for rank, r in enumerate(results[:max_results], start=1):
                updated = r.model_copy(update={"query": query, "rank": rank})
                updated_results.append(updated)
            return updated_results

        return SearchTool.generate_mock_fallback_results(query, max_results)


# --- Search Cache Component ---
class SearchCache:
    """Explicit, testable in-memory TTL search query cache."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, tuple[float, List[SearchResult]]] = {}

    def get(self, query: str) -> Optional[List[SearchResult]]:
        clean_q = query.strip().lower()
        if clean_q in self._store:
            timestamp, results = self._store[clean_q]
            if time.time() - timestamp < self.ttl_seconds:
                return results
            del self._store[clean_q]
        return None

    def set(self, query: str, results: List[SearchResult]) -> None:
        clean_q = query.strip().lower()
        self._store[clean_q] = (time.time(), results)

    def clear(self) -> None:
        self._store.clear()


# --- Main Search Tool Service ---
class SearchTool:
    """High-level Search Tool composing provider execution and caching."""

    def __init__(
        self,
        provider: Optional[BaseSearchProvider] = None,
        cache: Optional[SearchCache] = None,
    ) -> None:
        self.provider = provider or DuckDuckGoSearchProvider()
        self.cache = cache if cache is not None else SearchCache(ttl_seconds=3600)

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        if self.cache is not None:
            cached = self.cache.get(clean_query)
            if cached is not None:
                return cached[:max_results]

        try:
            results = self.provider.search(clean_query, max_results=max_results)
        except Exception:
            # NO ACCIDENTAL FABRICATION: On error, return empty list rather than generating fake URLs
            results = []

        if self.cache is not None and results:
            self.cache.set(clean_query, results)

        return results[:max_results]


    @staticmethod
    def generate_mock_fallback_results(query: str, max_results: int = 5) -> List[SearchResult]:
        """Provides deterministic search results for offline demos & fallback runs."""
        clean_q = query.replace(" ", "_")
        return [
            SearchResult(
                title=f"Research & Benchmark Overview: {query}",
                url=f"https://sloan.mit.edu/research/{clean_q}",
                canonical_url=f"https://sloan.mit.edu/research/{clean_q}",
                snippet=f"Empirical study and research findings regarding {query}.",
                domain="sloan.mit.edu",
                query=query,
                rank=1,
            ),
            SearchResult(
                title=f"Technical Report: {query}",
                url=f"https://techcrunch.com/2024/report/{clean_q}",
                canonical_url=f"https://techcrunch.com/2024/report/{clean_q}",
                snippet=f"Industry analysis and technical architecture overview of {query}.",
                domain="techcrunch.com",
                query=query,
                rank=2,
            ),
            SearchResult(
                title=f"Open Source Implementation and Analysis: {query}",
                url=f"https://github.com/topics/{clean_q}",
                canonical_url=f"https://github.com/topics/{clean_q}",
                snippet=f"Practitioner accounts, repository benchmarks, and code examples for {query}.",
                domain="github.com",
                query=query,
                rank=3,
            ),
        ][:max_results]
