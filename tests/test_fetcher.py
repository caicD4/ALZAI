import asyncio
import hashlib
import httpx
import pytest

from core.evidence import FetchSnapshot
from tools.fetcher import (
    ContentTypeError,
    EmptyContentError,
    FetchError,
    FetchTimeoutError,
    HttpFetchError,
    PageFetcher,
)


def test_clean_html_boilerplate_removal_and_title_extraction():
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>   Empirical AI ROI Study 2024   </title>
            <style>body { font-family: sans-serif; }</style>
            <script>window.analytics = {};</script>
        </head>
        <body>
            <header><nav><a href="/">Home Menu</a></nav></header>
            <main>
                <h1>Empirical AI ROI Study 2024</h1>
                <p>Only 11% of organizations surveyed reported significant ROI from enterprise AI investments.</p>
                <p>Post-mortems indicate process complexity was the primary bottleneck.</p>
            </main>
            <footer><p>Copyright 2024 All Rights Reserved</p></footer>
        </body>
    </html>
    """

    title, cleaned = PageFetcher.extract_title_and_clean_text(html_content)

    assert title == "Empirical AI ROI Study 2024"
    assert "Empirical AI ROI Study 2024" in cleaned
    assert "Only 11% of organizations surveyed" in cleaned
    assert "primary bottleneck" in cleaned
    assert "window.analytics" not in cleaned
    assert "font-family" not in cleaned
    assert "Home Menu" not in cleaned
    assert "Copyright 2024" not in cleaned


def test_sha256_hash_stability_and_sensitivity():
    text1 = "Only 11% of surveyed companies report AI ROI."
    text2 = "Only 11% of surveyed companies report AI ROI."
    text3 = "Only 12% of surveyed companies report AI ROI."

    hash1 = hashlib.sha256(text1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(text2.encode("utf-8")).hexdigest()
    hash3 = hashlib.sha256(text3.encode("utf-8")).hexdigest()

    # Stability
    assert hash1 == hash2
    # Sensitivity
    assert hash1 != hash3


def test_fetch_and_clean_success_with_mock_transport():
    target_url = "https://sloan.mit.edu/research/ai-roi"
    sample_html = "<html><head><title>MIT Research</title></head><body><main><p>Valid research text snippet.</p></main></body></html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            text=sample_html,
            headers={"content-type": "text/html; charset=utf-8"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = PageFetcher()

    async def _run():
        return await fetcher.fetch_and_clean(target_url, client=client)

    snapshot = asyncio.run(_run())

    assert isinstance(snapshot, FetchSnapshot)
    assert snapshot.url == target_url
    assert snapshot.final_url == target_url
    assert snapshot.title == "MIT Research"
    assert snapshot.cleaned_text == "Valid research text snippet."
    assert snapshot.http_status == 200
    assert snapshot.content_type == "text/html"
    assert snapshot.fetch_id.startswith("fetch-")



def test_fetch_and_clean_redirect_tracking():
    initial_url = "http://short.url/link"
    final_destination = "https://sloan.mit.edu/final-article"

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == initial_url:
            return httpx.Response(301, headers={"location": final_destination})
        return httpx.Response(200, text="<html><head><title>Final Page</title></head><body><p>Destination content.</p></body></html>")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport, follow_redirects=True)
    fetcher = PageFetcher()

    async def _run():
        return await fetcher.fetch_and_clean(initial_url, client=client)

    snapshot = asyncio.run(_run())
    assert snapshot.url == initial_url
    assert snapshot.final_url == final_destination
    assert snapshot.title == "Final Page"


def test_fetch_http_404_error_raises_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = PageFetcher()

    async def _run():
        await fetcher.fetch_and_clean("https://example.com/missing", client=client)

    with pytest.raises(HttpFetchError) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.status_code == 404
    assert exc_info.value.url == "https://example.com/missing"


def test_fetch_unsupported_content_type_raises_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "image/png"}, content=b"\x89PNG")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = PageFetcher()

    async def _run():
        await fetcher.fetch_and_clean("https://example.com/image.png", client=client)

    with pytest.raises(ContentTypeError) as exc_info:
        asyncio.run(_run())

    assert exc_info.value.content_type == "image/png"


def test_fetch_empty_content_raises_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="   \n   ")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = PageFetcher()

    async def _run():
        await fetcher.fetch_and_clean("https://example.com/empty", client=client)

    with pytest.raises(EmptyContentError):
        asyncio.run(_run())


def test_fetch_timeout_raises_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("Connection timed out")

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = PageFetcher()

    async def _run():
        await fetcher.fetch_and_clean("https://example.com/slow", client=client)

    with pytest.raises(FetchTimeoutError):
        asyncio.run(_run())
