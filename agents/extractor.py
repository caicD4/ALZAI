import hashlib
import json
import re
import uuid
from datetime import date
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

from core.evidence import EvidenceItem, FetchSnapshot, NumberFact
from core.research_plan import ResearchQuestion
from tools.llm_client import GeminiClient
from tools.quote_verifier import QuoteVerifier

# --- Boilerplate and Fluff Patterns to Reject ---
BOILERPLATE_PATTERNS = [
    r"\.gov\b",
    r"\bofficial website\b",
    r"\bdownload pdf\b",
    r"\bskip to main content\b",
    r"\bterms of use\b",
    r"\bprivacy policy\b",
    r"\bcookie\b",
    r"\btable of contents\b",
    r"\ball rights reserved\b",
    r"\blogin\b",
    r"\bsign in\b",
    r"\bcopyright\b",
    r"\bbefore sharing sensitive information\b",
    r"\bthe site is secure\b",
    r"\bensures that you are connecting\b",
]

FLUFF_PATTERNS = [
    r"\belevate your mind\b",
    r"\bdiscover the (?:scientifically-backed|secret|best) (?:strategies|ways|hacks|methods)\b",
    r"\bin today'?s rapidly (?:changing|evolving) world\b",
    r"\bunlock your (?:full )?potential\b",
    r"\blet'?s dive in(?:to)?\b",
    r"\bwelcome to (?:our|this) (?:guide|post|blog|article)\b",
    r"\bin this (?:blog post|article|guide|feature)\b",
    r"\bread on to (?:learn|discover|find out)\b",
    r"\bdon'?t forget to (?:subscribe|like|share)\b",
    r"\bclick here to (?:learn|read) more\b",
    r"\bboost your (?:iq|brain|mind) today\b",
    r"\bdownload our (?:new )?mobile app\b",
    r"\bstart your free (?:3-day )?trial\b",
    r"\bthe ultimate guide to\b",
    r"\bhave you ever wondered\b",
    r"\blook no further\b",
]

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "are",
    "what", "how", "why", "with", "about", "by", "from", "as", "it", "this", "that",
    "can", "be", "do", "does", "did", "write", "me", "post", "actual", "actually"
}


# --- 1. Document Chunking Infrastructure ---
class TextChunk(BaseModel):
    """Structured text chunk preserving character span locators."""

    chunk_index: int = Field(..., description="0-indexed position of chunk in document")
    text: str = Field(..., description="Cleaned substring content of the chunk")
    start_char: int = Field(..., description="Start character offset in full source document")
    end_char: int = Field(..., description="End character offset in full source document")
    locator: str = Field(..., description="Formatted character span locator string")


class DocumentChunker:
    """Deterministic document chunking preserving character spans and context overlap."""

    def __init__(
        self,
        max_chunk_size: int = 3000,
        chunk_overlap: int = 300,
    ) -> None:
        if max_chunk_size <= 0:
            raise ValueError("max_chunk_size must be greater than 0")
        if chunk_overlap < 0 or chunk_overlap >= max_chunk_size:
            raise ValueError("chunk_overlap must be non-negative and smaller than max_chunk_size")

        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> List[TextChunk]:
        """Splits full document text into overlapping deterministic chunks."""
        if not text or not text.strip():
            return []

        doc_len = len(text)
        if doc_len <= self.max_chunk_size:
            return [
                TextChunk(
                    chunk_index=0,
                    text=text,
                    start_char=0,
                    end_char=doc_len,
                    locator=f"span:0-{doc_len}",
                )
            ]

        chunks: List[TextChunk] = []
        start = 0
        chunk_idx = 0

        while start < doc_len:
            end = min(start + self.max_chunk_size, doc_len)

            if end < doc_len:
                boundary_search_start = max(start + self.max_chunk_size - self.chunk_overlap, start)
                best_end = -1
                for punct in [".\n", ". ", "\n\n", "\n", "? ", "! "]:
                    pos = text.rfind(punct, boundary_search_start, end)
                    if pos != -1:
                        best_end = pos + len(punct)
                        break
                if best_end != -1:
                    end = best_end

            chunk_text = text[start:end]
            chunks.append(
                TextChunk(
                    chunk_index=chunk_idx,
                    text=chunk_text,
                    start_char=start,
                    end_char=end,
                    locator=f"span:{start}-{end}",
                )
            )

            chunk_idx += 1
            if end >= doc_len:
                break

            step = end - start - self.chunk_overlap
            if step <= 0:
                step = self.max_chunk_size - self.chunk_overlap
            start += step

        return chunks


