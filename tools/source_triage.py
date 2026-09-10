from typing import List, Optional, Set
from urllib.parse import urlparse
from tools.search_tool import SearchResult

# Blocklist for low-quality content mills / promotional slop
DEFAULT_BLOCKLIST: Set[str] = {
    "ezinearticles.com",
    "contentmill.com",
    "promotional-seo-spam.com",
}

# Domain Tier Mappings
TIER_1_DOMAINS = {".gov", ".edu", "arxiv.org", "nature.com", "science.org", "sloan.mit.edu"}
TIER_2_DOMAINS = {"reuters.com", "bloomberg.com", "wsj.com", "ft.com", "bbc.com", "techcrunch.com", "ieee.org"}
TIER_3_DOMAINS = {"github.com", "medium.com", "substack.com", "reddit.com", "news.ycombinator.com", "dev.to"}


class SourceTriage:
    """Deterministic Source Triage Engine.

    Scores, filters, deduplicates, and ranks search results based on domain quality,
    recency heuristics, and domain capping constraints.
    """

    def __init__(
        self,
        max_per_domain: int = 2,
        blocklist: Optional[Set[str]] = None,
    ) -> None:
        self.max_per_domain = max_per_domain
        self.blocklist = blocklist or DEFAULT_BLOCKLIST

    def determine_quality_tier(self, url: str) -> int:
        """Determines the quality tier (1=highest, 5=lowest) for a given URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if any(b in domain for b in self.blocklist):
            return 5

        if any(domain.endswith(t1) or t1 in domain for t1 in TIER_1_DOMAINS):
            return 1
        if any(domain.endswith(t2) or t2 in domain for t2 in TIER_2_DOMAINS):
            return 2
        if any(domain.endswith(t3) or t3 in domain for t3 in TIER_3_DOMAINS):
            return 3

        # Path heuristics
        path = parsed.path.lower()
        if "/research/" in path or "/paper/" in path or "/case-study/" in path:
            return 2
        if "/blog/" in path or "/article/" in path:
            return 4

        return 3

    def triage_and_rank(
        self,
        results: List[SearchResult],
        seen_urls: Optional[Set[str]] = None,
    ) -> List[SearchResult]:
        """Filters, deduplicates, and ranks search results.

        Args:
            results: Input list of SearchResult items.
            seen_urls: Set of previously fetched/seen URLs to skip.

        Returns:
            Ranked list of top SearchResult items respecting domain caps and blocklists.
        """
        seen = seen_urls or set()
        domain_counts: dict[str, int] = {}
        triaged: List[tuple[int, SearchResult]] = []

        for item in results:
            url_clean = item.url.strip().rstrip("/")
            if url_clean in seen:
                continue

            domain = item.domain.lower()
            if any(b in domain for b in self.blocklist):
                continue

            current_count = domain_counts.get(domain, 0)
            if current_count >= self.max_per_domain:
                continue

            tier = self.determine_quality_tier(item.url)
            domain_counts[domain] = current_count + 1
            seen.add(url_clean)
            triaged.append((tier, item))

        # Sort by quality tier ascending (tier 1 first, tier 2 second, etc.)
        triaged.sort(key=lambda x: x[0])
        return [item for tier, item in triaged]
