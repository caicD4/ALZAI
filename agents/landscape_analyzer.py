"""Content Landscape Analyzer — searches & analyzes EXISTING content on a topic.

Retrieval happens BEFORE semantic analysis. Search queries are generated from
the RequestIntent (never hardcoded per topic). The analyzer only ever reports
what was actually retrieved; engagement numbers are never invented.
"""

import json
import re
from typing import Any, Dict, List, Optional

from core.content_landscape import ContentLandscape, ContentReference
from core.request_intent import RequestIntent
from tools.llm_client import GeminiClient
from tools.search_tool import SearchResult, SearchTool

LANDSCAPE_LLM_SYSTEM_PROMPT = """You are ALZAI's Content Landscape Intelligence Analyst.
You analyze EXISTING content that was actually retrieved from the web about a topic, and you produce a ContentLandscape: which angles dominate, which are saturated, where the gaps are, and what original angle ALZAI could take to stand out.

STRICT INTEGRITY RULES:
1. Base EVERY claim below ONLY on the retrieved references you are given (their titles, snippets, source types, and any provided metadata).
2. NEVER invent, assume, or fabricate: no made-up engagement numbers, no assumed publication dates, no imagined article content.
3. Engagement signals are ONLY reported if explicitly provided. Otherwise leave them out.
4. If a reference category is thin, say so honestly: an empty or short list is fine. Do NOT pad lists with generic invented angles.
5. "content_gaps" = things the retrieved references clearly do NOT cover. "possible_original_angles" = concrete, specific hooks that would differ from what the retrieved references cover.

Output ONLY valid JSON for a ContentLandscape.
"""