# --- 2. Raw Structured Output Models for LLM Extraction ---
class RawNumberFact(BaseModel):
    value: str = Field(..., description="Exact metric value string e.g. '40%'")
    unit: Optional[str] = Field(default=None, description="Unit of measurement")
    denominator: Optional[str] = Field(default=None, description="Scope or denominator")
    timeframe: Optional[str] = Field(default=None, description="Time period")
    sample: Optional[str] = Field(default=None, description="Sample size or details")


class RawCandidateEvidence(BaseModel):
    verbatim_quote: str = Field(
        ...,
        description="Exact verbatim text snippet copied character-for-character from source text.",
    )
    claim_summary: str = Field(
        ...,
        description="Concise summary of what the source passage is claiming.",
    )
    relevance_explanation: str = Field(
        default="",
        description="Explicit explanation detailing HOW this quote directly answers or provides insight for the Research Question.",
    )
    insight_type: str = Field(
        default="research_finding",
        description="Categorized type: research_finding, statistic, expert_claim, company_claim, example, case_study, anecdote, mechanism, opinion, prediction, marketing_claim, definition, trend, limitation, contradiction.",
    )
    evidence_type: Optional[str] = Field(
        default=None,
        description="Legacy evidence type alias mapped to insight_type.",
    )
    source_role: str = Field(
        default="evidence",
        description="Architectural role of source: evidence, context, discovery, primary_source, expert_perspective, example, company_claim, anecdotal, marketing.",
    )
    attribution: Optional[str] = Field(
        default=None,
        description="Explicit entity/author attribution if quote reports third-party claim. Null if direct author statement.",
    )
    suggested_writer_phrasing: Optional[str] = Field(
        default=None,
        description="Recommended phrasing for future content writer preserving epistemic and attribution limits without upgrading claim strength.",
    )
    limitations: Optional[str] = Field(
        default=None,
        description="Explicit caveats, sample limits, or study disclaimers in source text.",
    )
    is_substantive: bool = Field(
        default=True,
        description="Whether passage contains substantive research value (False for generic marketing fluff or intros).",
    )
    numbers: List[RawNumberFact] = Field(
        default_factory=list,
        description="Structured quantitative metrics in quote ONLY if present. Do NOT infer missing fields.",
    )
    data_date: Optional[str] = Field(
        default=None,
        description="Date of data collection (YYYY-MM-DD or YYYY) if stated.",
    )

    def model_post_init(self, __context) -> None:
        if self.evidence_type and (not self.insight_type or self.insight_type == "research_finding"):
            self.insight_type = self.evidence_type
        elif self.insight_type and not self.evidence_type:
            self.evidence_type = self.insight_type


class ExtractedCandidatesPayload(BaseModel):
    items: List[RawCandidateEvidence] = Field(default_factory=list)


# --- 3. Evidence Extractor System Prompt ---
EXTRACTOR_SYSTEM_PROMPT = """You are an Insight & Claim Interpretation Specialist in ALZAI's research-backed content engine.
Your task is to analyze the provided source text chunk and extract HIGH-VALUE insights, claims, evidence, mechanisms, examples, case studies, or anecdotes that directly address the Research Question.

STRICT ACCURACY & EPISTEMIC PRESERVATION RULES:
1. VERBATIM QUOTE CONTAINMENT: Every verbatim_quote MUST be copied EXACTLY, character-for-character, from the supplied text. NEVER paraphrase quotes.
2. SUBSTANTIVENESS OVER FLUFF: Extract ONLY substantive information. EXPLICITLY REJECT marketing fluff, clickbait intros ("Elevate your mind", "Unlock your potential", "In today's rapidly changing world", "Let's dive into"), SEO filler, and navigation.
3. PRESERVE CLAIM STRENGTH & ATTRIBUTION:
   - Identify WHO is making the claim (attribution).
   - DO NOT upgrade a source's claim! Provide suggested_writer_phrasing that maintains epistemic limits.
     - If a company claims something: phrasing MUST be "Company X claims..." NOT "It is proven that..."
     - If a study observed an effect: phrasing MUST be "Researchers observed..."
     - If users report an anecdote: phrasing MUST be "Some users report..."
4. INSIGHT TYPES:
   Classify each item into one of: research_finding, statistic, expert_claim, company_claim, example, case_study, anecdote, mechanism, opinion, prediction, marketing_claim, definition, trend, limitation, contradiction.
5. SOURCE ROLES:
   Classify the role into one of: evidence, context, discovery, primary_source, expert_perspective, example, company_claim, anecdotal, marketing.
6. ZERO IS PREFERRED: If the text chunk contains no substantive, relevant insight for the Research Question, return {"items": []}.
"""


