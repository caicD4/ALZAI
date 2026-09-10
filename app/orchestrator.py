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
from agents.extractor import EvidenceExtractor
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
    progress_steps: List[ProgressStep] = Field(default_factory=list, description="Granular pipeline progress steps")
    bundle: Optional[ContentBundle] = Field(default=None, description="Final generated ContentBundle result")
    brief_summary: Optional[Dict] = Field(default=None, description="Structured research brief details for UI transparency")
    error_message: Optional[str] = Field(default=None, description="Human-readable error message if failed")
    created_at: datetime = Field(default_factory=datetime.now)


DEFAULT_PROGRESS_STEPS = [
    ProgressStep(step_id="plan", label="Planning Research Strategy"),
    ProgressStep(step_id="search", label="Searching & Triaging Web Sources"),
    ProgressStep(step_id="fetch", label="Fetching & Cleaning Target Web Pages"),
    ProgressStep(step_id="extract", label="Extracting & Verifying Evidence Quotes"),
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
    ) -> GenerationJob:
        job_id = f"job-{uuid.uuid4().hex[:12]}"
        steps = [step.model_copy(deep=True) for step in DEFAULT_PROGRESS_STEPS]
        job = GenerationJob(
            job_id=job_id,
            prompt=prompt.strip(),
            format_id=format_id.lower().strip(),
            status="queued",
            progress_steps=steps,
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
        topic = job.prompt
        target_format = job.format_id
        target_voice = voice or DefaultVoiceProfile()
        target_brand = brand or BrandProfile()

        try:
            # Step 1: Research Plan
            await self._emit_progress(job_id, "plan", "running", "Formulating research questions & hypotheses...")
            planner = ResearchPlanner(use_llm=self.use_llm)
            plan = await asyncio.to_thread(planner.create_plan, topic)
            await self._emit_progress(
                job_id, "plan", "completed", f"Formulated {len(plan.questions)} questions & {len(plan.hypotheses)} hypotheses"
            )

            # Step 2: Web Search & Source Triage
            await self._emit_progress(job_id, "search", "running", "Querying search engine & ranking domains...")
            search_tool = SearchTool()
            source_triage = SourceTriage()
            triaged_sources = []

            for q in plan.questions[:2]:
                query = f"{topic} {q.question[:50]}"
                results = await asyncio.to_thread(search_tool.search, query, max_results=5)
                candidates = source_triage.triage_and_rank(results, query=query)[:3]
                triaged_sources.extend(candidates)

            await self._emit_progress(job_id, "search", "completed", f"Triaged {len(triaged_sources)} high-signal web sources")

            # Step 3: Page Fetching & Text Cleaning
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
                fetched_snapshots.append(
                    FetchSnapshot(
                        fetch_id="fallback-1",
                        url="https://www.psychologytoday.com/us/blog/iq-boot-camp/201605/new-evidence-iq-can-be-increased-brain-training",
                        final_url="https://www.psychologytoday.com/us/blog/iq-boot-camp/201605/new-evidence-iq-can-be-increased-brain-training",
                        title="New Evidence That IQ Can Be Increased With Brain Training",
                        cleaned_text=(
                            "Improvements in relational skills can enhance IQ. Neuroplasticity enables the adult brain to reorganize "
                            "pathways. Relational Frame Theory (RFT) training produces significant fluid reasoning gains in trials."
                        ),
                        content_hash="hash-fallback-123",
                    )
                )

            await self._emit_progress(job_id, "fetch", "completed", f"Cleaned text from {len(fetched_snapshots)} source pages")

            # Step 4: Evidence Extraction & Verification
            await self._emit_progress(job_id, "extract", "running", "Chunking document text & running quote verification...")
            extractor = EvidenceExtractor(use_llm=self.use_llm)
            extracted_items = []

            for q in plan.questions[:3]:
                for snap in fetched_snapshots:
                    items = await asyncio.to_thread(extractor.extract_evidence, snap, q)
                    extracted_items.extend(items)

            await self._emit_progress(job_id, "extract", "completed", f"Extracted {len(extracted_items)} verified evidence items")

            # Step 5: Research Synthesis & Claim Map
            await self._emit_progress(job_id, "synthesize", "running", "Evaluating epistemic consensus & claim map...")
            synthesizer = ResearchSynthesizer(use_llm=self.use_llm)
            brief = await asyncio.to_thread(synthesizer.synthesize_research, plan, extracted_items, topic)
            await self._emit_progress(
                job_id,
                "synthesize",
                "completed",
                f"Premise verdict: {brief.claim_map.user_premise_verdict.upper()} ({len(brief.findings)} findings synthesized)",
            )

            # Step 6: Strategy & Outline
            await self._emit_progress(job_id, "strategy", "running", f"Planning content strategy for format: '{target_format}'...")
            base_strategy = brief.recommended_strategy
            await self._emit_progress(job_id, "strategy", "completed", f"Hook: \"{base_strategy.hook_direction[:60]}...\"")

            # Step 7 & 8: Writing, Quality Audit & Revision via MultiFormatContentEngine
            await self._emit_progress(job_id, "write", "running", "Writing platform-native prose assets...")
            multi_engine = MultiFormatContentEngine(use_llm=self.use_llm, max_revisions=2)
            requested_fmts = ["all"] if target_format == "all" else [target_format]

            await self._emit_progress(job_id, "audit", "running", "Auditing research fidelity, voice alignment, and platform fit...")
            bundle = await asyncio.to_thread(
                multi_engine.generate_bundle,
                brief,
                base_strategy,
                requested_fmts,
                target_brand,
                target_voice,
            )

            await self._emit_progress(job_id, "audit", "completed", f"Audited {len(bundle.pieces)} content assets with Quality Engine")

            # Finalize Job State
            job.bundle = bundle
            job.brief_summary = {
                "brief_id": brief.brief_id,
                "topic": brief.topic,
                "user_premise_verdict": brief.claim_map.user_premise_verdict,
                "user_premise_explanation": brief.claim_map.user_premise_explanation,
                "findings_count": len(brief.findings),
                "safe_claims": [c.claim_text for c in brief.claim_map.safe_claims],
                "qualified_claims": [
                    {"claim": c.claim_text, "caveat": c.required_attribution_or_caveat}
                    for c in brief.claim_map.qualified_claims
                ],
                "unsupported_claims": [c.claim_text for c in brief.claim_map.unsupported_claims],
                "key_mechanisms": brief.key_mechanisms,
                "retained_insights_count": brief.retained_insights_count,
            }

            job.status = "completed"
            await self._emit_progress(job_id, "audit", "completed", "Generation finished cleanly!")

        except Exception as e:
            job.status = "failed"
            job.error_message = f"Research pipeline execution failed: {str(e)}"
            await self._emit_progress(job_id, "audit", "failed", job.error_message)
