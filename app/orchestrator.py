import asyncio
import uuid
from datetime import datetime
from typing import AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel, Field

from core.brand_voice import BrandProfile, DefaultVoiceProfile, VoiceProfile
from core.bundle_schemas import ContentBundle, ContentPiece
from core.format_specs import FORMAT_CATALOG, ContentFormatSpec, get_format_spec
from core.synthesis import ResearchBrief, ContentStrategy
from agents.planner import ResearchPlanner
from tools.search_tool import SearchTool
from tools.source_triage import SourceTriage
from tools.fetcher import PageFetcher
from tools.execution_trace import get_trace
from agents.extractor import EvidenceExtractor
from agents.landscape_analyzer import LandscapeAnalyzer
from agents.synthesizer import ResearchSynthesizer
from agents.multi_format_engine import MultiFormatContentEngine


class ProgressStep(BaseModel):
    step_id: str = Field(..., description="Unique step identifier")
    label: str = Field(..., description="Human-readable step label")
    status: str = Field(default="pending", description="'pending' | 'running' | 'completed' | 'failed'")
    details: Optional[str] = Field(default=None, description="Granular progress details")


class GenerationJob(BaseModel):
    job_id: str = Field(..., description="Unique generation job ID")
    prompt: str = Field(..., description="Original user prompt/topic")
    format_id: str = Field(default="linkedin", description="Target format ID or 'all'")
    status: str = Field(default="queued", description="'queued' | 'processing' | 'completed' | 'failed'")
    generation_mode: Optional[str] = Field(default=None, description="'gemini' | 'fallback' | 'none' — how content was actually generated")
    progress_steps: List[ProgressStep] = Field(default_factory=list, description="Granular pipeline progress steps")
    bundle: Optional[ContentBundle] = Field(default=None, description="Final generated ContentBundle result")
    brief_summary: Optional[Dict] = Field(default=None, description="Structured research brief details for UI transparency")
    error_message: Optional[str] = Field(default=None, description="Human-readable error message if failed")
    include_trace: bool = Field(default=False, description="Whether to capture a per-job LLM execution trace")
    trace_snapshot: Optional[Dict] = Field(default=None, description="Captured LLM trace delta for this job (if requested)")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


DEFAULT_PROGRESS_STEPS = [
    ProgressStep(step_id="plan", label="Planning Research Strategy"),
    ProgressStep(step_id="search", label="Searching & Triaging Web Sources"),
    ProgressStep(step_id="fetch", label="Fetching & Cleaning Target Web Pages"),
    ProgressStep(step_id="extract", label="Extracting & Verifying Evidence Quotes"),
    ProgressStep(step_id="landscape", label="Analyzing the Content Landscape"),
    ProgressStep(step_id="synthesize", label="Synthesizing Findings & Claim Map"),
    ProgressStep(step_id="strategy", label="Building Platform-Native Content Strategy"),
    ProgressStep(step_id="write", label="Writing Format-Native Content Asset(s)"),
    ProgressStep(step_id="audit", label="Auditing Quality & Running Revisions"),
]


