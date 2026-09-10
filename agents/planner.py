from typing import Optional
from pydantic import ValidationError

from core.research_plan import (
    ContrarianProbe,
    ResearchHypothesis,
    ResearchPlan,
    ResearchQuestion,
    StoppingCriteria,
)
from tools.llm_client import GeminiClient


class ResearchPlanner:
    """Planner component that generates a structured ResearchPlan from a user request.

    Utilizes Gemini LLM to generate research plans and validates output via Pydantic.
    Supports a deterministic fallback mode for offline testing.
    """

    def __init__(
        self,
        max_iterations: int = 3,
        use_llm: bool = True,
        llm_client: Optional[GeminiClient] = None,
    ) -> None:
        self.max_iterations = max_iterations
        self.use_llm = use_llm
        self.llm_client = llm_client

    def create_plan(self, user_request: str) -> ResearchPlan:
        """Generates a validated ResearchPlan for the given user request."""
        clean_topic = user_request.strip()
        if not clean_topic:
            raise ValueError("User request/topic cannot be empty.")

        if self.use_llm:
            return self._create_plan_with_llm(clean_topic)
        else:
            return self._create_deterministic_plan(clean_topic)

    def _create_plan_with_llm(self, topic: str) -> ResearchPlan:
        client = self.llm_client or GeminiClient()
        schema_dict = ResearchPlan.model_json_schema()

        try:
            raw_json = client.generate_json_plan(topic, schema_dict)
        except Exception as err:
            # Handle API network failure or 503 unavailability gracefully
            print(f"[Notice] Gemini API unavailable ({err}); falling back to deterministic plan.")
            return self._create_deterministic_plan(topic)

        # Parse and validate with Pydantic; fails explicitly on malformed output
        try:
            plan = ResearchPlan.model_validate_json(raw_json)
            return plan
        except (ValidationError, Exception) as err:
            raise ValueError(f"Failed to parse Gemini response into a valid ResearchPlan: {err}") from err



    def _create_deterministic_plan(self, clean_topic: str) -> ResearchPlan:
        """Generates a deterministic placeholder ResearchPlan without external API calls."""
        q1 = ResearchQuestion(
            id="rq-1",
            question=f"What are the foundational concepts and current state of {clean_topic}?",
            rationale="Establish core background knowledge and baseline understanding.",
            priority=1,
            search_queries=[
                f"{clean_topic} overview core concepts",
                f"introduction to {clean_topic}",
            ],
        )

        q2 = ResearchQuestion(
            id="rq-2",
            question=f"What are the key trends, advantages, and challenges in {clean_topic}?",
            rationale="Identify practical implications, benefits, and common obstacles.",
            priority=2,
            search_queries=[
                f"{clean_topic} key trends benefits challenges",
                f"latest developments in {clean_topic}",
            ],
        )

        q3 = ResearchQuestion(
            id="rq-3",
            question=f"What are the verifiable evidence, statistics, or case studies regarding {clean_topic}?",
            rationale="Gather empirical evidence and real-world examples for grounded writing.",
            priority=3,
            search_queries=[
                f"{clean_topic} data statistics case studies",
                f"{clean_topic} real world examples evidence",
            ],
        )

        q4 = ResearchQuestion(
            id="rq-4",
            question=f"What are the underlying technical mechanisms and structural frameworks supporting {clean_topic}?",
            rationale="Understand technical depth, architecture, and operational mechanics.",
            priority=4,
            search_queries=[
                f"{clean_topic} technical architecture mechanics",
                f"{clean_topic} underlying frameworks",
            ],
        )

        q5 = ResearchQuestion(
            id="rq-5",
            question=f"What are the future outlook, emerging risks, and strategic implications of {clean_topic}?",
            rationale="Project long-term trajectories, potential disruptions, and policy/strategic impacts.",
            priority=5,
            search_queries=[
                f"{clean_topic} future outlook strategic implications",
                f"{clean_topic} emerging risks trends",
            ],
        )

        questions = [q1, q2, q3, q4, q5]

        h1 = ResearchHypothesis(
            id="rh-1",
            statement=f"{clean_topic} significantly improves efficiency and outcome quality when implemented systematically.",
        )
        h2 = ResearchHypothesis(
            id="rh-2",
            statement=f"Adoption of {clean_topic} faces critical bottlenecks due to integration complexity and resource constraints.",
        )
        hypotheses = [h1, h2]

        cp1 = ContrarianProbe(
            id="cp-1",
            question=f"What if {clean_topic} introduces unseen systemic risks that outweigh its reported benefits?",
        )
        cp2 = ContrarianProbe(
            id="cp-2",
            question=f"Could the current enthusiasm for {clean_topic} be driven by market hype rather than measurable empirical results?",
        )
        contrarian_probes = [cp1, cp2]

        stopping_criteria = StoppingCriteria(
            max_iterations=self.max_iterations,
            min_useful_evidence=5,
            saturation_threshold=0.85,
        )

        all_queries = [query for q in questions for query in q.search_queries]

        goals = [
            f"Understand foundational concepts of {clean_topic}",
            f"Analyze major trends, advantages, and challenges regarding {clean_topic}",
            f"Collect verified evidence and case studies on {clean_topic}",
            f"Evaluate technical mechanisms and architectural frameworks for {clean_topic}",
            f"Assess future outlook and strategic implications for {clean_topic}",
        ]

        return ResearchPlan(
            topic=clean_topic,
            goals=goals,
            questions=questions,
            hypotheses=hypotheses,
            contrarian_probes=contrarian_probes,
            stopping_criteria=stopping_criteria,
            search_queries=all_queries,
            max_iterations=self.max_iterations,
        )
