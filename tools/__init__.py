"""External tool integrations and utilities."""

from tools.execution_trace import (
    ExecutionTrace,
    FailureCategory,
    TraceEntry,
    classify_exception,
    get_trace,
    reset_trace,
)
from tools.fetcher import (
    ContentTypeError,
    EmptyContentError,
    FetchError,
    FetchSnapshot,
    FetchTimeoutError,
    HttpFetchError,
    PageFetcher,
)
from tools.llm_client import GeminiClient
from tools.quote_verifier import QuoteVerifier, verify_quote
from tools.search_tool import (
    BaseSearchProvider,
    DuckDuckGoSearchProvider,
    MockSearchProvider,
    SearchCache,
    SearchError,
    SearchProviderError,
    SearchResult,
    SearchTimeoutError,
    SearchTool,
    normalize_url,
)
from tools.source_triage import SourceTriage

__all__ = [
    "BaseSearchProvider",
    "ContentTypeError",
    "DuckDuckGoSearchProvider",
    "EmptyContentError",
    "ExecutionTrace",
    "FailureCategory",
    "FetchError",
    "FetchSnapshot",
    "FetchTimeoutError",
    "GeminiClient",
    "HttpFetchError",
    "MockSearchProvider",
    "PageFetcher",
    "QuoteVerifier",
    "SearchCache",
    "SearchError",
    "SearchProviderError",
    "SearchResult",
    "SearchTimeoutError",
    "SearchTool",
    "SourceTriage",
    "TraceEntry",
    "classify_exception",
    "get_trace",
    "normalize_url",
    "reset_trace",
    "verify_quote",
]
