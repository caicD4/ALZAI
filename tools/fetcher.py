import hashlib
import re
from typing import Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

from core.evidence import FetchSnapshot


# --- Typed Exceptions ---
class FetchError(Exception):
    """Base exception for page fetching failures."""

    def __init__(self, message: str, url: str) -> None:
        super().__init__(message)
        self.url = url


class FetchTimeoutError(FetchError):
    """Raised when an HTTP fetch times out."""
    pass


class HttpFetchError(FetchError):
    """Raised when an HTTP response returns a 4xx or 5xx status code."""

    def __init__(self, message: str, url: str, status_code: int) -> None:
        super().__init__(message, url)
        self.status_code = status_code


class ContentTypeError(FetchError):
    """Raised when the fetched response content-type is unsupported (e.g. binary, images)."""

    def __init__(self, message: str, url: str, content_type: str) -> None:
        super().__init__(message, url)
        self.content_type = content_type


class EmptyContentError(FetchError):
    """Raised when the fetched page content is empty or contains no readable text."""
    pass


# Supported MIME types for text extraction
SUPPORTED_CONTENT_TYPES = {
    "text/html",
    "text/plain",
    "application/xhtml+xml",
    "application/xml",
    "text/xml",
}


class PageFetcher:
    """Production Page Fetcher and HTML Content Normalizer.

    Fetches web documents via HTTP, tracks redirects, validates content-types,
    extracts main article text and titles, computes SHA-256 content hashes, and returns immutable FetchSnapshot objects.
    Does NOT fabricate synthetic fallback content on failure.
    """

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }

    async def fetch_and_clean(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> FetchSnapshot:
        """Fetches page content from url, cleans HTML text, and returns FetchSnapshot.

        Args:
            url: Target URL to fetch.
            client: Optional httpx.AsyncClient instance for connection pooling / mocking.

        Returns:
            Validated FetchSnapshot object.

        Raises:
            FetchTimeoutError: On HTTP request timeout.
            HttpFetchError: On 4xx or 5xx HTTP response codes.
            ContentTypeError: On unsupported non-text MIME types.
            EmptyContentError: On empty or unparseable HTML text.
            FetchError: On network or connection failures.
        """
        clean_url = url.strip()
        if not clean_url:
            raise FetchError("Cannot fetch an empty URL", url="")

        should_close = False
        if client is None:
            client = httpx.AsyncClient(timeout=self.timeout_seconds, follow_redirects=True)
            should_close = True

        try:
            try:
                response = await client.get(clean_url, headers=self.headers)
            except httpx.TimeoutException as e:
                raise FetchTimeoutError(f"HTTP request timed out after {self.timeout_seconds}s for URL '{clean_url}'", url=clean_url) from e
            except httpx.HTTPError as e:
                raise FetchError(f"Network failure connecting to URL '{clean_url}': {e}", url=clean_url) from e

            # Validate HTTP status
            if response.status_code >= 400:
                raise HttpFetchError(
                    f"HTTP {response.status_code} error fetching URL '{clean_url}'",
                    url=clean_url,
                    status_code=response.status_code,
                )

            # Validate Content-Type
            raw_content_type = response.headers.get("content-type", "text/html").lower()
            content_type = raw_content_type.split(";")[0].strip()
            if content_type not in SUPPORTED_CONTENT_TYPES and not content_type.startswith("text/"):
                raise ContentTypeError(
                    f"Unsupported content-type '{content_type}' for URL '{clean_url}'",
                    url=clean_url,
                    content_type=content_type,
                )

            html_text = response.text
            if not html_text or not html_text.strip():
                raise EmptyContentError(f"Page response was empty for URL '{clean_url}'", url=clean_url)

            # Extract Title and Clean Text
            title, cleaned_text = self.extract_title_and_clean_text(html_text)
            if not cleaned_text or not cleaned_text.strip():
                raise EmptyContentError(f"No readable text remaining after cleaning page HTML for URL '{clean_url}'", url=clean_url)

            final_url = str(response.url)
            content_hash = hashlib.sha256(cleaned_text.encode("utf-8")).hexdigest()
            fetch_id = f"fetch-{content_hash[:12]}"

            return FetchSnapshot(
                fetch_id=fetch_id,
                url=clean_url,
                final_url=final_url,
                title=title,
                cleaned_text=cleaned_text,
                content_hash=content_hash,
                content_type=content_type,
                http_status=response.status_code,
            )
        finally:
            if should_close:
                await client.aclose()

    @classmethod
    def extract_title_and_clean_text(cls, html_content: str) -> tuple[Optional[str], str]:
        """Extracts page title and cleans HTML body text.

        Returns:
            Tuple of (extracted_title, cleaned_text_content).
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Extract Title
        title: Optional[str] = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        elif soup.find("meta", property="og:title"):
            og_tag = soup.find("meta", property="og:title")
            if og_tag and og_tag.get("content"):
                title = str(og_tag.get("content")).strip()
        elif soup.h1:
            title = soup.h1.get_text().strip()

        # 2. Decompose Boilerplate & Non-Content Elements
        for element in soup([
            "script", "style", "nav", "footer", "header",
            "aside", "form", "iframe", "noscript", "svg",
        ]):
            element.decompose()

        # 3. Prefer Main Article / Container if available
        content_container = soup.find("main") or soup.find("article") or soup.body or soup

        # 4. Extract Text
        text = content_container.get_text(separator=" ")

        # 5. Clean Whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        cleaned = "\n".join(chunk for chunk in chunks if chunk)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return title, cleaned.strip()
