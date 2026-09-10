from core.research_plan import ResearchPlan, ResearchQuestion


class ResearchPlanner:
    """Planner component that generates a structured ResearchPlan from a user request.

    Currently uses deterministic placeholder logic which can be easily swapped with an LLM.
    """

    def __init__(self, max_iterations: int = 3) -> None:
        self.max_iterations = max_iterations

    def create_plan(self, user_request: str) -> ResearchPlan:
        """Generates a validated ResearchPlan for the given user request."""
        clean_topic = user_request.strip()
        if not clean_topic:
            raise ValueError("User request/topic cannot be empty.")

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

        questions = [q1, q2, q3]
        all_queries = [query for q in questions for query in q.search_queries]

        goals = [
            f"Understand foundational concepts of {clean_topic}",
            f"Analyze major trends, advantages, and challenges regarding {clean_topic}",
            f"Collect verified evidence and case studies on {clean_topic}",
        ]

        return ResearchPlan(
            topic=clean_topic,
            goals=goals,
            questions=questions,
            search_queries=all_queries,
            max_iterations=self.max_iterations,
        )
