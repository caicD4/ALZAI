from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from core.quality_schemas import ContentQualityReport
from core.synthesis import ContentStrategy


class ContentPiece(BaseModel):
    """Represents a generated, quality-audited format output asset."""

    content_id: str = Field(..., description="Unique identifier for this content asset")
    format_id: str = Field(..., description="Format ID matching ContentFormatSpec e.g. 'linkedin', 'x_thread'")
    platform: str = Field(..., description="Target platform name e.g. 'LinkedIn', 'X/Twitter'")
    title: Optional[str] = Field(default=None, description="Headline or title of content asset")
    body_text: str = Field(..., description="Full prose body or assembled script text")
    sections: List[str] = Field(default_factory=list, description="Structured sub-components e.g. individual posts or slides")
    word_count: int = Field(default=0, description="Word count of body text")
    estimated_duration: Optional[str] = Field(default=None, description="Estimated reading/speaking time e.g. '45s', '5 min'")
    brief_id: Optional[str] = Field(default=None, description="ID of source ResearchBrief")
    version: int = Field(default=1, description="Draft version number")
    quality_report: Optional[ContentQualityReport] = Field(default=None, description="Quality audit report from Stage 7")


class ContentBundle(BaseModel):
    """Collection of multiple platform-adapted content pieces derived from a single ResearchBrief."""

    bundle_id: str = Field(..., description="Unique identifier for this multi-format content bundle")
    brief_id: str = Field(..., description="ID of originating ResearchBrief")
    topic: str = Field(..., description="Target research topic")
    source_strategy: ContentStrategy = Field(..., description="Originating base ContentStrategy")
    pieces: Dict[str, ContentPiece] = Field(default_factory=dict, description="Map of format_id to generated ContentPiece")
    created_at: datetime = Field(default_factory=datetime.now, description="Timestamp of bundle creation")

    def get_piece(self, format_id: str) -> Optional[ContentPiece]:
        """Retrieves a specific content piece by format_id."""
        return self.pieces.get(format_id)
