import asyncio
import json
from typing import Dict, List, Optional
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from core.format_specs import FORMAT_CATALOG, ContentFormatSpec
from core.brand_voice import BrandProfile, VoiceProfile, DefaultVoiceProfile
from app.orchestrator import GenerationJob, PipelineOrchestrator

app = FastAPI(
    title="ALZAI Content Creation API",
    description="Research-backed multi-format content creation engine API",
    version="1.0.0",
)

# Enable CORS for local development (Vite frontend on 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate global orchestrator
orchestrator = PipelineOrchestrator(use_llm=True)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Topic or research request prompt", min_length=3)
    format: str = Field(default="linkedin", description="Target format ID matching FORMAT_CATALOG or 'all'")
    brand_profile: Optional[Dict] = Field(default=None, description="Optional custom BrandProfile")
    voice_profile: Optional[Dict] = Field(default=None, description="Optional custom VoiceProfile")


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "ALZAI API Engine",
        "version": "1.0.0",
        "llm_mode": "Gemini 3.6 Flash",
    }


@app.get("/api/formats")
def get_formats():
    """Returns available content format specifications from central catalog."""
    formats_list = []
    for fid, spec in FORMAT_CATALOG.items():
        formats_list.append(spec.model_dump())
    return {
        "formats": formats_list,
        "supported_ids": list(FORMAT_CATALOG.keys()) + ["all"],
    }


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_content(req: GenerateRequest, background_tasks: BackgroundTasks):
    """Submits a research & content creation request to the ALZAI pipeline."""
    fmt = req.format.lower().strip()
    if fmt != "all" and fmt not in FORMAT_CATALOG:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format '{req.format}'. Supported: {list(FORMAT_CATALOG.keys()) + ['all']}",
        )

    # Parse optional brand or voice profiles if supplied
    brand = None
    if req.brand_profile:
        try:
            brand = BrandProfile(**req.brand_profile)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid brand_profile: {str(e)}")

    voice = None
    if req.voice_profile:
        try:
            voice = VoiceProfile(**req.voice_profile)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid voice_profile: {str(e)}")

    job = orchestrator.create_job(prompt=req.prompt, format_id=fmt, brand=brand, voice=voice)

    # Launch pipeline execution as background task
    background_tasks.add_task(orchestrator.execute_job, job.job_id, brand, voice)

    return GenerateResponse(
        job_id=job.job_id,
        status="queued",
        message="Research and content creation pipeline job started successfully.",
    )


@app.get("/api/generate/{job_id}")
def get_job_status(job_id: str):
    """Retrieves current job progress, result bundle, or error message."""
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Generation job '{job_id}' not found.")
    return job.model_dump()


@app.get("/api/generate/stream/{job_id}")
async def stream_job_progress(job_id: str):
    """Streams real-time pipeline execution progress events via Server-Sent Events (SSE)."""
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Generation job '{job_id}' not found.")

    async def sse_event_generator():
        q = orchestrator.subscribe(job_id)
        try:
            # Emit initial current job state
            initial_payload = {
                "job_id": job.job_id,
                "status": job.status,
                "steps": [s.model_dump() for s in job.progress_steps],
            }
            yield f"data: {json.dumps(initial_payload)}\n\n"

            while True:
                if job.status in ("completed", "failed"):
                    final_payload = {
                        "job_id": job.job_id,
                        "status": job.status,
                        "steps": [s.model_dump() for s in job.progress_steps],
                        "error_message": job.error_message,
                    }
                    yield f"data: {json.dumps(final_payload)}\n\n"
                    break

                try:
                    event = await asyncio.wait_for(q.get(), timeout=2.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield f": heartbeat\n\n"
        finally:
            orchestrator.unsubscribe(job_id, q)

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
