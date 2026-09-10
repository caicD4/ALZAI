import asyncio
import sys

# Ensure UTF-8 output encoding for Windows command line terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from agents import (
    ContentOutliner,
    ContentVerifier,
    EvidenceExtractor,
    HumanBrandVoiceWriter,
    ResearchPlanner,
    ResearchSynthesizer,
    TargetedRevisionWorker,
)
from config.gemini_config import is_api_key_available, load_environment
from core import BrandProfile, DefaultVoiceProfile
from core.evidence import FetchSnapshot
from tools.fetcher import PageFetcher
from tools.quote_verifier import verify_quote
from tools.search_tool import SearchTool
from tools.source_triage import SourceTriage




async def run_pipeline_demo(topic: str) -> None:
    load_environment()
    use_llm = is_api_key_available()

    print("============================================================")
    print("      CONTENT RESEARCH AGENT - PIPELINE DEMONSTRATION       ")
    print("============================================================")
    print(f"Topic: '{topic}'")
    print(f"LLM Mode: {'Gemini 3.6 Flash (.env loaded)' if use_llm else 'Deterministic Offline Mode'}")
    print("============================================================\n")

    # 1. Research Planning Stage
    print("--- [STAGE 1] GENERATING RESEARCH PLAN ---")
    planner = ResearchPlanner(max_iterations=3, use_llm=use_llm)
    plan = planner.create_plan(topic)

    print(f"Plan Goals ({len(plan.goals)}):")
    for g in plan.goals[:3]:
        print(f"  - {g}")

    print(f"\nResearch Questions ({len(plan.questions)}):")
    for q in plan.questions[:3]:
        print(f"  [{q.id}] (Priority {q.priority}) {q.question}")

    print(f"\nHypotheses ({len(plan.hypotheses)}):")
    for h in plan.hypotheses:
        print(f"  [{h.id}] {h.statement}")

    print(f"\nContrarian Probes ({len(plan.contrarian_probes)}):")
    for cp in plan.contrarian_probes:
        print(f"  [{cp.id}] {cp.question}")

    # 2. Search & Triage Stage
    seed_query = plan.search_queries[0] if plan.search_queries else f"{topic} overview"
    print(f"\n--- [STAGE 2] WEB SEARCH & SOURCE TRIAGE ---")
    print(f"Executing Search Query: '{seed_query}'")

    search_tool = SearchTool()
    raw_results = search_tool.search(seed_query, max_results=5)
    print(f"Raw Search Results Found: {len(raw_results)}")

    triage = SourceTriage(max_per_domain=1)
    triaged_candidates = triage.triage_and_rank(raw_results)
    print(f"Triaged & Ranked Candidates ({len(triaged_candidates)}):")
    for res in triaged_candidates:
        print(f"  - [{res.domain}] (Rank {res.rank}) {res.title}")
        print(f"    URL: {res.url}")

    # 3. Page Fetching & Text Cleaning Stage
    print(f"\n--- [STAGE 3] PAGE FETCHING & TEXT CLEANING ---")
    fetcher = PageFetcher()
    valid_snapshots: List[FetchSnapshot] = []

    for candidate in triaged_candidates:
        print(f"Attempting Fetch Target: {candidate.url}")
        try:
            snapshot = await fetcher.fetch_and_clean(candidate.url)
            # Check if page is readable content rather than JS challenge / paywall block
            if snapshot and snapshot.cleaned_text and len(snapshot.cleaned_text) > 400 and "browser settings" not in snapshot.cleaned_text.lower():
                print(f"  Fetch Successful!")
                print(f"  Fetch ID: {snapshot.fetch_id}")
                print(f"  Final URL: {snapshot.final_url}")
                print(f"  Content Hash (SHA-256): {snapshot.content_hash[:16]}...")
                print(f"  Extracted Title: {snapshot.title or candidate.title}")
                print(f"  Cleaned Text Length: {len(snapshot.cleaned_text)} characters")
                print(f"  Sample Text Snippet: \"{snapshot.cleaned_text[:200]}...\"")
                valid_snapshots.append(snapshot)
                if len(valid_snapshots) >= 2:
                    break
            else:
                print(f"  Fetch Skipped (Insufficient readable text or JS challenge block, length={len(snapshot.cleaned_text) if snapshot else 0})")
        except Exception as err:
            print(f"  Fetch Attempt Failed ({type(err).__name__}: {err})")

    # 4. Evidence Extraction & Deterministic Verification Stage
    print(f"\n--- [STAGE 4] EVIDENCE EXTRACTION & VERIFICATION WORKER ---")
    if not valid_snapshots:
        print("  No readable snapshots fetched from live web; using fallback snapshot.")
        fallback_text = (
            "According to a 2023 survey by Gartner, 70-85% of enterprise AI projects fail "
            "to deliver on their initial business objectives. The primary causes cited include "
            "poor data quality and lack of executive alignment. Additionally, OpenAI reported "
            "that smaller specialized models achieve 95% accuracy compared to generic LLMs."
        )
        valid_snapshots.append(
            FetchSnapshot(
                fetch_id="fetch-demo-fallback",
                url="https://example.com/demo-ai-report",
                final_url="https://example.com/demo-ai-report",
                title="Enterprise AI ROI & Benchmarks Report",
                cleaned_text=fallback_text,
                content_hash="demo-hash-12345",
            )
        )

    extractor = EvidenceExtractor(use_llm=use_llm)
    all_extracted_items: List[EvidenceItem] = []

    # Process all research questions against fetched snapshots
    questions_to_process = plan.questions[:3] if plan.questions else []
    for q in questions_to_process:
        print(f"\nProcessing Target Question [{q.id}]: {q.question}")
        q_items_count = 0
        for snapshot in valid_snapshots:
            items = extractor.extract_evidence(snapshot, q)
            for item in items:
                all_extracted_items.append(item)
                q_items_count += 1
        print(f"  -> Extracted {q_items_count} verified evidence items for Question [{q.id}]")

    print(f"\nTOTAL VERIFIED EVIDENCE ITEMS EXTRACTED: {len(all_extracted_items)}")

    # 5. Research Synthesis & Content Strategy Stage
    print(f"\n--- [STAGE 5] RESEARCH SYNTHESIS & CONTENT STRATEGY ---")
    synthesizer = ResearchSynthesizer(use_llm=use_llm)
    brief = synthesizer.synthesize_research(plan, all_extracted_items, topic)

    print(f"\nInsight Processing Metrics:")
    print(f"  - Total Raw Insights: {brief.total_raw_insights}")
    print(f"  - Retained Relevant Insights: {brief.retained_insights_count}")
    print(f"  - Rejected Off-Topic Insights: {brief.rejected_insights_count}")

    print(f"\nSynthesized Findings ({len(brief.findings)}):")
    for f in brief.findings:
        print(f"  - [{f.status.upper()}] {f.statement}")
        print(f"    Reasoning: {f.reasoning}")
        print(f"    Independent Sources: {f.independent_sources_count} (Total Insights: {f.source_count})")

    print(f"\nClaim Map Evaluation:")
    print(f"  User Premise Verdict: {brief.claim_map.user_premise_verdict.upper()}")
    print(f"  User Premise Explanation: {brief.claim_map.user_premise_explanation}")
    
    if brief.claim_map.safe_claims:
        print(f"\n  Safe Claims ({len(brief.claim_map.safe_claims)}):")
        for sc in brief.claim_map.safe_claims:
            print(f"    ✓ {sc.claim_text}")
    if brief.claim_map.qualified_claims:
        print(f"\n  Qualified Claims ({len(brief.claim_map.qualified_claims)}):")
        for qc in brief.claim_map.qualified_claims:
            print(f"    ⚠ {qc.claim_text}")
            if qc.required_attribution_or_caveat:
                print(f"      Caveat: {qc.required_attribution_or_caveat}")
    if brief.claim_map.unsupported_claims:
        print(f"\n  Unsupported Claims ({len(brief.claim_map.unsupported_claims)}):")
        for uc in brief.claim_map.unsupported_claims:
            print(f"    ✗ {uc.claim_text}")
    if brief.claim_map.contradicted_claims:
        print(f"\n  Contradicted Claims ({len(brief.claim_map.contradicted_claims)}):")
        for cc in brief.claim_map.contradicted_claims:
            print(f"    ⛔ {cc.claim_text}")

    if brief.key_mechanisms:
        print(f"\nKey Mechanisms Identified:")
        for mech in brief.key_mechanisms:
            print(f"  - {mech}")

    if brief.research_gaps:
        print(f"\nResearch Gaps Identified:")
        for gap in brief.research_gaps:
            print(f"  - {gap}")

    print(f"\nGenerated Content Angles ({len(brief.content_angles)}):")
    for angle in brief.content_angles:
        print(f"  - [{angle.suitable_platform}] \"{angle.angle_title}\"")
        print(f"    Thesis: {angle.central_thesis}")
        print(f"    Why Interesting: {angle.why_interesting}")

    strat = brief.recommended_strategy
    print(f"\nRecommended Content Strategy:")
    print(f"  Platform: {strat.platform} ({strat.content_type})")
    print(f"  Audience: {strat.audience}")
    print(f"  Objective: {strat.objective}")
    print(f"  Hook Direction: \"{strat.hook_direction}\"")
    print(f"  Key Points:")
    for kp in strat.key_points:
        print(f"    • {kp}")
    if strat.claims_to_avoid:
        print(f"  Claims to Avoid:")
        for cta in strat.claims_to_avoid:
            print(f"    • {cta}")
    print(f"  Desired Takeaway: {strat.desired_takeaway}")

    # 6. Content Outliner, Human Brand Voice Writer, Verifier & Targeted Revision Stage
    print(f"\n--- [STAGE 6] CONTENT OUTLINER, HUMAN WRITER, VERIFIER & REVISION ---")

    # A. Voice & Brand Setup
    voice_profile = DefaultVoiceProfile()
    brand_profile = BrandProfile(
        name="Cognitive Performance & AI Specialist",
        niche="Neuroscience & AI Engineering",
        audience="Tech Leaders, Researchers, and Lifelong Learners",
        positioning="Empirical, rigorous, and anti-cliché",
        topics=["Cognitive Enhancement", "Neuroplasticity", "Relational Frame Theory"],
    )

    print(f"\nWriting Style Profile:")
    print(f"  Name: {voice_profile.name} (is_default_profile={voice_profile.is_default_profile})")
    print(f"  Formality: {voice_profile.formality}")
    print(f"  Directness: {voice_profile.directness}")
    print(f"  Banned AI Clichés ({len(voice_profile.avoided_phrases)}): {', '.join(voice_profile.avoided_phrases[:4])}...")

    # B. Content Outliner
    print(f"\nGenerating Platform-Aware Content Outline ({strat.platform})...")
    outliner = ContentOutliner(use_llm=use_llm)
    outline = outliner.create_outline(brief, strat, brand=brand_profile, voice=voice_profile)

    print(f"\nContent Outline Structure:")
    print(f"  Hook Direction: \"{outline.hook_direction}\"")
    print(f"  Setup Context: {outline.setup_context}")
    print(f"  Main Points ({len(outline.main_points)}):")
    for pt in outline.main_points:
        print(f"    - [{pt.point_id}] {pt.title}")
        print(f"      Concept: {pt.key_concept}")
        if pt.example_or_mechanism:
            print(f"      Mechanism/Example: {pt.example_or_mechanism}")

    # C. Human Brand Voice Writer
    print(f"\nGenerating Prose Draft with Human Brand Voice Writer...")
    writer = HumanBrandVoiceWriter(use_llm=use_llm)
    initial_draft = writer.write_draft(brief, strat, outline, brand=brand_profile, voice=voice_profile)

    print(f"\nInitial Prose Draft Generated:")
    print(f"  Title: {initial_draft.title or 'N/A'}")
    print(f"  Word Count: {initial_draft.word_count} words")
    print(f"--- Initial Draft Body ---")
    print(initial_draft.body_text)
    print(f"--------------------------")

    # D. Content Verifier
    print(f"\nAuditing Draft with Content Verifier (Dual-Axis Verification)...")
    verifier = ContentVerifier(use_llm=use_llm)
    report = verifier.verify_draft(initial_draft, brief, strat, voice=voice_profile)

    print(f"\nVerification Report Result:")
    print(f"  Status: {'PASSED ✓' if report.is_passed else 'FAILED ✗'}")
    print(f"  Overall Style Score: {report.voice_alignment.overall_style_score:.2f} / 1.00")
    print(f"  Factual Errors ({len(report.factual_errors)}):")
    for fe in report.factual_errors:
        print(f"    - [{fe.category.upper()}] \"{fe.quote_in_draft}\" -> Fix: {fe.suggested_fix}")
    print(f"  Style Errors ({len(report.style_errors)}):")
    for se in report.style_errors:
        print(f"    - [{se.category.upper()}] \"{se.quote_in_draft}\" -> Fix: {se.suggested_fix}")

    # E. Targeted Revision Worker (Max 2 Passes)
    final_content = initial_draft
    if not report.is_passed:
        print(f"\nExecuting Targeted Revision Worker (Max 2 Passes)...")
        revision_worker = TargetedRevisionWorker(verifier=verifier, use_llm=use_llm, max_revisions=2)
        final_content, history = revision_worker.execute_targeted_revision(
            initial_draft, report, brief, strat, voice=voice_profile
        )

        print(f"\nRevision History ({len(history)} passes executed):")
        for pass_res in history:
            print(f"  Pass #{pass_res.pass_number}: Passed={pass_res.verification_report.is_passed}")
            print(f"  Fixes Applied: {len(pass_res.fixes_applied)}")
            for fix in pass_res.fixes_applied:
                print(f"    • {fix}")

    # F. Final Output Presentation
    print("\n============================================================")
    print("                 FINAL PUBLISHABLE CONTENT                  ")
    print("============================================================")
    if final_content.title:
        print(f"Headline: {final_content.title}\n")
    print(final_content.body_text)
    print("============================================================")
    print("                 DEMONSTRATION COMPLETE                     ")
    print("============================================================")



def main() -> None:
    topic = "Autonomous AI Agents in Software Engineering"
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])

    asyncio.run(run_pipeline_demo(topic))


if __name__ == "__main__":
    main()
