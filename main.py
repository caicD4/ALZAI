from agents.planner import ResearchPlanner
from config.gemini_config import is_api_key_available


def main() -> None:
    use_llm = is_api_key_available()

    if use_llm:
        print("=== Running Gemini LLM Research Planner ===")
        print("API Key Status: Available (.env loaded)")
    else:
        print("=== Running Deterministic Offline Research Planner ===")
        print("(Set GEMINI_API_KEY in environment or .env file to enable Gemini LLM planning)")

    try:
        planner = ResearchPlanner(max_iterations=3, use_llm=use_llm)
        sample_topic = "Autonomous AI Agents in Software Engineering"
        plan = planner.create_plan(sample_topic)

        print("\n=== Generated ResearchPlan ===")
        print(f"Topic: {plan.topic}")
        print(f"Max Iterations: {plan.max_iterations}")
        print(
            f"Stopping Criteria: max_iterations={plan.stopping_criteria.max_iterations}, "
            f"min_useful_evidence={plan.stopping_criteria.min_useful_evidence}, "
            f"saturation_threshold={plan.stopping_criteria.saturation_threshold}"
        )

        print(f"\nGoals ({len(plan.goals)}):")
        for goal in plan.goals:
            print(f"  - {goal}")

        print(f"\nQuestions ({len(plan.questions)}):")
        for q in plan.questions:
            print(f"  [{q.id}] (Priority {q.priority}) {q.question}")
            print(f"       Rationale: {q.rationale}")
            print(f"       Queries: {', '.join(q.search_queries)}")

        print(f"\nHypotheses ({len(plan.hypotheses)}):")
        for h in plan.hypotheses:
            print(f"  [{h.id}] {h.statement}")

        print(f"\nContrarian Probes ({len(plan.contrarian_probes)}):")
        for cp in plan.contrarian_probes:
            print(f"  [{cp.id}] {cp.question}")

    except Exception as e:
        print("\n[ERROR] ResearchPlanner execution failed:")
        print(f"  Type: {type(e).__name__}")
        print(f"  Message: {e}")


if __name__ == "__main__":
    main()
