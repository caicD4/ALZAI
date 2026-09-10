from datetime import date
from core.evidence import EvidenceItem, FetchSnapshot, NumberFact, Source
from tools.search_tool import SearchResult


def test_provenance_chain_transformation_integrity():
    query = "Enterprise AI adoption ROI studies"

    # Step 1: Search Result
    search_result = SearchResult(
        title="MIT Sloan AI ROI Study 2024",
        url="https://sloan.mit.edu/research/ai-roi",
        canonical_url="https://sloan.mit.edu/research/ai-roi",
        snippet="MIT study showing only 11% of surveyed companies achieve high ROI from AI.",
        domain="sloan.mit.edu",
        query=query,
        rank=1,
    )
    assert search_result.query == query
    assert search_result.rank == 1

    # Step 2: Fetch Snapshot
    cleaned_text = (
        "MIT Sloan AI ROI Study 2024\n"
        "According to MIT Sloan research, only 11% of organizations surveyed "
        "reported significant returns from their AI investments."
    )
    content_hash = "a1b2c3d4e5f678901234567890abcdef1234567890abcdef1234567890abcdef"
    fetch_snapshot = FetchSnapshot(
        fetch_id="fetch-a1b2c3d4e5f6",
        url=search_result.url,
        final_url="https://sloan.mit.edu/research/ai-roi",
        title=search_result.title,
        cleaned_text=cleaned_text,
        content_hash=content_hash,
        content_type="text/html",
        http_status=200,
    )
    assert fetch_snapshot.url == search_result.url
    assert fetch_snapshot.fetch_id == "fetch-a1b2c3d4e5f6"

    # Step 3: Source Metadata
    source = Source(
        source_id="src-mit-01",
        url=search_result.url,
        canonical_url=search_result.canonical_url,
        domain=search_result.domain,
        title=search_result.title,
        query=search_result.query,
        serp_rank=search_result.rank,
        published_at=date(2024, 5, 1),
        fetch_id=fetch_snapshot.fetch_id,
        content_hash=fetch_snapshot.content_hash,
        quality_tier=1,
        vested_interest=False,
    )
    assert source.query == search_result.query
    assert source.serp_rank == search_result.rank
    assert source.fetch_id == fetch_snapshot.fetch_id
    assert source.content_hash == fetch_snapshot.content_hash

    # Step 4: Evidence Item
    number_fact = NumberFact(
        value="11%",
        denominator="of organizations surveyed",
        timeframe="2024 survey",
    )
    evidence_item = EvidenceItem(
        evidence_id="E07",
        fetch_id=fetch_snapshot.fetch_id,
        locator="span:28-125",
        verbatim_quote="only 11% of organizations surveyed reported significant returns from their AI investments",
        claim_summary="Only 11% of surveyed companies achieve major ROI from AI.",
        evidence_type="statistic",
        attribution="MIT Sloan AI ROI Study 2024",
        numbers=[number_fact],
        data_date=date(2024, 5, 1),
        quote_verified=True,
    )

    # Verify Provenance Chain Connections
    assert evidence_item.fetch_id == source.fetch_id == fetch_snapshot.fetch_id
    assert source.url == search_result.url
    assert source.content_hash == fetch_snapshot.content_hash
    assert evidence_item.verbatim_quote in fetch_snapshot.cleaned_text