# --- 4. Evidence Extraction Worker Service ---
class EvidenceExtractor:
    """Extracts structured candidate evidence items, enforces semantic relevance, and verifies quote containment."""

    def __init__(
        self,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
        chunker: Optional[DocumentChunker] = None,
        min_document_relevance: float = 0.05,
    ) -> None:
        self.use_llm = use_llm
        self.llm_client = llm_client if use_llm else None
        self.chunker = chunker or DocumentChunker()
        self.min_document_relevance = min_document_relevance

    def extract_evidence(
        self,
        snapshot: FetchSnapshot,
        question: ResearchQuestion,
    ) -> List[EvidenceItem]:
        """Transforms FetchSnapshot and ResearchQuestion into verified, high-signal EvidenceItems."""
        if not snapshot or not snapshot.cleaned_text or not snapshot.cleaned_text.strip() or snapshot.error:
            return []

        if not question or not question.question.strip():
            return []

        # PRE-FILTER GATE: Evaluate snapshot-level relevance before extracting
        is_relevant, doc_score = self.is_snapshot_relevant(snapshot, question, threshold=self.min_document_relevance)
        if not is_relevant:
            # Snapshot text is completely off-topic for this ResearchQuestion; return zero evidence
            return []

        # Determine source quality tier
        from tools.source_triage import SourceTriage
        triage_helper = SourceTriage()
        source_tier = triage_helper.determine_quality_tier(snapshot.url)

        # Step 1: Chunk document text deterministically
        chunks = self.chunker.chunk(snapshot.cleaned_text)
        if not chunks:
            return []

        candidate_items: List[RawCandidateEvidence] = []

        for chunk in chunks:
            if self.use_llm and self.llm_client is not None:
                extracted = self._extract_via_llm(chunk.text, question)
            else:
                extracted = self._extract_fallback(chunk.text, question)

            for cand in extracted:
                candidate_items.append(cand)

        # Step 2: Filter, Deduplicate, and Verify Candidates
        verified_evidence_pool: List[EvidenceItem] = []
        seen_quotes: Set[str] = set()

        for cand in candidate_items:
            quote = cand.verbatim_quote.strip() if cand.verbatim_quote else ""
            if not quote:
                continue

            # Normalized deduplication across ALL chunks
            norm_quote = self._normalize_quote_key(quote)
            if norm_quote in seen_quotes:
                continue

            # 1. Deterministic Boilerplate & Fluff Filter
            if self._is_boilerplate(quote) or not self._is_substantive(quote) or not cand.is_substantive:
                continue

            # 2. Length Filter (<20 chars rejected unless containing valid numbers)
            if len(quote) < 20 and not cand.numbers:
                continue

            # 3. Question Semantic Relevance Filter
            if not self._is_relevant_to_question(quote, cand.claim_summary, cand.relevance_explanation, question):
                continue

            # 4. CRITICAL DETERMINISTIC QUOTE VERIFICATION GATE
            is_verified = QuoteVerifier.verify(quote, snapshot.cleaned_text)
            if not is_verified:
                continue

            seen_quotes.add(norm_quote)

            # Compute exact character offset locator relative to snapshot.cleaned_text
            locator = self._compute_exact_locator(quote, snapshot.cleaned_text)

            # Normalize insight_type and source_role
            valid_insight_types = {
                "research_finding", "statistic", "expert_claim", "company_claim", "example",
                "case_study", "anecdote", "mechanism", "opinion", "prediction",
                "marketing_claim", "definition", "trend", "limitation", "contradiction",
                "causal_claim", "expert_opinion", "promotional"
            }
            valid_roles = {
                "evidence", "context", "discovery", "primary_source", "expert_perspective",
                "example", "company_claim", "anecdotal", "marketing"
            }
            insight_t = cand.insight_type.lower() if cand.insight_type.lower() in valid_insight_types else "research_finding"
            s_role = cand.source_role.lower() if cand.source_role.lower() in valid_roles else "evidence"

            # Filter and transform NumberFacts
            number_facts = []
            for num in cand.numbers:
                if num.value and num.value.strip():
                    number_facts.append(
                        NumberFact(
                            value=num.value.strip(),
                            unit=num.unit.strip() if num.unit else None,
                            denominator=num.denominator.strip() if num.denominator else None,
                            timeframe=num.timeframe.strip() if num.timeframe else None,
                            sample=num.sample.strip() if num.sample else None,
                        )
                    )

            # Parse optional data_date
            parsed_date: Optional[date] = None
            if cand.data_date:
                parsed_date = self._parse_date(cand.data_date)

            # Generate deterministic evidence ID
            quote_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()[:10]
            evidence_id = f"ev-{snapshot.fetch_id[:8]}-{quote_hash}"

            evidence_item = EvidenceItem(
                evidence_id=evidence_id,
                fetch_id=snapshot.fetch_id,
                locator=locator,
                verbatim_quote=quote,
                claim_summary=cand.claim_summary.strip() if cand.claim_summary else quote[:120],
                insight_type=insight_t,
                evidence_type=insight_t,
                source_role=s_role,
                source_tier=source_tier,
                attribution=cand.attribution.strip() if cand.attribution else None,
                suggested_writer_phrasing=cand.suggested_writer_phrasing.strip() if cand.suggested_writer_phrasing else None,
                limitations=cand.limitations.strip() if cand.limitations else None,
                substantive=True,
                relevance_explanation=cand.relevance_explanation.strip() if cand.relevance_explanation else None,
                numbers=number_facts,
                data_date=parsed_date,
                quote_verified=True,
            )

            verified_evidence_pool.append(evidence_item)

        return verified_evidence_pool

    @classmethod
    def is_snapshot_relevant(
        cls,
        snapshot: FetchSnapshot,
        question: ResearchQuestion,
        threshold: float = 0.05,
    ) -> tuple[bool, float]:
        """Evaluates whether full FetchSnapshot text has non-zero relevance to target ResearchQuestion."""
        if not snapshot or not snapshot.cleaned_text:
            return False, 0.0

        q_context = f"{question.question} {question.rationale} {' '.join(question.search_queries or [])}".lower()
        raw_words = set(re.findall(r"\w+", q_context))
        search_terms = {w for w in raw_words if len(w) > 2 and w not in STOP_WORDS}

        if not search_terms:
            return True, 1.0

        doc_text = snapshot.cleaned_text.lower()
        matched = 0
        for term in search_terms:
            t_stem = term.rstrip("s") if len(term) > 3 else term
            if t_stem in doc_text or term in doc_text:
                matched += 1

        score = matched / len(search_terms)
        return score >= threshold, score

    def _extract_via_llm(
        self,
        chunk_text: str,
        question: ResearchQuestion,
    ) -> List[RawCandidateEvidence]:
        """Invokes Gemini LLM to extract candidate evidence JSON from a single chunk."""
        if not self.llm_client:
            return []

        prompt = (
            f"Research Question: {question.question}\n"
            f"Question Rationale: {question.rationale}\n\n"
            f"Source Text Chunk:\n\"\"\"\n{chunk_text}\n\"\"\"\n\n"
            f"Required JSON Schema:\n{json.dumps(ExtractedCandidatesPayload.model_json_schema(), indent=2)}\n\n"
            "Extract HIGH-SIGNAL evidence candidates directly answering the Research Question. "
            "If no relevant evidence exists in this chunk, return {\"items\": []}. Respond ONLY with the JSON object:"
        )

        try:
            raw_json = self.llm_client.generate_json(
                prompt=prompt,
                system_instruction=EXTRACTOR_SYSTEM_PROMPT,
                temperature=0.1,
            )
            data = json.loads(raw_json)
            payload = ExtractedCandidatesPayload.model_validate(data)
            return payload.items
        except Exception:
            return []

    def _extract_fallback(
        self,
        chunk_text: str,
        question: ResearchQuestion,
    ) -> List[RawCandidateEvidence]:
        """Deterministic rule-based extractor used in offline or fallback modes."""
        candidates: List[RawCandidateEvidence] = []
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk_text) if len(s.strip()) > 20]

        question_context = f"{question.question} {question.rationale} {' '.join(question.search_queries or [])}".lower()
        raw_words = set(re.findall(r"\w+", question_context))
        question_terms = {w for w in raw_words if len(w) > 2 and w not in STOP_WORDS}

        for sentence in sentences:
            if self._is_boilerplate(sentence) or not self._is_substantive(sentence):
                continue

            s_lower = sentence.lower()
            term_matches = [w for w in question_terms if (w.rstrip("s") if len(w) > 3 else w) in s_lower or w in s_lower]
            has_number = bool(re.search(r"\d+(?:\.\d+)?%|\$\d+|\b\d+\b", sentence))

            # Require at least 2 key term matches OR 1 key term match with quantitative metric
            if len(term_matches) >= 2 or (has_number and len(term_matches) >= 1):
                numbers = []
                stat_match = re.search(r"(\d+(?:\.\d+)?%|\$\d+[\w\s]*|\b\d+\s+(?:percent|users|projects|accuracy|points)\b)", sentence)
                if stat_match:
                    numbers.append(RawNumberFact(value=stat_match.group(1).strip()))

                attribution = None
                attr_match = re.search(r"(?:according to|reported by|stated by|found by)\s+([A-Z][\w\s]+)", sentence, re.IGNORECASE)
                if attr_match:
                    attribution = attr_match.group(1).strip()

                insight_t = "statistic" if has_number else ("expert_claim" if attribution else "research_finding")
                phrasing = f"{attribution} states: '{sentence}'" if attribution else sentence

                candidates.append(
                    RawCandidateEvidence(
                        verbatim_quote=sentence,
                        claim_summary=f"Key finding regarding {question.question[:40]}",
                        relevance_explanation=f"Matches research question concepts: {', '.join(term_matches[:3])}",
                        insight_type=insight_t,
                        evidence_type=insight_t,
                        source_role="evidence",
                        attribution=attribution,
                        suggested_writer_phrasing=phrasing,
                        is_substantive=True,
                        numbers=numbers,
                    )
                )

        return candidates[:8]

    @staticmethod
    def _is_boilerplate(text: str) -> bool:
        """Determines if text snippet is administrative, navigational, or site boilerplate."""
        t_lower = text.lower().strip()
        for pattern in BOILERPLATE_PATTERNS:
            if re.search(pattern, t_lower):
                return True
        return False

    @staticmethod
    def _is_substantive(text: str) -> bool:
        """Determines if a passage contains substantive research/insight value, rejecting marketing fluff & generic intros."""
        if not text or len(text.strip()) < 15:
            return False

        t_lower = text.lower().strip()
        for pattern in FLUFF_PATTERNS:
            if re.search(pattern, t_lower):
                return False

        if re.match(r"^(?:in today'?s|welcome to|let'?s dive|elevate your|unlock your|are you looking|have you ever)", t_lower):
            return False

        return True

    @staticmethod
    def _is_relevant_to_question(
        quote: str,
        summary: str,
        explanation: str,
        question: ResearchQuestion,
    ) -> bool:
        """Determines if a candidate quote is semantically relevant to the target ResearchQuestion."""
        question_context = f"{question.question} {question.rationale} {' '.join(question.search_queries or [])}".lower()
        raw_words = set(re.findall(r"\w+", question_context))
        search_terms = {w for w in raw_words if len(w) > 2 and w not in STOP_WORDS}

        if not search_terms:
            return True

        combined_text = f"{quote} {summary} {explanation}".lower()
        for term in search_terms:
            t_stem = term.rstrip("s") if len(term) > 3 else term
            if t_stem in combined_text or term in combined_text:
                return True

        return False

    @staticmethod
    def _compute_exact_locator(quote: str, full_text: str) -> str:
        """Computes exact character offset span locator relative to full_text."""
        pos = full_text.find(quote)
        if pos != -1:
            return f"span:{pos}-{pos + len(quote)}"

        norm_quote = re.sub(r"\s+", " ", quote).strip().lower()
        norm_full = re.sub(r"\s+", " ", full_text).lower()
        norm_pos = norm_full.find(norm_quote)

        if norm_pos != -1:
            return f"span:{norm_pos}-{norm_pos + len(quote)}"

        return "span:0-0"

    @staticmethod
    def _normalize_quote_key(quote: str) -> str:
        """Collapses whitespace and lowercases quote for deduplication."""
        return re.sub(r"\s+", " ", quote).strip().lower()

    @staticmethod
    def _parse_date(date_str: str) -> Optional[date]:
        """Safely parses YYYY-MM-DD or YYYY string into date object."""
        if not date_str:
            return None
        date_str = date_str.strip()
        match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", date_str)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass
        year_match = re.search(r"\b(19\d\2|20\d{2})\b", date_str)
        if year_match:
            try:
                return date(int(year_match.group(1)), 1, 1)
            except ValueError:
                pass
        return None
