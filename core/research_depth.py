"""Adaptive research depth — a SMALL classifier, not a reasoning subsystem.

Answers one question: how much research is actually useful for this request?
quick / standard / deep.
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ResearchDepth(BaseModel):
    """Determines research intensity based on request type, not over-engineered."""

    depth_level: Literal["quick", "standard", "deep"] = Field(
        ..., description="Research intensity level"
    )
    max_questions: int = Field(default=3, ge=1, le=8, description="Max research questions to plan")
    max_sources_per_question: int = Field(default=3, ge=1, le=8, description="Max search sources to triage per question")
    max_fetches: int = Field(default=3, ge=1, le=8, description="Max pages to fetch full text from")
    include_landscape: bool = Field(default=True, description="Whether to run content landscape retrieval/analysis")
    reasoning: str = Field(..., description="Short human-readable reason for the chosen depth")


class DepthClassifier:
    """Small deterministic classifier mapping a request intent to a ResearchDepth."""

    def classify(self, intent: Optional["object"] = None, prompt: str = "") -> ResearchDepth:
        intent_type = getattr(intent, "intent_type", None) if intent is not None else None
        subject = (getattr(intent, "subject", "") or "").lower()
        prompt_l = prompt.lower()
        proposition = (getattr(intent, "proposition", None) or "").lower()

        # Deep: comparative deep-dives, controversial/critical figures, "secretly/critically"
        deep_signals = (
            intent_type in ("comparison",)
            or "secretly" in proposition
            or "deeply researched" in prompt_l
            or ("agent" in subject and "architecture" in prompt_l)
            or "controversial" in prompt_l
            or ("why" in proposition and any(
                w in proposition for w in ("evil", "sucks", "shady", "overrated", "scam")))
        )
        if deep_signals and "explain" not in prompt_l[:12]:
            return ResearchDepth(
                depth_level="deep",
                max_questions=5,
                max_sources_per_question=5,
                max_fetches=5,
                include_landscape=True,
                reasoning="Controversial/comparative request requiring careful, broad research.",
            )

        # Quick: simple explanation / how-to of a well-defined concept
        quick_signals = (
            (intent_type == "explanation" or prompt_l.startswith("what is ") or prompt_l.startswith("how does "))
            and len(prompt_l.split()) <= 3
        )
        if quick_signals:
            return ResearchDepth(
                depth_level="quick",
                max_questions=2,
                max_sources_per_question=2,
                max_fetches=2,
                include_landscape=False,
                reasoning="Simple well-scoped explanation; minimal research needed.",
            )

        # Standard: everything else — normal content creation research
        return ResearchDepth(
            depth_level="standard",
            max_questions=3,
            max_sources_per_question=3,
            max_fetches=3,
            include_landscape=True,
            reasoning="Standard content request; balanced research plus content landscape.",
        )