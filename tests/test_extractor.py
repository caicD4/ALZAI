import json
from unittest.mock import MagicMock
import pytest

from agents.extractor import DocumentChunker, EvidenceExtractor
from core.evidence import EvidenceItem, FetchSnapshot, NumberFact
from core.research_plan import ResearchQuestion
from tools.llm_client import GeminiClient


# --- Fixtures ---
@pytest.fixture
def sample_question():
    return ResearchQuestion(
        id="rq-1",
        question="What is the failure rate of enterprise AI projects?",
        rationale="Assess industry AI adoption risks and success benchmarks.",
        priority=1,
        search_queries=["enterprise AI project failure rate benchmarks"],
    )


@pytest.fixture
def sample_snapshot():
    text = (
        "According to a 2023 survey by Gartner, 70-85% of enterprise AI projects fail "
        "to deliver on their initial business objectives. The primary causes cited include "
        "poor data quality and lack of executive alignment. Additionally, OpenAI reported "
        "that smaller specialized models achieve 95% accuracy compared to generic LLMs."
    )
    return FetchSnapshot(
        fetch_id="fetch-test-12345",
        url="https://example.com/ai-report",
        final_url="https://example.com/ai-report",
        title="AI Adoption & Failure Analysis",
        cleaned_text=text,
        content_hash="hash-12345",
    )


# --- 1. Valid Structured Gemini Response Produces EvidenceItems ---
def test_valid_gemini_response_produces_evidence_items(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "70-85% of enterprise AI projects fail to deliver on their initial business objectives.",
                    "claim_summary": "70-85% of enterprise AI projects fail.",
                    "relevance_explanation": "Directly states failure rate metric for enterprise AI projects.",
                    "evidence_type": "statistic",
                    "attribution": "Gartner 2023 survey",
                    "numbers": [
                        {
                            "value": "70-85%",
                            "unit": "projects",
                            "denominator": "enterprise AI projects",
                            "timeframe": "2023 survey",
                            "sample": "surveyed enterprises",
                        }
                    ],
                    "data_date": "2023-01-01",
                }
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert isinstance(item, EvidenceItem)
    assert item.quote_verified is True
    assert item.fetch_id == sample_snapshot.fetch_id
    assert "70-85%" in item.verbatim_quote
    assert item.evidence_type == "statistic"


# --- 1b. LLM Failure Degrades to Deterministic Evidence Extraction (no silent starvation) ---
def test_llm_failure_falls_back_to_deterministic_extraction(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.side_effect = RuntimeError("429 RESOURCE_EXHAUSTED: Gemini quota exceeded")

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) >= 1, "LLM failure must not silently starve the evidence pipeline"
    for item in results:
        assert item.quote_verified is True
        assert item.verbatim_quote in sample_snapshot.cleaned_text
        assert "70-85%" in item.verbatim_quote


# --- 2. Exact Quote Passes Verification ---
def test_exact_quote_passes_verification(sample_snapshot, sample_question):
    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) >= 1
    for item in results:
        assert item.quote_verified is True
        assert item.verbatim_quote in sample_snapshot.cleaned_text


# --- 3. Whitespace & Case-Normalized Quote Passes Verification ---
def test_normalized_quote_passes_verification(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "According to a 2023 survey by gartner, 70-85%  of enterprise AI projects fail",
                    "claim_summary": "High AI failure rate reported by Gartner",
                    "relevance_explanation": "Reports Gartner AI failure rate statistics.",
                    "evidence_type": "statistic",
                    "attribution": "Gartner",
                }
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 1
    assert results[0].quote_verified is True


# --- 4. Fabricated Quote is Rejected ---
def test_fabricated_quote_is_rejected(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "100% of all software projects succeed instantly without any bugs.",
                    "claim_summary": "All projects succeed.",
                    "relevance_explanation": "Claims 100% success rate.",
                    "evidence_type": "statistic",
                }
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 0


# --- 5. Multiple Evidence Items Handled Correctly ---
def test_multiple_evidence_items_handled(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "70-85% of enterprise AI projects fail to deliver on their initial business objectives.",
                    "claim_summary": "70-85% failure rate for enterprise AI.",
                    "relevance_explanation": "Failure rate statistic for enterprise AI.",
                    "evidence_type": "statistic",
                    "attribution": "Gartner",
                },
                {
                    "verbatim_quote": "smaller specialized models achieve 95% accuracy compared to generic LLMs.",
                    "claim_summary": "Specialized models achieve 95% accuracy.",
                    "relevance_explanation": "Model accuracy benchmark for specialized models.",
                    "evidence_type": "statistic",
                    "attribution": "OpenAI",
                },
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 2
    assert all(r.quote_verified for r in results)
    quotes = [r.verbatim_quote for r in results]
    assert any("70-85%" in q for q in quotes)
    assert any("95% accuracy" in q for q in quotes)


# --- 6. NumberFact Extraction is Preserved ---
def test_number_fact_extraction_preserved(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "smaller specialized models achieve 95% accuracy compared to generic LLMs.",
                    "claim_summary": "95% accuracy for specialized models.",
                    "relevance_explanation": "Provides quantitative accuracy benchmark.",
                    "evidence_type": "statistic",
                    "numbers": [
                        {
                            "value": "95%",
                            "unit": "accuracy",
                            "denominator": "compared to generic LLMs",
                            "timeframe": None,
                            "sample": "specialized models",
                        }
                    ],
                }
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 1
    assert len(results[0].numbers) == 1
    nf = results[0].numbers[0]
    assert isinstance(nf, NumberFact)
    assert nf.value == "95%"
    assert nf.unit == "accuracy"