class LandscapeAnalyzer:
    """Searches the web for existing content and analyzes the landscape."""

    last_analysis_method: Optional[str] = None
    last_analysis_error: Optional[str] = None

    def __init__(
        self,
        search_tool: Optional[SearchTool] = None,
        llm_client: Optional[GeminiClient] = None,
        use_llm: bool = True,
        max_queries: int = 4,
        max_results_per_query: int = 3,
    ) -> None:
        self.search_tool = search_tool or SearchTool()
        self.use_llm = use_llm
        if use_llm:
            self.llm_client = llm_client or GeminiClient()
        else:
            self.llm_client = None
        self.max_queries = max_queries
        self.max_results_per_query = max_results_per_query
        self.last_searches: List[Dict[str, Any]] = []

    def generate_landscape_queries(self, intent: RequestIntent) -> List[str]:
        """Derive landscape search queries from the request intent — never hardcoded per topic."""
        subject = intent.subject
        prop = (intent.proposition or "").strip()
        queries: List[str] = []

        base = f"about {subject}" if not subject.lower().startswith(("what", "why", "how")) else subject
        queries.append(f"best {base}")

        if intent.intent_type in ("critique", "claim_investigation") or intent.stance == "critical":
            queries.append(f"{subject} criticism controversy")
            if prop and "why" in prop.lower():
                queries.append(prop)
        elif intent.intent_type == "explanation":
            queries.append(f"{subject} explained simply")
            queries.append(f"{subject} guide overview")
        elif intent.intent_type == "content_request":
            queries.append(f"{subject} viral posts")
            queries.append(f"{subject} hot takes opinion")
        elif intent.intent_type == "comparison":
            queries.append(f"{subject} comparison vs")
        else:
            queries.append(f"{subject} key arguments debate")

        queries.append(f"{subject} main arguments counterarguments")

        seen: List[str] = []
        for q in queries:
            qq = q.strip().lower()
            if not qq or qq in seen:
                continue
            seen.append(qq)
            if len(seen) >= self.max_queries:
                break
        return seen

    def search_landscape(self, queries: List[str]) -> List[ContentReference]:
        """Run real searches and convert results into ContentReference objects (deduped)."""
        references: List[ContentReference] = []
        seen_urls = set()
        self.last_searches = []

        for query in queries:
            try:
                results: List[SearchResult] = self.search_tool.search(query, max_results=self.max_results_per_query)
            except Exception:
                results = []
            self.last_searches.append({"query": query, "results_found": len(results)})

            for r in results:
                if not r.canonical_url or r.canonical_url in seen_urls:
                    continue
                if not r.snippet and not r.title:
                    continue
                if len(r.snippet.strip().split()) < 2 and len(r.title.strip().split()) < 2:
                    continue
                seen_urls.add(r.canonical_url)
                references.append(self._search_result_to_reference(r))

        return references[:16]

    @staticmethod
    def _search_result_to_reference(r: SearchResult) -> ContentReference:
        snippet = r.snippet.strip()
        angle_guess = snippet[:140] if snippet else f"Title-based angle: {r.title.strip()[:140]}"
        return ContentReference(
            reference_id=f"ref-{abs(hash(r.canonical_url) & 0xffffffff):08x}",
            title=r.title.strip(),
            url=r.url,
            source_type=LandscapeAnalyzer._guess_source_type(r.domain),
            snippet=snippet,
            key_points=[snippet] if snippet else [],
            angle=angle_guess,
            relevance=f"Retrieved via search query: {r.query}",
            discovery_source="search",
            engagement=None,  # NEVER invented
        )

    @staticmethod
    def _guess_source_type(domain: str) -> str:
        d = domain.lower()
        if "reddit" in d or "forum" in d:
            return "forum"
        if "linkedin" in d:
            return "linkedin_post"
        if "x.com" in d or "twitter" in d or "twtr" in d:
            return "x_post"
        if any(k in d for k in ("cnn", "bbc", "wsj", "nytimes", "bloomberg", "wired", "theverge", "techcrunch")):
            return "news"
        if "github" in d:
            return "code"
        if "blog" in d or "medium" in d or "substack" in d:
            return "blog"
        return "web"

    def analyze(self, intent: RequestIntent, references: List[ContentReference]) -> ContentLandscape:
        """Analyze retrieved references into a ContentLandscape."""
        if not references:
            return ContentLandscape(
                topic=intent.subject,
                reference_ids=[],
                content_gaps=[f"No existing content references were retrieved for '{intent.subject}' via search."],
                possible_original_angles=[self._default_angle_for_intent(intent)],
                recommended_differentiation=f"Nothing retrieved yet; create fresh original content about {intent.subject}.",
            )

        if self.use_llm and self.llm_client is not None:
            landscape, error = self._analyze_via_llm(intent, references)
            if landscape:
                self.last_analysis_method = "gemini"
                self.last_analysis_error = None
                return landscape
            self.last_analysis_method = "grounded_fallback"
            self.last_analysis_error = error or "Unknown LLM error"

        self.last_analysis_method = "grounded_fallback"
        self.last_analysis_error = self.last_analysis_error or "LLM disabled/unavailable"
        return self._analyze_fallback(intent, references)

    def _build_llm_prompt(self, intent: RequestIntent, references: List[ContentReference]) -> str:
        ref_block = []
        for idx, ref in enumerate(references, start=1):
            parts = [
                f"[{idx}] Title: {ref.title}",
                f"    URL: {ref.url or 'n/a'}",
                f"    Source Type: {ref.source_type}",
            ]
            if ref.snippet:
                parts.append(f"    Snippet: {ref.snippet[:300]}")
            if ref.discovery_source:
                parts.append(f"    Discovery: {ref.discovery_source}")
            ref_block.append("\n".join(parts))
        return (
            f"USER REQUEST CONTEXT:\n"
            f"  Subject: {intent.subject}\n"
            f"  Intent Type: {intent.intent_type}\n"
            f"  Desired Content Type: {intent.desired_content_type}\n"
            f"  Stance: {intent.stance}\n"
            f"  Framing: {intent.proposition or 'None'}\n"
            f"  Research Goal: {intent.research_goal}\n\n"
            f"RETRIEVED EXISTING CONTENT ({len(references)} references):\n"
            + "\n".join(ref_block)
            + "\n\nProduce the ContentLandscape JSON. Base everything on the retrieved content ONLY. "
            "Identify saturated angles and concrete content gaps. Output ONLY valid JSON."
        )

    def _analyze_via_llm(
        self,
        intent: RequestIntent,
        references: List[ContentReference],
    ) -> tuple[Optional[ContentLandscape], Optional[str]]:
        if not self.llm_client:
            return None, "No LLM client available"
        try:
            raw_json = self.llm_client.generate_json(
                prompt=self._build_llm_prompt(intent, references[:12]),
                system_instruction=LANDSCAPE_LLM_SYSTEM_PROMPT,
                temperature=0.3,
                stage_label="LandscapeAnalyst",
            )
            data = json.loads(raw_json)
            landscape = ContentLandscape.model_validate(data)
            landscape.topic = intent.subject
            landscape.reference_ids = [r.reference_id for r in references]
            landscape.total_references = len(references)
            return landscape, None
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:200]}"

    def _analyze_fallback(
        self,
        intent: RequestIntent,
        references: List[ContentReference],
    ) -> ContentLandscape:
        titles = " ".join(r.title.lower() for r in references)
        title_words = re.findall(r"\w+", titles)

        def count_word(w: str) -> int:
            return title_words.count(w.lower())

        dominant = []
        probe_words = ["guide", "how", "why", "explained", "review", "best", "vs", "comparison", "pros", "cons", "controversy", "criticism"]
        for w in probe_words:
            if count_word(w) >= 2 or (w in ("guide", "how", "explained") and count_word(w) >= 1):
                dominant.append(f"{w.title()} angle")
        if not dominant:
            dominant = ["informational overview"]

        gaps = [
            f"Existing content on '{intent.subject}' is mostly {', '.join(dominant) if dominant else 'informational'}; "
            "personal, opinion-led or highly specific angles are underrepresented.",
        ]
        if len(references) < 4:
            gaps.append(f"Only {len(references)} distinct references retrieved — the landscape is thin, so original angles are wide open.")

        possible_angles = [self._default_angle_for_intent(intent)]
        if intent.stance == "critical":
            possible_angles.append(
                f"A balanced critical deep-dive on {intent.subject} that fairly engages the strongest counterarguments."
            )
        elif intent.intent_type == "explanation":
            possible_angles.append(
                f"{intent.subject} explained with the mental models practitioners actually use, not textbook definitions."
            )
        elif intent.intent_type == "content_request":
            possible_angles.append(
                f"A scroll-stopping, opinionated post on {intent.subject} that starts a real debate."
            )

        return ContentLandscape(
            topic=intent.subject,
            reference_ids=[r.reference_id for r in references],
            dominant_angles=dominant,
            saturated_angles=[dominant[0]] if dominant else [],
            content_gaps=gaps,
            possible_original_angles=possible_angles,
            recommended_differentiation=(
                f"Lead with an original, opinionated angle on {intent.subject} that the {len(references)} retrieved "
                f"references mostly do not cover: '{', '.join(possible_angles)}'."
            ),
        )

    @staticmethod
    def _default_angle_for_intent(intent: RequestIntent) -> str:
        if intent.intent_type == "critique" or intent.stance == "critical":
            return (
                f"The layered, honest case on {intent.subject}: the documented criticisms AND the strongest "
                f"counterarguments, in a fresh framing readers haven't seen."
            )
        if intent.intent_type == "explanation":
            return f"{intent.subject} explained through the lens practitioners actually care about."
        if intent.intent_type == "content_request":
            return f"An opinionated, hook-first take on {intent.subject} built to start a conversation."
        return f"A distinctive, insider-level perspective on {intent.subject}."