from typing import Optional, Union
from pydantic import ValidationError

from core.request_intent import RequestIntent, RequestInterpreter, UserRequest
from core.research_plan import (
    ContrarianProbe,
    ResearchHypothesis,
    ResearchPlan,
    ResearchQuestion,
    StoppingCriteria,
)
from tools.llm_client import GeminiClient


class ResearchPlanner:
    """Planner component that generates a structured ResearchPlan from a user request or RequestIntent.

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
        self.interpreter = RequestInterpreter(llm_client=llm_client, use_llm=use_llm)

    def create_plan(
        self, user_request: Union[str, UserRequest, RequestIntent]
    ) -> ResearchPlan:
        """Generates a validated ResearchPlan for the given user request or intent."""
        if isinstance(user_request, RequestIntent):
            intent = user_request
        elif isinstance(user_request, UserRequest):
            intent = self.interpreter.interpret(user_request)
        elif isinstance(user_request, str):
            clean = user_request.strip()
            if not clean:
                raise ValueError("User request/topic cannot be empty.")
            req = UserRequest(raw_prompt=clean)
            intent = self.interpreter.interpret(req)
        else:
            raise ValueError(f"Unsupported request type: {type(user_request)}")

        if self.use_llm:
            return self._create_plan_with_llm(intent)
        else:
            return self._create_deterministic_plan(intent)

    def _create_plan_with_llm(self, intent: RequestIntent) -> ResearchPlan:
        client = self.llm_client or GeminiClient()
        schema_dict = ResearchPlan.model_json_schema()

        prompt_str = (
            f"User Raw Prompt: \"{intent.proposition or intent.subject}\"\n"
            f"Parsed Subject: {intent.subject}\n"
            f"Intent Type: {intent.intent_type}\n"
            f"Proposition / Claim: {intent.proposition or 'None'}\n"
            f"Research Goal: {intent.research_goal}\n"
            f"Key Entities: {', '.join(intent.key_entities) if intent.key_entities else 'None'}\n"
            f"Key Concepts: {', '.join(intent.key_concepts) if intent.key_concepts else 'None'}\n\n"
            "INSTRUCTIONS:\n"
            "1. Generate research questions and search queries derived from the parsed Subject, Entities, Concepts, and Research Goal.\n"
            "2. The user's framing (proposition) is CREATIVE DIRECTION: it tells you what content they want (critical content, explanation, etc.). Build queries that gather the best raw material to support that direction AND honest counterpoints — do not treat the framing as a scientific truth claim to adjudicate.\n"
            "3. DO NOT use raw claims/opinions verbatim as literal search query strings.\n"
            "4. Research questions should also enrich the content landscape view: what angles, hooks, and arguments already exist about the subject, and what is underserved.\n"
            f"Required JSON Schema:\n{schema_dict}\n"
        )

        try:
            raw_json = client.generate_json_plan(prompt_str, schema_dict)
        except Exception as err:
            print(f"[Notice] Gemini API unavailable or failed ({err}); falling back to deterministic plan.")
            return self._create_deterministic_plan(intent)

        try:
            plan = ResearchPlan.model_validate_json(raw_json)
            plan.request_intent = intent
            return plan
        except (ValidationError, Exception) as err:
            raise ValueError(f"Failed to parse Gemini response into a valid ResearchPlan: {err}") from err


    def _create_deterministic_plan(self, intent: RequestIntent) -> ResearchPlan:
        """Generates a deterministic placeholder ResearchPlan without external API calls."""
        subject = intent.subject
        intent_type = intent.intent_type
        claim = intent.proposition

        if intent_type == "claim_investigation" or intent_type == "critique":
            q1 = ResearchQuestion(
                id="rq-1",
                question=f"What documented actions, decisions, or events relate to {subject}?",
                rationale="Establish documented baseline facts regarding the subject.",
                priority=1,
                search_queries=[
                    f"{subject} controversies documented decisions",
                    f"{subject} key actions track record",
                ],
            )
            q2 = ResearchQuestion(
                id="rq-2",
                question=f"What are the primary criticisms, evidence, or arguments regarding {subject}?",
                rationale="Gather the strongest raw material for critical content.",
                priority=2,
                search_queries=[
                    f"{subject} criticism governance controversy",
                    f"{subject} documented allegations evidence",
                ],
            )
            q3 = ResearchQuestion(
                id="rq-3",
                question=f"What evidence, context, or counter-arguments complicate or refute these criticisms?",
                rationale="Collect counterarguments so the critical content has nuance and credibility.",
                priority=3,
                search_queries=[
                    f"{subject} responses counterarguments defense",
                    f"{subject} rebuttal official statements",
                ],
            )
            q4 = ResearchQuestion(
                id="rq-4",
                question=f"Which reported claims regarding {subject} are verified facts versus interpretations or opinions?",
                rationale="Equip the writer to separate FACT / REPORTED EVENT / ALLEGATION / OPINION.",
                priority=4,
                search_queries=[
                    f"{subject} verified facts versus opinions",
                    f"{subject} primary source documents analysis",
                ],
            )
            goals = [
                f"Gather documented facts regarding {subject}",
                f"Collect the strongest documented criticisms of {subject}",
                f"Collect counterarguments and complicating context regarding {subject}",
                f"Separate verified facts from reported allegations and opinions regarding {subject}",
            ]
            questions = [q1, q2, q3, q4]
        elif intent_type == "explanation":
            q1 = ResearchQuestion(
                id="rq-1",
                question=f"What are the foundational principles and architecture of {subject}?",
                rationale="Understand fundamental mechanisms.",
                priority=1,
                search_queries=[
                    f"{subject} core principles architecture",
                    f"{subject} technical explanation overview",
                ],
            )
            q2 = ResearchQuestion(
                id="rq-2",
                question=f"How do the internal components and mechanisms of {subject} operate?",
                rationale="Analyze internal workflow and execution details.",
                priority=2,
                search_queries=[
                    f"{subject} internal mechanisms workflow",
                    f"{subject} routing algorithms execution",
                ],
            )
            q3 = ResearchQuestion(
                id="rq-3",
                question=f"What are the key advantages, tradeoffs, and limitations of {subject}?",
                rationale="Evaluate practical utility and system tradeoffs.",
                priority=3,
                search_queries=[
                    f"{subject} advantages tradeoffs benchmarks",
                    f"{subject} performance limitations",
                ],
            )
            q4 = ResearchQuestion(
                id="rq-4",
                question=f"What are real-world implementations and case studies of {subject}?",
                rationale="Gather empirical usage patterns.",
                priority=4,
                search_queries=[
                    f"{subject} real world implementation case studies",
                    f"{subject} production deployment examples",
                ],
            )
            q5 = ResearchQuestion(
                id="rq-5",
                question=f"What are future developments and optimization trends in {subject}?",
                rationale="Project upcoming technical trajectory.",
                priority=5,
                search_queries=[
                    f"{subject} future developments research trends",
                    f"{subject} optimization techniques",
                ],
            )
            goals = [
                f"Explain foundational principles of {subject}",
                f"Analyze core mechanisms and architecture of {subject}",
                f"Evaluate performance tradeoffs and limitations of {subject}",
                f"Gather practical case studies of {subject}",
                f"Outline future trends in {subject}",
            ]
        else:
            q1 = ResearchQuestion(
                id="rq-1",
                question=f"What are the core concepts and background of {subject}?",
                rationale="Establish baseline knowledge.",
                priority=1,
                search_queries=[
                    f"{subject} core concepts overview",
                    f"introduction to {subject}",
                ],
            )
            q2 = ResearchQuestion(
                id="rq-2",
                question=f"What are the primary drivers, benefits, and challenges associated with {subject}?",
                rationale="Identify key factors driving developments.",
                priority=2,
                search_queries=[
                    f"{subject} key drivers benefits challenges",
                    f"latest trends in {subject}",
                ],
            )
            q3 = ResearchQuestion(
                id="rq-3",
                question=f"What empirical evidence, data, or case studies exist regarding {subject}?",
                rationale="Gather grounded empirical evidence.",
                priority=3,
                search_queries=[
                    f"{subject} data statistics case studies",
                    f"{subject} empirical evidence examples",
                ],
            )
            q4 = ResearchQuestion(
                id="rq-4",
                question=f"What are the underlying technical or operational frameworks supporting {subject}?",
                rationale="Analyze technical mechanisms.",
                priority=4,
                search_queries=[
                    f"{subject} technical architecture frameworks",
                    f"{subject} operational mechanics",
                ],
            )
            q5 = ResearchQuestion(
                id="rq-5",
                question=f"What is the future outlook and strategic impact of {subject}?",
                rationale="Assess long-term implications.",
                priority=5,
                search_queries=[
                    f"{subject} future outlook strategic impact",
                    f"{subject} emerging developments",
                ],
            )
            goals = [
                f"Understand foundational concepts of {subject}",
                f"Analyze key drivers and challenges of {subject}",
                f"Collect empirical evidence and case studies on {subject}",
                f"Evaluate operational frameworks for {subject}",
                f"Assess future strategic outlook for {subject}",
            ]

        if intent_type in ("claim_investigation", "critique"):
            questions = [q1, q2, q3, q4]
        else:
            questions = [q1, q2, q3, q4, q5]

        h1 = ResearchHypothesis(
            id="rh-1",
            statement=f"Existing content on {subject} clusters around a few predictable angles, leaving space for original takes.",
        )
        h2 = ResearchHypothesis(
            id="rh-2",
            statement=f"Critical or popular narratives about {subject} often diverge from documented source material.",
        )
        hypotheses = [h1, h2]

        cp1 = ContrarianProbe(
            id="cp-1",
            question=f"What if prevailing assumptions about {subject} are incomplete or oversimplified?",
        )
        cp2 = ContrarianProbe(
            id="cp-2",
            question=f"Could current developments in {subject} be driven by short-term narrative rather than lasting fundamentals?",
        )
        contrarian_probes = [cp1, cp2]

        stopping_criteria = StoppingCriteria(
            max_iterations=self.max_iterations,
            min_useful_evidence=5,
            saturation_threshold=0.85,
        )

        all_queries = [query for q in questions for query in q.search_queries]

        return ResearchPlan(
            topic=intent.proposition or intent.subject,
            request_intent=intent,
            goals=goals,
            questions=questions,
            hypotheses=hypotheses,
            contrarian_probes=contrarian_probes,
            stopping_criteria=stopping_criteria,
            search_queries=all_queries,
            max_iterations=self.max_iterations,
        )


