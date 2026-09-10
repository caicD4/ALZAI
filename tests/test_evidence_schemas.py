from datetime import date
import pytest
from pydantic import ValidationError

from core.evidence import (
    ClaimCheck,
    EvidenceItem,
    FetchSnapshot,
    Finding,
    NumberFact,
    Source,
)


def test_source_and_fetch_snapshot_creation():
    snapshot = FetchSnapshot(
        fetch_id="fetch-123",
        url="https://sloan.mit.edu/ai-report",
        cleaned_text="Only 11% of organizations surveyed reported significant returns...",
        content_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    assert snapshot.fetch_id == "fetch-123"
    assert "11%" in snapshot.cleaned_text

    source = Source(
        source_id="src-1",
        url="https://sloan.mit.edu/ai-report",
        domain="sloan.mit.edu",
        title="MIT Sloan AI Investment Study",
        fetch_id=snapshot.fetch_id,
        content_hash=snapshot.content_hash,
        quality_tier=1,
        vested_interest=False,
    )
    assert source.domain == "sloan.mit.edu"
    assert source.quality_tier == 1


def test_evidence_item_with_number_facts():
    number = NumberFact(
        value="11%",
        denominator="of organizations surveyed",
        timeframe="2023 survey",
    )
    evidence = EvidenceItem(
        evidence_id="E07",
        fetch_id="fetch-123",
        locator="span:0-65",
        verbatim_quote="only 11% of organizations surveyed reported significant returns from their AI investments",
        claim_summary="Only 11% of surveyed companies achieve major ROI from AI.",
        evidence_type="statistic",
        numbers=[number],
        quote_verified=True,
    )
    assert evidence.evidence_id == "E07"
    assert evidence.quote_verified is True
    assert len(evidence.numbers) == 1
    assert evidence.numbers[0].value == "11%"


def test_finding_and_claim_check_models():
    finding = Finding(
        finding_id="F01",
        sub_question_id="rq-1",
        statement="Most enterprise AI projects struggle to achieve ROI.",
        evidence_ids=["E07", "E19"],
        status="contested",
    )
    assert finding.finding_id == "F01"
    assert finding.status == "contested"

    claim_check = ClaimCheck(
        claim="Over 80% of enterprise AI projects fail.",
        claim_type="factual",
        verdict="partial",
        evidence_ids=["E07"],
        note="Claim is exaggerated compared to survey data showing 11% high ROI.",
    )
    assert claim_check.verdict == "partial"
    assert claim_check.claim_type == "factual"