# --- 7. Attribution is Preserved ---
def test_attribution_preserved(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "smaller specialized models achieve 95% accuracy compared to generic LLMs.",
                    "claim_summary": "OpenAI accuracy benchmark report.",
                    "relevance_explanation": "Reports OpenAI study on specialized model accuracy.",
                    "evidence_type": "expert_opinion",
                    "attribution": "OpenAI report",
                }
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) == 1
    assert results[0].attribution == "OpenAI report"


# --- 8. Malformed Gemini Output Falls Back to Deterministic Extraction ---
def test_malformed_gemini_output_falls_back(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = "INVALID_NON_JSON_TEXT_RESPONSE"

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) >= 1
    assert all(r.quote_verified for r in results)
    assert all(r.verbatim_quote in sample_snapshot.cleaned_text for r in results)


# --- 9. Gemini/API Failure Falls Back to Deterministic Extraction ---
def test_gemini_api_failure_falls_back(sample_snapshot, sample_question):
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.side_effect = RuntimeError("API connection timeout")

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) >= 1
    assert all(r.quote_verified for r in results)
    assert all(r.verbatim_quote in sample_snapshot.cleaned_text for r in results)


# --- 10. Empty Source Produces No Fabricated Evidence ---
def test_empty_source_produces_no_evidence(sample_question):
    empty_snapshot = FetchSnapshot(
        fetch_id="fetch-empty",
        url="https://example.com/empty",
        cleaned_text="   ",
        content_hash="empty",
    )

    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(empty_snapshot, sample_question)

    assert results == []


# --- 11. Long-Source Chunking & Cross-Chunk Deduplication Works ---
def test_long_source_chunking_and_deduplication(sample_question):
    chunker = DocumentChunker(max_chunk_size=100, chunk_overlap=20)
    long_text = "Sentence one is long and detailed. " * 15
    long_snapshot = FetchSnapshot(
        fetch_id="fetch-long",
        url="https://example.com/long",
        cleaned_text=long_text,
        content_hash="long-hash",
    )
    extractor = EvidenceExtractor(use_llm=False, chunker=chunker)
    results = extractor.extract_evidence(long_snapshot, sample_question)
    assert isinstance(results, list)

    # Ensure no duplicate quotes exist in output pool
    seen_quotes = set()
    for item in results:
        norm_q = item.verbatim_quote.strip().lower()
        assert norm_q not in seen_quotes
        seen_quotes.add(norm_q)


# --- 12. Boilerplate Quotes are Rejected even if Grounded in Text ---
def test_boilerplate_quote_is_rejected_despite_groundedness(sample_question):
    text = (
        "The .gov means it's official. Federal government websites often end in .gov or .mil. "
        "Before sharing sensitive information, make sure you're on a federal government site. "
        "According to Gartner 2023, 70-85% of enterprise AI projects fail to deliver on business objectives. "
        "Skip to main content. Download PDF."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-boilerplate-test",
        url="https://example.gov/report",
        cleaned_text=text,
        content_hash="hash-boilerplate",
    )

    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "The .gov means it's official.",
                    "claim_summary": "Official site notice",
                    "relevance_explanation": "General site notice",
                    "evidence_type": "causal_claim",
                },
                {
                    "verbatim_quote": "Skip to main content.",
                    "claim_summary": "Navigation bar link",
                    "relevance_explanation": "Site UI element",
                    "evidence_type": "promotional",
                },
                {
                    "verbatim_quote": "70-85% of enterprise AI projects fail to deliver on business objectives.",
                    "claim_summary": "70-85% failure rate for enterprise AI.",
                    "relevance_explanation": "Directly reports failure rate statistic for enterprise AI projects.",
                    "evidence_type": "statistic",
                },
            ]
        }
    )

    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    # Boilerplate quotes like ".gov means it's official" must be rejected despite passing QuoteVerifier
    assert len(results) == 1
    assert "70-85%" in results[0].verbatim_quote
    assert ".gov" not in results[0].verbatim_quote


# --- 13. Irrelevant Text Returns Zero Evidence Items ---
def test_zero_relevant_evidence_returns_empty_list():
    question = ResearchQuestion(
        id="rq-2",
        question="What structural neuroplastic mechanisms underlie adult fluid intelligence?",
        rationale="Examine frontoparietal network rewiring and neurogenesis.",
        priority=1,
        search_queries=["neuroplasticity fluid intelligence adult brain"],
    )
    text = (
        "Instructions for baking chocolate cake: Pre-heat oven to 350F. Mix flour, cocoa powder, and sugar in a bowl. "
        "Bake for 30 minutes until a toothpick inserted in the center comes out clean."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-recipe",
        url="https://example.com/recipe",
        cleaned_text=text,
        content_hash="hash-recipe",
    )

    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(snapshot, question)

    # Completely irrelevant text produces zero evidence items
    assert results == []


# --- 14. Exact Character Locators in Cleaned Text ---
def test_exact_character_locator_in_cleaned_text(sample_snapshot, sample_question):
    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(sample_snapshot, sample_question)

    assert len(results) >= 1
    item = results[0]
    assert item.locator.startswith("span:")
    
    # Extract start and end offsets from locator string
    offsets = item.locator.replace("span:", "").split("-")
    start, end = int(offsets[0]), int(offsets[1])
    
    # Assert character slice in snapshot.cleaned_text matches verbatim_quote
    assert sample_snapshot.cleaned_text[start:end] == item.verbatim_quote
