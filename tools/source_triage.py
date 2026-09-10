import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from tools.search_tool import SearchResult, normalize_url

# Default blocklist for content mills, SEO spam, and low-quality portals
DEFAULT_BLOCKLIST: Set[str] = {
    "ezinearticles.com",
    "contentmill.com",
    "promotional-seo-spam.com",
    "ehow.com",
}

# Explicit Heuristic Tier Rule Mappings
TIER_1_DOMAINS = {
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "cell.com",
    "pnas.org",
    "frontiersin.org",
    "springer.com",
    "wiley.com",
    "biorxiv.org",
    "medrxiv.org",
    "arxiv.org",
    "plos.org",
    "tandfonline.com",
    "jamanetwork.com",
    "sloan.mit.edu",
    ".gov",
    ".edu",
}

TIER_2_DOMAINS = {
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "bbc.com",
    "techcrunch.com",
    "ieee.org",
    "scientificamerican.com",
    "newscientist.com",
    "theatlantic.com",
}

TIER_3_DOMAINS = {
    "wikipedia.org",
    "medium.com",
    "substack.com",
    "github.com",
    "news.ycombinator.com",
    "dev.to",
}

TIER_4_DOMAINS = {
    "quora.com",
    "reddit.com",
    "whats-your-iq.com",
    "realiqtest.net",
    "thegeniusindex.com",
    "highiqpro.com",
    "neurolaunch.com",
}

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "for", "to", "of", "and", "or", "is", "are",
    "what", "how", "why", "with", "about", "by", "from", "as", "it", "this", "that",
    "can", "be", "do", "does", "did", "write", "me", "post", "on", "actual", "actually"
}


class TriageAuditRecord(BaseModel):
    """Audit log item documenting source selection or explicit rejection reason."""

    url: str = Field(..., description="Target URL evaluated")
    domain: str = Field(..., description="Domain name of candidate")
    quality_tier: int = Field(..., description="Assigned quality tier (1=academic, 5=spam)")
    relevance_score: float = Field(..., description="Query relevance score between 0.0 and 1.0")
    combined_score: float = Field(..., description="Composite ranking score")
    accepted: bool = Field(..., description="Whether candidate was accepted for fetch")
    rejection_reason: Optional[str] = Field(default=None, description="Inspectable rejection reason if discarded")


