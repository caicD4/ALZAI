from tools.search_tool import SearchResult
from tools.source_triage import SourceTriage


def test_source_triage_tier_ranking():
    triage = SourceTriage(max_per_domain=2)

    r_tier1 = SearchResult(
        title="MIT Sloan Research",
        url="https://sloan.mit.edu/paper",
        canonical_url="https://sloan.mit.edu/paper",
        snippet="MIT study",
        domain="sloan.mit.edu",
        query="test",
        rank=2,
    )
    r_tier2 = SearchResult(
        title="Reuters News",
        url="https://reuters.com/article/ai",
        canonical_url="https://reuters.com/article/ai",
        snippet="Reuters report",
        domain="reuters.com",
        query="test",
        rank=1,
    )
    r_unknown = SearchResult(
        title="Unknown Blog",
        url="https://some-unknown-blog.com/post",
        canonical_url="https://some-unknown-blog.com/post",
        snippet="Blog post",
        domain="some-unknown-blog.com",
        query="test",
        rank=3,
    )

    ranked = triage.triage_and_rank([r_unknown, r_tier2, r_tier1])

    # Tier 1 (MIT) should rank first, then Tier 2 (Reuters), then Tier 3 (Unknown)
    assert ranked[0].domain == "sloan.mit.edu"
    assert ranked[1].domain == "reuters.com"
    assert ranked[2].domain == "some-unknown-blog.com"


def test_source_triage_deduplication_and_per_domain_limits():
    triage = SourceTriage(max_per_domain=1)

    r1 = SearchResult(
        title="Article 1",
        url="https://techcrunch.com/article1/",
        canonical_url="https://techcrunch.com/article1",
        snippet="Snippet 1",
        domain="techcrunch.com",
        query="q1",
        rank=1,
    )
    r1_duplicate = SearchResult(
        title="Article 1 Dup",
        url="https://techcrunch.com/article1",
        canonical_url="https://techcrunch.com/article1",
        snippet="Snippet 1 dup",
        domain="techcrunch.com",
        query="q2",
        rank=1,
    )
    r2 = SearchResult(
        title="Article 2",
        url="https://techcrunch.com/article2",
        canonical_url="https://techcrunch.com/article2",
        snippet="Snippet 2",
        domain="techcrunch.com",
        query="q1",
        rank=2,
    )

    # test canonical URL seen deduplication
    ranked = triage.triage_and_rank([r1, r1_duplicate, r2])

    # r1_duplicate is duplicate canonical URL; r2 exceeds max_per_domain=1
    assert len(ranked) == 1
    assert ranked[0].canonical_url == "https://techcrunch.com/article1"


def test_source_triage_blocklist_filtering():
    triage = SourceTriage(blocklist={"spam-domain.com"})

    r_valid = SearchResult(
        title="Valid Site",
        url="https://github.com/project",
        canonical_url="https://github.com/project",
        snippet="Valid project",
        domain="github.com",
        query="q",
        rank=1,
    )
    r_spam = SearchResult(
        title="Spam Site",
        url="https://spam-domain.com/article",
        canonical_url="https://spam-domain.com/article",
        snippet="Spam link",
        domain="spam-domain.com",
        query="q",
        rank=2,
    )

    ranked = triage.triage_and_rank([r_valid, r_spam])
    assert len(ranked) == 1
    assert ranked[0].domain == "github.com"


def test_source_triage_query_relevance_filtering():
    triage = SourceTriage(min_relevance_score=0.1)

    relevant = SearchResult(
        title="Neuroplasticity and Fluid Intelligence in Adults",
        url="https://nature.com/articles/neuroplasticity-adult-brain",
        canonical_url="https://nature.com/articles/neuroplasticity-adult-brain",
        snippet="Study on how adult brain plasticity improves fluid intelligence.",
        domain="nature.com",
        query="neuroplasticity fluid intelligence adult brain plasticity",
        rank=1,
    )

    irrelevant = SearchResult(
        title="ChatGPT DAN Jailbreak Prompt",
        url="https://github.com/0xk1h0/ChatGPT_DAN",
        canonical_url="https://github.com/0xk1h0/ChatGPT_DAN",
        snippet="Collection of ChatGPT DAN prompt jailbreaks and tricks.",
        domain="github.com",
        query="neuroplasticity fluid intelligence adult brain plasticity",
        rank=2,
    )

    query = "neuroplasticity fluid intelligence adult brain plasticity"
    ranked = triage.triage_and_rank([relevant, irrelevant], query=query)

    # Irrelevant result with 0 term overlap is filtered out
    assert len(ranked) == 1
    assert ranked[0].url == "https://nature.com/articles/neuroplasticity-adult-brain"
