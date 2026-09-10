import json
from unittest.mock import MagicMock
import pytest

from agents.extractor import EvidenceExtractor
from core.evidence import EvidenceItem, FetchSnapshot, ResearchInsight
from core.research_plan import ResearchQuestion
from tools.llm_client import GeminiClient


@pytest.fixture
def sample_question():
    return ResearchQuestion(
        id="rq-insight-1",
        question="How does neuroplasticity facilitate cognitive adaptation in adult brain training?",
        rationale="Understand mechanisms of adult brain plasticity during adaptive training.",
        priority=1,
        search_queries=["neuroplasticity adult brain cognitive adaptation"],
    )


# 1. Useful research finding is accepted
def test_useful_research_finding_accepted(sample_question):
    text = (
        "In a controlled neuroplasticity study of adult brain training, "
        "researchers observed that adult brains demonstrate structural neuroplasticity "
        "during intensive cognitive adaptation training tasks."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-rf-1",
        url="https://journalofneuroscience.org/study-1",
        cleaned_text=text,
        content_hash="hash-rf-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "researchers observed that adult brains demonstrate structural neuroplasticity during intensive cognitive adaptation training tasks.",
                    "claim_summary": "Adult brains show structural neuroplasticity in cognitive training.",
                    "relevance_explanation": "Directly demonstrates neuroplastic mechanism.",
                    "insight_type": "research_finding",
                    "source_role": "evidence",
                    "attribution": "Journal of Neuroscience Study",
                    "suggested_writer_phrasing": "Researchers observed structural neuroplasticity in adult brains during cognitive adaptation training.",
                    "is_substantive": True,
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert item.insight_type == "research_finding"
    assert item.source_role == "evidence"
    assert item.quote_verified is True


# 2. Statistic is accepted and numbers are preserved
def test_statistic_accepted_and_numbers_preserved(sample_question):
    text = (
        "In an adult brain cognitive training study, neuroscientists reported a 28% increase "
        "in synaptic density among participants after 6 weeks of adaptive training."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-stat-1",
        url="https://example.org/stats",
        cleaned_text=text,
        content_hash="hash-stat-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "neuroscientists reported a 28% increase in synaptic density among participants after 6 weeks of adaptive training.",
                    "claim_summary": "28% increase in synaptic density after adaptive training.",
                    "relevance_explanation": "Provides quantitative neuroplasticity metric.",
                    "insight_type": "statistic",
                    "source_role": "evidence",
                    "attribution": "Neuroscientists report",
                    "suggested_writer_phrasing": "Studies report a 28% increase in synaptic density following adaptive training.",
                    "numbers": [
                        {
                            "value": "28%",
                            "unit": "synaptic density increase",
                            "timeframe": "6 weeks",
                            "sample": "study participants",
                        }
                    ],
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert item.insight_type == "statistic"
    assert len(item.numbers) == 1
    assert item.numbers[0].value == "28%"


# 3. Expert claim preserves attribution
def test_expert_claim_preserves_attribution(sample_question):
    text = (
        "Regarding adult brain cognitive adaptation, Dr. Eleanor Vance, lead neuroscientist at Oxford, "
        "argues that relational skill acquisition rewires executive control networks."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-expert-1",
        url="https://oxford.edu/vance-quote",
        cleaned_text=text,
        content_hash="hash-exp-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "Dr. Eleanor Vance, lead neuroscientist at Oxford, argues that relational skill acquisition rewires executive control networks.",
                    "claim_summary": "Relational skills rewire executive control networks.",
                    "relevance_explanation": "Expert opinion on neural rewiring mechanism.",
                    "insight_type": "expert_claim",
                    "source_role": "expert_perspective",
                    "attribution": "Dr. Eleanor Vance (Oxford)",
                    "suggested_writer_phrasing": "Dr. Eleanor Vance of Oxford argues that relational skill acquisition rewires executive control networks.",
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert item.attribution == "Dr. Eleanor Vance (Oxford)"
    assert item.insight_type == "expert_claim"
    assert "Dr. Eleanor Vance" in item.suggested_writer_phrasing


# 4. Company claim remains a company claim
def test_company_claim_remains_company_claim(sample_question):
    text = (
        "Evaluating adult brain cognitive training programs, Cognitive Corp claims "
        "its software increases mental agility by 45% in 30 days."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-comp-1",
        url="https://cognitivecorp.com/press",
        cleaned_text=text,
        content_hash="hash-comp-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "Cognitive Corp claims its software increases mental agility by 45% in 30 days.",
                    "claim_summary": "Company vendor claim of 45% agility increase.",
                    "relevance_explanation": "Vendor marketing claim regarding training outcomes.",
                    "insight_type": "company_claim",
                    "source_role": "company_claim",
                    "attribution": "Cognitive Corp press release",
                    "suggested_writer_phrasing": "Cognitive Corp claims its software increases mental agility by up to 45%.",
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert item.insight_type == "company_claim"
    assert item.source_role == "company_claim"
    assert "claims" in item.suggested_writer_phrasing.lower()


# 5. Anecdote remains anecdotal
def test_anecdote_remains_anecdotal(sample_question):
    text = (
        "In an adult cognitive training trial, one 42-year-old participant noted "
        "that after completing 40 sessions, solving complex work problems felt noticeably faster."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-anec-1",
        url="https://case-studies.org/subject-42",
        cleaned_text=text,
        content_hash="hash-anec-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "In an adult cognitive training trial, one 42-year-old participant noted that after completing 40 sessions, solving complex work problems felt noticeably faster.",
                    "claim_summary": "User self-report of improved problem-solving speed in cognitive training.",
                    "relevance_explanation": "Subjective user anecdote during adult cognitive training.",
                    "insight_type": "anecdote",
                    "source_role": "anecdotal",
                    "attribution": "Study participant self-report",
                    "suggested_writer_phrasing": "Some participants report subjective improvements in problem-solving speed after training.",
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert item.insight_type == "anecdote"
    assert item.source_role == "anecdotal"


# 6. Generic rhetorical introduction is rejected
def test_generic_rhetorical_intro_rejected(sample_question):
    text = "In today's rapidly changing world, everyone wants to unlock their full potential and dive into brain optimization."
    snapshot = FetchSnapshot(
        fetch_id="fetch-fluff-1",
        url="https://seo-blog.com/post-1",
        cleaned_text=text,
        content_hash="hash-fluff-1",
    )
    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(snapshot, sample_question)
    assert len(results) == 0


# 7. Grounded-but-useless passage (Neurolaunch regression test) is rejected
def test_neurolaunch_grounded_fluff_rejected(sample_question):
    text = (
        "Elevate your mind: Discover the scientifically-backed strategies to boost your IQ today! "
        "Welcome to our guide on cognitive development. Click here to learn more!"
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-neurolaunch-fluff",
        url="https://neurolaunch.com/article",
        cleaned_text=text,
        content_hash="hash-neurolaunch",
    )
    extractor = EvidenceExtractor(use_llm=False)
    results = extractor.extract_evidence(snapshot, sample_question)
    assert len(results) == 0


# 8. Relevant semantic passage with low literal keyword overlap is accepted
def test_semantic_relevance_low_keyword_overlap(sample_question):
    # Text uses synonyms: "synaptic remodeling" instead of "neuroplasticity", "working memory adaptation"
    text = (
        "In adult brain training experiments, experimental observations confirm "
        "synaptic remodeling and dendritic growth when subjects engage in continuous difficulty-scaled working memory adaptation tasks."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-synonym-1",
        url="https://nature.com/synaptic-remodeling",
        cleaned_text=text,
        content_hash="hash-synonym-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "experimental observations confirm synaptic remodeling and dendritic growth when subjects engage in continuous difficulty-scaled working memory adaptation tasks.",
                    "claim_summary": "Difficulty-scaled working memory tasks trigger synaptic remodeling and dendritic growth.",
                    "relevance_explanation": "Explains underlying cellular mechanism of neuroplastic adaptation.",
                    "insight_type": "mechanism",
                    "source_role": "evidence",
                    "attribution": "Nature neuroscience research paper",
                    "suggested_writer_phrasing": "Observations show that difficulty-scaled working memory tasks promote synaptic remodeling.",
                    "is_substantive": True,
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    assert results[0].insight_type == "mechanism"


# 9. Claim wording does not become stronger than source
def test_claim_phrasing_preserves_epistemic_level(sample_question):
    text = (
        "Studying adult brain cognitive adaptation, the authors hypothesize that "
        "relational training might correlate with broader fluid intelligence markers in young adults."
    )
    snapshot = FetchSnapshot(
        fetch_id="fetch-hypo-1",
        url="https://example.edu/paper",
        cleaned_text=text,
        content_hash="hash-hypo-1",
    )
    mock_llm = MagicMock(spec=GeminiClient)
    mock_llm.generate_json.return_value = json.dumps(
        {
            "items": [
                {
                    "verbatim_quote": "the authors hypothesize that relational training might correlate with broader fluid intelligence markers in young adults.",
                    "claim_summary": "Authors hypothesize possible correlation between relational training and fluid intelligence.",
                    "relevance_explanation": "Hypothesis regarding relational training outcomes.",
                    "insight_type": "opinion",
                    "source_role": "context",
                    "attribution": "Study authors",
                    "suggested_writer_phrasing": "The authors hypothesize a potential link between relational training and fluid intelligence markers.",
                    "limitations": "Hypothesis only; requires empirical replication.",
                }
            ]
        }
    )
    extractor = EvidenceExtractor(llm_client=mock_llm, use_llm=True)
    results = extractor.extract_evidence(snapshot, sample_question)

    assert len(results) == 1
    item = results[0]
    assert "hypothesize" in item.suggested_writer_phrasing.lower()
    assert item.limitations is not None
