from agents.planner import ResearchPlanner


def main() -> None:
    planner = ResearchPlanner(max_iterations=3)
    sample_topic = "Autonomous AI Agents in Software Engineering"
    plan = planner.create_plan(sample_topic)

    print("=== Research Planner Initialized ===")
    print(f"Topic: {plan.topic}")
    print(f"Max Iterations: {plan.max_iterations}")
    print(f"Goals ({len(plan.goals)}):")
    for goal in plan.goals:
        print(f"  - {goal}")
    print(f"Questions ({len(plan.questions)}):")
    for q in plan.questions:
        print(f"  [{q.id}] (Priority {q.priority}) {q.question}")
        print(f"       Rationale: {q.rationale}")
        print(f"       Queries: {', '.join(q.search_queries)}")


if __name__ == "__main__":
    main()
