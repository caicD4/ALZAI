"""Content Landscape — first-class content intelligence.

Represents EXISTING content found in the wild (never fabricated), plus the
landscape analysis (dominant angles, saturated angles, content gaps, and
possible original angles) that lets ALZAI avoid publishing the same generic
post everyone else already wrote.

Retrieval MUST happen before semantic analysis. Engagement data is only ever
stored when actually retrieved from a trustworthy source — never invented.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class EngagementSignal(BaseModel):
    """Real engagement data with explicit provenance. Never invented."""

    metric: str = Field(..., description="Engagement metric, e.g. 'likes', 'reposts', 'views'")
    value: int = Field(..., description="Numeric value of the metric")
    provenance: str = Field(..., description="Where the number actually came from (source/URL/method)")


class ContentReference(BaseModel):
    """A piece of EXISTING content retrieved from the landscape.

    All fields describe genuinely retrieved material. Fields only populated when
    the information was actually available (author, publication_date, engagement).
    """

    reference_id: str = Field(..., description="Unique identifier for this content reference")
    title: str = Field(..., description="Title of the existing content")
    url: Optional[str] = Field(default=None, description="URL of the original content if available")
    source_type: str = Field(default="web", description="Type of content source, e.g. 'blog', 'article', 'linkedin_post', 'x_post', 'news', 'reddit', 'forum'")
    author: Optional[str] = Field(default=None, description="Author/creator name ONLY if actually available")
    publication_date: Optional[str] = Field(default=None, description="Publication date ONLY if actually available")
    snippet: str = Field(..., description="Actual retrieved text snippet from the content")
    key_points: List[str] = Field(default_factory=list, description="Key points present in the retrieved content")
    angle: str = Field(..., description="The angle this existing content takes on the topic")
    hook: Optional[str] = Field(default=None, description="The hook/framing used, if discernible")
    tone: str = Field(default="", description="Observed tone, e.g. 'informative', 'critical', 'promotional'")
    main_argument: str = Field(default="", description="Central argument/main thrust of the content")
    notable_points: List[str] = Field(default_factory=list, description="Distinctive or notable statements/claims")
    relevance: str = Field(default="", description="Why this reference is relevant to the user's request")
    discovery_source: str = Field(default="search", description="How it was discovered, e.g. 'search', 'web'")
    engagement: Optional[EngagementSignal] = Field(default=None, description="Real engagement data if retrieved; None otherwise")


class ContentLandscape(BaseModel):
    """Analysis of existing content on the topic — derived from RETRIEVED references."""

    topic: str = Field(..., description="Topic the landscape covers")
    total_references: int = Field(default=0, description="Number of existing content references analyzed")
    reference_ids: List[str] = Field(default_factory=list, description="IDs of included references")
    dominant_angles: List[str] = Field(default_factory=list, description="Angles most existing content takes")
    repeated_arguments: List[str] = Field(default_factory=list, description="Arguments that recur across references")
    common_hooks: List[str] = Field(default_factory=list, description="Common opening hooks/framing")
    saturated_angles: List[str] = Field(default_factory=list, description="Angles heavily covered — avoid simply repeating")
    common_framing: List[str] = Field(default_factory=list, description="Shared framing/language across the space")
    audience_questions: List[str] = Field(default_factory=list, description="Questions the existing content implicitly answers or leaves open")
    disagreements: List[str] = Field(default_factory=list, description="Points where existing content disagrees")
    underexplored_perspectives: List[str] = Field(default_factory=list, description="Perspectives rarely covered by existing content")
    content_gaps: List[str] = Field(default_factory=list, description="Topics/angles nobody is covering — opportunity for original content")
    possible_original_angles: List[str] = Field(default_factory=list, description="Concrete original angles ALZAI could take to stand out")
    recommended_differentiation: str = Field(default="", description="How to differentiate from the existing conversation")

    def model_post_init(self, __context) -> None:
        self.total_references = len(self.reference_ids)