class SourceTriage:
    """Deterministic Source Candidate Selection & Relevance Verification Engine."""

    def __init__(
        self,
        max_per_domain: int = 2,
        blocklist: Optional[Set[str]] = None,
        allowlist: Optional[Set[str]] = None,
        min_relevance_score: float = 0.08,
    ) -> None:
        self.max_per_domain = max_per_domain
        self.blocklist = blocklist if blocklist is not None else DEFAULT_BLOCKLIST
        self.allowlist = allowlist or set()
        self.min_relevance_score = min_relevance_score

    def determine_quality_tier(self, url: str) -> int:
        """Determines quality tier heuristic (1=highest academic/institutional, 5=lowest/spam)."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if any(b in domain for b in self.blocklist):
            return 5

        if self.allowlist and any(a in domain for a in self.allowlist):
            return 1

        if any(domain.endswith(t1) or t1 in domain for t1 in TIER_1_DOMAINS):
            return 1
        if any(domain.endswith(t2) or t2 in domain for t2 in TIER_2_DOMAINS):
            return 2
        if any(domain.endswith(t3) or t3 in domain for t3 in TIER_3_DOMAINS):
            return 3
        if any(domain.endswith(t4) or t4 in domain for t4 in TIER_4_DOMAINS):
            return 4

        path = parsed.path.lower()
        if "/research/" in path or "/paper/" in path or "/case-study/" in path or "/articles/" in path:
            return 2
        if "/blog/" in path or "/article/" in path:
            return 4

        return 3

    @staticmethod
    def compute_relevance_score(item: SearchResult, query: Optional[str] = None) -> float:
        """Calculates keyword relevance overlap between search query and result metadata."""
        search_q = query or item.query
        if not search_q or not search_q.strip():
            return 1.0

        raw_words = re.findall(r"\w+", search_q.lower())
        query_terms = [w for w in raw_words if len(w) > 2 and w not in STOP_WORDS]
        if not query_terms:
            return 1.0

        content_text = f"{item.title} {item.snippet} {item.url}".lower()
        matched_terms = sum(1 for term in query_terms if term in content_text)
        return matched_terms / len(query_terms)

    def triage_and_rank(
        self,
        results: List[SearchResult],
        seen_urls: Optional[Set[str]] = None,
        query: Optional[str] = None,
    ) -> List[SearchResult]:
        """Filters and ranks search candidates, discarding irrelevant or blocked URLs."""
        candidates, _ = self.triage_with_audit(results, seen_urls=seen_urls, query=query)
        return candidates

    def triage_with_audit(
        self,
        results: List[SearchResult],
        seen_urls: Optional[Set[str]] = None,
        query: Optional[str] = None,
    ) -> tuple[List[SearchResult], List[TriageAuditRecord]]:
        """Filters and ranks candidates while producing an inspectable audit log."""
        seen = {normalize_url(u) for u in (seen_urls or set()) if u}
        domain_counts: Dict[str, int] = {}
        triaged: List[tuple[float, SearchResult, TriageAuditRecord]] = []
        audit_log: List[TriageAuditRecord] = []

        for item in results:
            canon_url = item.canonical_url or normalize_url(item.url)
            domain = item.domain.lower()
            tier = self.determine_quality_tier(item.url)
            rel_score = self.compute_relevance_score(item, query=query)
            
            # Combined score: Quality tier weight + query relevance weight
            # Tier 1 gives 8.0, Tier 2 gives 6.0, Tier 3 gives 4.0, Tier 4 gives 2.0; rel_score gives up to 5.0
            combined_score = round((5.0 - tier) * 2.0 + rel_score * 5.0, 3)

            if not canon_url or canon_url in seen:
                record = TriageAuditRecord(
                    url=item.url,
                    domain=domain,
                    quality_tier=tier,
                    relevance_score=rel_score,
                    combined_score=combined_score,
                    accepted=False,
                    rejection_reason="duplicate_canonical_url",
                )
                audit_log.append(record)
                continue

            if any(b in domain for b in self.blocklist):
                record = TriageAuditRecord(
                    url=item.url,
                    domain=domain,
                    quality_tier=tier,
                    relevance_score=rel_score,
                    combined_score=combined_score,
                    accepted=False,
                    rejection_reason="blocked_domain",
                )
                audit_log.append(record)
                continue

            if query and rel_score < self.min_relevance_score:
                record = TriageAuditRecord(
                    url=item.url,
                    domain=domain,
                    quality_tier=tier,
                    relevance_score=rel_score,
                    combined_score=combined_score,
                    accepted=False,
                    rejection_reason=f"relevance_below_threshold ({rel_score:.2f} < {self.min_relevance_score:.2f})",
                )
                audit_log.append(record)
                continue

            current_count = domain_counts.get(domain, 0)
            if current_count >= self.max_per_domain:
                record = TriageAuditRecord(
                    url=item.url,
                    domain=domain,
                    quality_tier=tier,
                    relevance_score=rel_score,
                    combined_score=combined_score,
                    accepted=False,
                    rejection_reason=f"domain_limit_exceeded (max {self.max_per_domain})",
                )
                audit_log.append(record)
                continue

            domain_counts[domain] = current_count + 1
            seen.add(canon_url)

            record = TriageAuditRecord(
                url=item.url,
                domain=domain,
                quality_tier=tier,
                relevance_score=rel_score,
                combined_score=combined_score,
                accepted=True,
                rejection_reason=None,
            )
            audit_log.append(record)
            triaged.append((combined_score, item, record))

        # Sort primarily by combined_score DESC, secondarily by SERP rank ASC
        triaged.sort(key=lambda x: (-x[0], x[1].rank))
        ranked_candidates = [item for _, item, _ in triaged]

        return ranked_candidates, audit_log