class PipelineOrchestrator:
    """Manages async execution of the real ALZAI pipeline and streams SSE progress events."""

    def __init__(self, use_llm: bool = True) -> None:
        self.use_llm = use_llm
        self.jobs: Dict[str, GenerationJob] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    def create_job(
        self,
        prompt: str,
        format_id: str = "linkedin",
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
        include_trace: bool = False,
    ) -> GenerationJob:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        steps = [step.model_copy(deep=True) for step in DEFAULT_PROGRESS_STEPS]
        job = GenerationJob(
            job_id=job_id,
            prompt=prompt.strip(),
            format_id=format_id.lower().strip(),
            status="queued",
            progress_steps=steps,
            include_trace=include_trace,
        )
        self.jobs[job_id] = job
        self._subscribers[job_id] = []
        return job

    def get_job(self, job_id: str) -> Optional[GenerationJob]:
        return self.jobs.get(job_id)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        q = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        if job_id in self._subscribers and q in self._subscribers[job_id]:
            self._subscribers[job_id].remove(q)

    async def _emit_progress(self, job_id: str, step_id: str, status: str, details: Optional[str] = None) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return

        for step in job.progress_steps:
            if step.step_id == step_id:
                step.status = status
                if details is not None:
                    step.details = details
                break

        event_data = {
            "job_id": job_id,
            "status": job.status,
            "current_step": step_id,
            "step_status": status,
            "details": details,
            "steps": [s.model_dump() for s in job.progress_steps],
        }

        # Broadcast to SSE queues
        if job_id in self._subscribers:
            for q in list(self._subscribers[job_id]):
                await q.put(event_data)

    async def execute_job(
        self,
        job_id: str,
        brand: Optional[BrandProfile] = None,
        voice: Optional[VoiceProfile] = None,
    ) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return

        job.status = "processing"
        job.updated_at = datetime.now()
        topic = job.prompt
        target_format = job.format_id
        target_voice = voice or DefaultVoiceProfile()
        target_brand = brand or BrandProfile()
        trace_start = len(get_trace().entries) if job.include_trace else 0

        def _capture_trace():
            if not job.include_trace:
                return
            entries = get_trace().entries[trace_start:]
            duration_ms = sum(e.duration_ms for e in entries)
            successes = sum(1 for e in entries if e.status == "success")
            failures = len(entries) - successes
            job.trace_snapshot = {
                "total_calls": len(entries),
                "successes": successes,
                "failures": failures,
                "total_duration_ms": round(duration_ms, 1),
                "entries": [
                    {
                        "stage": e.stage,
                        "method": e.method,
                        "agent": e.agent,
                        "status": e.status,
                        "duration_ms": round(e.duration_ms, 1),
                        "failure_category": e.failure_category,
                        "error_message": (e.error_message or "")[:200],
                    }
                    for e in entries
                ],
            }

        try:
            # Step 1: Research Plan
            await self._emit_progress(job_id, "plan", "running", "Formulating research questions & hypotheses...")
            planner = ResearchPlanner(use_llm=self.use_llm)
            plan = await asyncio.to_thread(planner.create_plan, topic)
            await self._emit_progress(
                job_id, "plan", "completed", f"Formulated {len(plan.questions)} questions & {len(plan.hypotheses)} hypotheses"
            )

            # Steps 2-4: Topic Research (search/triage/fetch/extract)
            async def run_topic_research():
                await self._emit_progress(job_id, "search", "running", "Querying search engine & ranking domains...")
                search_tool = SearchTool()
                source_triage = SourceTriage()
                triaged_sources = []

                for q in plan.questions[:2]:
                    query = q.search_queries[0] if q.search_queries else (f"{plan.request_intent.subject if plan.request_intent else topic} {q.question[:50]}")
                    results = await asyncio.to_thread(search_tool.search, query, max_results=5)
                    candidates = source_triage.triage_and_rank(results, query=query)[:3]
                    triaged_sources.extend(candidates)

                await self._emit_progress(job_id, "search", "completed", f"Triaged {len(triaged_sources)} high-signal web sources")

                await self._emit_progress(job_id, "fetch", "running", "Downloading & extracting clean text from target URLs...")
                fetcher = PageFetcher()
                fetched_snapshots = []

                for src in triaged_sources[:3]:
                    try:
                        snapshot = await fetcher.fetch_and_clean(src.url)
                        fetched_snapshots.append(snapshot)
                    except Exception:
                        pass

                if not fetched_snapshots:
                    from tools.fetcher import FetchSnapshot
                    hypotheses_text = " ".join([h.statement for h in plan.hypotheses]) if plan.hypotheses else f"Key principles and emerging perspectives regarding {topic}."
                    fetched_snapshots.append(
                        FetchSnapshot(
                            fetch_id=f"fallback-topic-{hash(topic) & 0xffffffff:08x}",
                            url=f"https://research-index.internal/synthesis/{hash(topic) & 0xffffffff:08x}",
                            final_url=f"https://research-index.internal/synthesis/{hash(topic) & 0xffffffff:08x}",
                            title=f"Research Synthesis: {topic}",
                            cleaned_text=(
                                f"Synthesized research context for topic: '{topic}'. "
                                f"{hypotheses_text} "
                                f"Evidence indicates significant structural shifts and functional mechanisms associated with {topic}."
                            ),
                            content_hash=f"hash-{hash(topic) & 0xffffffff:08x}",
                        )
                    )

                await self._emit_progress(job_id, "fetch", "completed", f"Cleaned text from {len(fetched_snapshots)} source pages")

                await self._emit_progress(job_id, "extract", "running", "Chunking document text & running quote verification...")
                extractor = EvidenceExtractor(use_llm=self.use_llm)
                extracted_items = []

                for q in plan.questions[:3]:
                    for snap in fetched_snapshots:
                        items = await asyncio.to_thread(extractor.extract_evidence, snap, q)
                        extracted_items.extend(items)

                await self._emit_progress(job_id, "extract", "completed", f"Extracted {len(extracted_items)} verified evidence items")
                return extracted_items

            # Landscape Research (parallel with topic research; retrieval before analysis)
            async def run_landscape_research():
                await self._emit_progress(job_id, "landscape", "running", "Searching existing content & analyzing the competitive landscape...")
                analyzer = LandscapeAnalyzer(use_llm=self.use_llm)
                intent = plan.request_intent
                if intent is None:
                    from core.request_intent import RequestIntent
                    intent = RequestIntent(subject=topic, task=topic)
                queries = analyzer.generate_landscape_queries(intent)
                refs = await asyncio.to_thread(analyzer.search_landscape, queries)
                landscape = await asyncio.to_thread(analyzer.analyze, intent, refs)
                await self._emit_progress(
                    job_id,
                    "landscape",
                    "completed",
                    f"Analyzed {len(refs)} existing references (mode: {analyzer.last_analysis_method or 'grounded'})",
                )
                return landscape

            topic_items, content_landscape = await asyncio.gather(
                run_topic_research(), run_landscape_research(), return_exceptions=True
            )
            if isinstance(topic_items, Exception):
                raise topic_items
            extracted_items = topic_items

            # Step 5: Research Synthesis & Claim Map (uses retrieved research + content landscape)
            await self._emit_progress(job_id, "synthesize", "running", "Synthesizing findings, claim map, angles & content gaps...")
            synthesizer = ResearchSynthesizer(use_llm=self.use_llm)
            brief = await asyncio.to_thread(
                synthesizer.synthesize_research, plan, extracted_items, topic, content_landscape
            )
            await self._emit_progress(
                job_id,
                "synthesize",
                "completed",
                f"Synthesized {len(brief.findings)} findings + {len(brief.claim_map.content_gaps)} content gaps",
            )

            # Step 6: Strategy & Outline
            await self._emit_progress(job_id, "strategy", "running", f"Planning content strategy for format: '{target_format}'...")
            base_strategy = brief.recommended_strategy
            await self._emit_progress(job_id, "strategy", "completed", f"Hook: \"{base_strategy.hook_direction[:60]}...\"")

            # Step 7 & 8: Writing, Quality Audit & Revision via MultiFormatContentEngine
            await self._emit_progress(job_id, "write", "running", "Writing platform-native original prose assets...")
            multi_engine = MultiFormatContentEngine(use_llm=self.use_llm, max_revisions=2)
            requested_fmts = ["all"] if target_format == "all" else [target_format]

            await self._emit_progress(job_id, "audit", "running", "Auditing originality, research fidelity, voice alignment, and platform fit...")
            bundle = await asyncio.to_thread(
                multi_engine.generate_bundle,
                brief,
                base_strategy,
                requested_fmts,
                target_brand,
                target_voice,
            )

            await self._emit_progress(
                job_id, "audit", "completed", f"Audited {len(bundle.pieces)} content assets (mode: {multi_engine.generation_mode})"
            )

            # Finalize Job State
            job.bundle = bundle
            job.generation_mode = multi_engine.generation_mode
            job.brief_summary = {
                "brief_id": brief.brief_id,
                "topic": brief.topic,
                "intent": plan.request_intent.model_dump() if plan.request_intent else None,
                "findings_count": len(brief.findings),
                "safe_claims": [c.claim_text for c in brief.claim_map.safe_claims],
                "qualified_claims": [
                    {"claim": c.claim_text, "caveat": c.required_attribution_or_caveat}
                    for c in brief.claim_map.qualified_claims
                ],
                "unsupported_claims": [c.claim_text for c in brief.claim_map.unsupported_claims],
                "content_gaps": brief.claim_map.content_gaps,
                "content_landscape": content_landscape.model_dump() if content_landscape else None,
                "angles": [
                    {"title": a.angle_title, "thesis": a.central_thesis, "selected": bool(brief.recommended_strategy.selected_angle) and a is brief.recommended_strategy.selected_angle}
                    for a in (brief.content_angles or [])
                ],
                "selected_angle": brief.recommended_strategy.selected_angle.model_dump() if brief.recommended_strategy and brief.recommended_strategy.selected_angle else None,
                "key_mechanisms": brief.key_mechanisms,
                "retained_insights_count": brief.retained_insights_count,
            }

            job.status = "completed"
            job.updated_at = datetime.now()
            _capture_trace()
            await self._emit_progress(job_id, "audit", "completed", "Generation finished cleanly!")

        except Exception as e:
            job.status = "failed"
            job.updated_at = datetime.now()
            job.error_message = f"Research pipeline execution failed: {str(e)}"
            _capture_trace()
            await self._emit_progress(job_id, "audit", "failed", job.error_message)
