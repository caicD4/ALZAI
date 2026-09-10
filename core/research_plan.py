from typing import List, Optional
from pydantic import BaseModel, Field

from core.request_intent import RequestIntent


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


class ResearchHypothesis(BaseModel):
    """Represents a proposition to be investigated during research."""

    id: str = Field(..., description="Unique identifier for the hypothesis")
    statement: str = Field(..., description="The hypothesis statement to be investigated")


class ContrarianProbe(BaseModel):
    """Represents an alternative or challenging question testing consensus assumptions."""

    id: str = Field(..., description="Unique identifier for the contrarian probe")
    question: str = Field(..., description="The probe question testing alternative explanations")


class StoppingCriteria(BaseModel):
    """Conditions used by the research loop to determine when research is sufficient."""

    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Bounded maximum number of research iterations allowed",
    )
    min_useful_evidence: int = Field(
        default=5,
        ge=1,
        description="Minimum target count of useful evidence items required",
    )
    saturation_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Novelty/saturation threshold to evaluate research diminishing returns",
    )


class ResearchPlan(BaseModel):
    """Structured plan for guiding the research process."""

    topic: str = Field(..., description="Original user request or topic")
    request_intent: Optional[RequestIntent] = Field(
        default=None, description="Parsed semantic request intent guiding this plan"
    )
    goals: List[str] = Field(..., description="Key goals of the research plan")
    questions: List[ResearchQuestion] = Field(
        ..., description="List of structured research questions to investigate"
    )
    hypotheses: List[ResearchHypothesis] = Field(
        default_factory=list,
        description="Propositions to investigate during research",
    )
    contrarian_probes: List[ContrarianProbe] = Field(
        default_factory=list,
        description="Contrarian probes to test alternative viewpoints",
    )
    stopping_criteria: StoppingCriteria = Field(
        default_factory=StoppingCriteria,
        description="Stopping conditions for the research loop",
    )
    search_queries: List[str] = Field(
        default_factory=list,
        description="Aggregated search queries across all questions and probes",
    )
    max_iterations: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Bounded maximum number of research iterations allowed",
    )

