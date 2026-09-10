from typing import List
from pydantic import BaseModel, Field


class ResearchQuestion(BaseModel):
    """Structured representation of an individual research question."""

    id: str = Field(..., description="Unique identifier for the research question")
    question: str = Field(..., description="The core research question to investigate")
    rationale: str = Field(..., description="Why this question is relevant to the topic")
    priority: int = Field(default=1, description="Priority level (1 = highest)")
    search_queries: List[str] = Field(
        default_factory=list,
        description="Search queries generated specifically for this question",
    )


class ResearchPlan(BaseModel):
    """Structured plan for guiding the research process."""

    topic: str = Field(..., description="Original user request or topic")
    goals: List[str] = Field(..., description="Key goals of the research plan")
    questions: List[ResearchQuestion] = Field(
        ..., description="List of structured research questions to investigate"
    )
    search_queries: List[str] = Field(
        ..., description="Aggregated search queries across all questions"
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Bounded maximum number of research iterations allowed",
    )
