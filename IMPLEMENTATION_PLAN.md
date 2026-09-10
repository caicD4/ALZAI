# ALZAI Product Reorientation - Implementation Plan (REVISED)

## Executive Summary

Transform ALZAI from an academic evidence verification system into an **AI Content Research & Content Intelligence Engine** with a real production web app. The system understands user content requests, researches the topic AND the existing content landscape, discovers original angles, has Gemini write genuinely original content, and delivers format-native output.

**Core Principle**: The LLM is the intelligence responsible for semantic synthesis and writing. The application code is responsible for orchestration, retrieval, structure, validation, state, and reliability. Do not reverse those responsibilities.

**Ultimate Success Test**: If the user types *"why Elon Musk sucks"*, ALZAI must produce an actual interesting, readable, original piece of content about criticisms of Elon Musk. Not a refusal, not a template, not an academic summary.

---

## Required Architecture

```
USER REQUEST
      ↓
REQUEST UNDERSTANDING        (1 LLM call)
      ↓
RESEARCH PLAN
      ↓
┌──────────────────────────────────┐
│                                  │
│  TOPIC RESEARCH                  │  ← parallel: same research tooling
│  CONTENT LANDSCAPE RESEARCH      │  ← NEW: retrieves existing content
│                                  │
└──────────────────────────────────┘
      ↓
RESEARCH + CONTENT LANDSCAPE raw material
      ↓
GEMINI SYNTHESIS                 (1 LLM call)
      ↓
ANGLE DISCOVERY                  (discovered gaps → original angles)
      ↓
FORMAT STRATEGY
      ↓
GEMINI WRITER                    (1 LLM call per format)
      ↓
QUALITY CHECK                    (1 LLM call, only when useful)
      ↓
TARGETED REVISION IF NECESSARY   (0–1 LLM calls)
      ↓
FINAL CONTENT
```

**Critical constraint**: Retrieval MUST happen before semantic landscape analysis. The system cannot analyze content it has not retrieved. The LLM can PLAN what landscape material to search for, but it cannot analyze it before retrieval.

---

## Phase 1: Backend Architecture Reorientation

### 1.1 Remove PubMedGPT Academic Gates — KEEP Factual Integrity

**Remove / rework:**
- `user_premise_verdict` + `user_premise_explanation` from ClaimMap
- `_build_insufficient_evidence_brief()` blocking path in synthesizer
- "cannot safely continue" language
- Academic proof gates, consensus requirements, research requirements that prevent opinion/commentary content
- Deterministic prose templates that manufacture fake intelligence:
  - "Understanding the core operational shift..."
  - "Research reveals..."
  - "Primary evidence supports..."
  - "Real-world outcomes depend on..."
  - "Key strategic principles behind..."

**KEEP (non-negotiable):**
- No fabricated facts, statistics, quotes, sources, attribution, or events
- Quote verification and source retrieval honesty

**New distinction** — the writer must distinguish and write responsibly (without being stopped):
- FACT / REPORTED EVENT / ALLEGATION / OPINION / INTERPRETATION / PREDICTION / COMMENTARY

### 1.2 User Framing = Creative Direction (NON-NEGOTIABLE)

For *"why Sam Altman is evil"*:
- subject = Sam Altman
- stance = critical
- content intent = critical analysis/opinion
- research direction = relevant documented criticism, controversies, decisions, arguments and counterarguments
- desired output = compelling critical content

The user is telling us what CONTENT they want. Normal factual accuracy still applies, but the system must NOT convert creative direction into "*Can we establish whether Sam Altman is evil?*"

**Files:** `agents/request_intent.py` (reframe interpreter prompt + fallback), `agents/synthesizer.py`, `core/synthesis.py`

### 1.3 Research Must Be Content-Aware

Research questions are determined by the request type, not funneled through identical academic research:
| Request | Research direction |
|---|---|
| "Explain mixture of experts" | technical explanation research |
| "Why Elon Musk sucks" | criticism / controversy / content landscape research |
| "Give me a viral LinkedIn post about remote work" | topic research + landscape + audience arguments + hooks + gaps |
| "Write a funny post about AI agents" | useful facts + examples + existing content patterns + humor angle |

**Files:** `agents/planner.py`, `core/request_intent.py`

### 1.4 Adaptive Research Depth — Simple

Three levels only: `quick` / `standard` / `deep`.

| Level | When | Behavior |
|---|---|---|
| quick | "explain sigmoid" | minimal research, fast |
| standard | researched LinkedIn post | normal depth + landscape |
| deep | deep-dive comparative article | more questions, more sources, careful research |

Semi-open rule: controversial requests → deeper. Content creation requests → standard. Simple explanation → quick.

Do NOT build another reasoning subsystem. A small classifier only.

**New file:** `core/research_depth.py`

---

## Phase 2: Content Landscape (First-Class Content Intelligence System)

### 2.1 Schemas

**New file: `core/content_landscape.py`**

```python
class ContentReference(BaseModel):
    """EXISTING content found in the wild. Never fabricated."""
    reference_id: str
    title: str
    url: Optional[str]
    source_type: str              # blog / linkedin_post / x_post / article / reddit / etc.
    author: Optional[str]         # only if actually available
    publication_date: Optional[str]  # only if actually available
    snippet: str                  # actual retrieved text/snippet
    key_points: List[str]
    angle: str                    # angle the existing content takes
    hook: Optional[str]
    tone: str
    main_argument: str
    notable_points: List[str]
    relevance: str                # why this is relevant to the request
    discovery_source: str         # "search" / "web" / etc.
    engagement: Optional[EngagementSignal] = None

class EngagementSignal(BaseModel):
    """Real engagement data ONLY. Never invented."""
    metric: str                   # e.g. "likes", "reposts"
    value: int
    provenance: str               # where the number came from

class ContentLandscape(BaseModel):
    """Analysis of existing content on the topic (LLM-generated from RETRIEVED references)."""
    topic: str
    total_references: int
    reference_ids: List[str]
    dominant_angles: List[str]
    repeated_arguments: List[str]
    common_hooks: List[str]
    saturated_angles: List[str]
    common_framing: List[str]
    audience_questions: List[str]
    disagreements: List[str]
    underexplored_perspectives: List[str]
    content_gaps: List[str]
    possible_original_angles: List[str]
    recommended_differentiation: str
```

### 2.2 Landscape Retrieval — REAL

Queries generated from `RequestIntent`, never hardcoded by topic.

For *"why Elon Musk sucks"* → search for:
- criticism of Elon Musk
- controversies involving Elon Musk
- arguments criticizing Elon Musk
- articles discussing Elon Musk's leadership
- relevant discussions
- existing opinions / competing perspectives

For *"AI agents are changing software development"* → search for:
- articles, blogs, technical writing
- LinkedIn/X content where accessible
- discussions, competing takes, common arguments

**Build:** a `ContentLandscapeSearcher` that converts RequestIntent → a set of real search queries → runs `SearchTool` → collects references (title/url/snippet). Same retrieval tooling as topic research, distinct search targets.

**Hard rules:**
- DO NOT fabricate engagement. `engagement = None` if not retrieved.
- If real numeric engagement exists, store value + provenance.
- Never let Gemini invent popularity.

### 2.3 Landscape Analysis — Gap Discovery

Gemini analyzes the RETRIEVED references and outputs `ContentLandscape`:
- dominant angles, repeated arguments, common hooks
- saturated angles, common framing
- audience questions, disagreements
- underexplored perspectives, **content gaps**, possible original angles

**The value**: e.g., existing content repeatedly says "AI agents are better because they can divide tasks." ALZAI should be able to discover: *"Most discussion focuses on agent specialization, but the more interesting issue is coordination overhead."* That gap discovery is what makes ALZAI avoid producing the same generic post as everyone else.

**New agent:** `agents/landscape_analyzer.py` (GroundedLandscapeAnalyzer) — LLM-based with deterministic grounding fallback that derives analysis from actual reference text.

---

## Phase 3: Writer + Quality Rework

### 3.1 Writer = Original Synthesis, NOT Paraphrase

The writer receives:
- user intent
- research (synthesized brief)
- content landscape (references + analysis)
- selected angle
- content gaps
- relevant examples
- format
- voice

Then creates original content. The flow is NEVER:
- Source A → rewrite Source A
- Existing LinkedIn post → rewrite it

It is:
- multiple research sources + multiple content references + landscape analysis + user intent + original angle → Gemini → new content

**New mandatory instruction in writer prompt:**
> "Do not reproduce distinctive wording, sentences, metaphors, or structure from any supplied content reference."

**Files:** `agents/writer.py`, `agents/multiformat_writer.py`

### 3.2 The LLM MUST Actually Write

- If Gemini succeeds → Gemini writes the content.
- If Gemini fails → the system reports honest failure. NO fake polished articles from deterministic string templates.
- Python must NOT manufacture fake intelligent prose.

### 3.3 Fallbacks Must NEVER Look Like Success

Status is explicit everywhere:
```
status: researching | analyzing | writing | verifying | complete | failed
generation_mode: gemini | fallback | none
```

- If Gemini fails and fallback is insufficient → `status = failed`, NOT `complete` + `quality = 100%`.
- The test harness and UI must distinguish LLM-generated vs fallback output.

### 3.4 Quality Score Must Mean Something

Quality considers actual signal:
- content quality, relevance, coherence, usefulness
- platform fit, naturalness, voice
- factual integrity, research consistency

Rules:
- A failed generation is NEVER a high-quality generation.
- No "1.00 / 1.00" from a deterministic checker just because there are no punctuation errors.
- When the LLM quality engine is unavailable/unreliable, the quality score should reflect honest uncertainty rather than blanket perfection.

### 3.5 Each Format Derives Independently

Multi-format generation: each format derives independently from Research + Content Landscape + Selected Angle + Brand + Voice + Format Specification.

Never: LinkedIn → rewrite into X → rewrite into article.

**Files:** `agents/multi_format_engine.py`, `agents/multiformat_writer.py`, `agents/content_quality.py`

---

## Phase 4: LLM Call Optimization (Intelligent, Not Arbitrary)

**The goal is NOT "≤6 calls."** It is *minimum necessary calls while preserving genuinely intelligent research and writing*.

### 4.1 Principle

- Identify calls that can genuinely be combined (same retrieved context, same reasoning purpose).
- Identify redundant calls.
- Keep calls separate when they require different retrieved context.
- Batch multiple extracted documents/chunks into fewer calls where context limits permit.
- **Measure actual calls; never impose a fake architectural limit.**

### 4.2 Target Flow (approximate, driven by necessity)

| Stage | LLM calls |
|---|---|
| Intent + Research Planning | 1 |
| Content Landscape Analysis | 1 |
| Research Synthesis + Angle Discovery | 1 |
| Evidence Extraction | may legitimately require several (batched by chunk) |
| Writing | 1 per format |
| Quality | 1, only when useful |
| Revision | 0–1, only when necessary |

### 4.3 What NOT to Do

- Do NOT merge Intent+Landscape (impossible — landscape needs retrieval first).
- Do NOT merge unrelated reasoning just to hit a number.
- Do NOT skip evidence extraction calls for small request types (quick mode) unnecessarily — but scale with depth.

---

## Phase 5: API & Orchestrator Updates

### 5.1 Pipeline Order (orchestrator)

1. Intent Analysis + Research Plan
2. Content Landscape Retrieval  ← NEW, real search
3. Content Landscape Analysis   ← NEW, Gemini
4. Topic Research (search → fetch → extract evidence)
5. Research Synthesis + Angle Discovery
6. Format Strategy (per format)
7. Write (per format)
8. Quality Check
9. Targeted Revision if necessary
10. Final Content

Retrieval always precedes semantic landscape analysis.

### 5.2 API

Keep FastAPI. Clean job model.

- `POST /api/generate` — accept prompt + formats + optional mode (quick/standard/deep)
- `GET /api/generate/{job_id}` — job status + result
- `GET /api/generate/{job_id}/trace` — execution trace when requested
- SSE only if it streams REAL events — never fake progress percentages

Job model fields include: `status`, `generation_mode` (gemini/fallback/none), `error_message` when failed.

### 5.3 History

Keep generation history. Store:
- request, timestamp, selected formats
- title/preview, status, generation mode
- final content

User can click a previous generation and reopen it.

---

## Phase 6: Frontend — Content-First Dark Premium UI

### 6.1 Content-First UX

The user came to CREATE CONTENT. Primary experience:
1. Large natural-language composer
2. Format selection
3. Generate
4. Progress
5. Beautiful content result

Research is SECONDARY — expandable sections only:
- "Research"
- "Sources"
- "Content Landscape"
- "Why this angle?"
- "Generation details"

Do NOT make the user navigate an academic research dashboard.

### 6.2 UI Design

Keep the dark ALZAI aesthetic, feel like a real AI creation product (ChatGPT / Google AI Studio reference):
- dark near-black background
- purple accent
- premium typography
- subtle borders, rounded surfaces, restrained glow
- clean hierarchy, excellent spacing
- natural-language composer
- smooth generation transitions
- format tabs, beautiful content cards

Avoid: generic SaaS dashboard, excessive neon, meaningless metrics, giant empty areas, academic research UI as primary interface.

### 6.3 New / Reworked Components

- `Composer.tsx` — large natural-language input, format selector, mode selector (quick/standard/deep)
- `ProgressTracker.tsx` — real pipeline progress with landscape stage
- `ContentRenderer.tsx` — format-native rendering (actual LinkedIn-style post, coherent thread, real article, spoken script, slide-by-slide carousel)
- `ContentLandscapeCard.tsx` — expandable landscape analysis (NEW)
- `AngleSelector.tsx` — let user see/pick discovered angles (NEW)
- `ResearchTransparency.tsx` — rework: sources + angles, not claim-map academic UI
- `GenerationDetails.tsx` — trace + generation mode + quality, expandable (NEW)
- `History.tsx` — click to reopen past generations (NEW)
- `api.ts` / `types/alzai.ts` — update contracts

---

## Phase 7: Real E2E Tests

### 7.1 Required Test Prompts

Run and INSPECT actual output for all of these:
1. `why sam altman is evil`
2. `why elon musk sucks`
3. `explain mixture of experts`
4. `why modern AI agent architectures are shifting from single prompts to multi-agent orchestration`
5. `write a controversial LinkedIn post about remote work`

### 7.2 Report per run (not just "tests passed")

- request intent
- research performed
- content landscape references
- discovered angles
- selected angle
- Gemini calls + count
- generation mode (gemini/fallback)
- status
- quality
- revision count
- **final output (most important)**

### 7.3 Gemini Rate Limit Honesty

Current: free tier rate-limited. Therefore:
- NEVER pretend a fallback run is real Gemini E2E success.
- Test harness explicitly distinguishes LLM-generated vs fallback output.
- When quota becomes available → genuine E2E verification run.

### 7.4 Unit/Integration Tests (new)

- `tests/test_content_landscape.py` — schemas, searcher query generation (no hardcoded topics), gap discovery, no fabricated engagement
- `tests/test_research_depth.py` — classifier (quick/standard/deep), no over-engineering
- `tests/test_writer_originality.py` — writer prompt includes anti-paraphrase instruction; fallback is honest about mode
- `tests/test_new_pipeline.py` — orchestrator order: retrieval precedes landscape analysis; status/generation_mode correctness
- `tests/test_quality_score.py` — failed generation never high score; determinism honesty
- All 150 existing tests keep passing (updated for removed gates)

---

## Implementation Order

Following the user's explicit 7-phase order. Backend FIRST — do not polish frontend while backend generates garbage.

### PHASE 1 — Backend Architecture Reorientation
Remove PubMedGPT gates / templates from synthesis; reframe intent for creative direction; content-aware planner; simple ResearchDepth classifier.

### PHASE 2 — Content Landscape
Schemas (`core/content_landscape.py`), real landscape searcher (intent-driven queries), landscape analyzer with gap discovery.

### PHASE 3 — Writer + Quality Rework
Anti-paraphrase original-synthesis writer prompts; honest fallbacks; meaningful quality scoring; independent per-format generation.

### PHASE 4 — LLM Call Optimization
Consolidate genuinely-mergeable calls; batch evidence extraction; measure, don't impose.

### PHASE 5 — API / Orchestrator
New pipeline order; clean job model with `generation_mode`; trace endpoint; history.

### PHASE 6 — Frontend
Content-first dark premium UI; new components; research as secondary expandable sections.

### PHASE 7 — Tests + Genuine E2E
New tests + 5 real E2E runs, full report per run, rate-limit honesty. Then UI build polish + final verification.

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Gemini rate limits (20/day) | Honest fallback + generation_mode; consolidate real calls; E2E when quota available |
| Content landscape search misses | Intent-driven multi-query generation, same tooling as topic research |
| Fabricated engagement | Engagement only from real retrieved data with provenance; None otherwise |
| Backward compatibility of existing tests | Update tests for removed gates, keep 150 passing |
| Over-engineering creep | Explicitly banned: no new intent/claim/evidence/epistemic/verification engines |

---

## Success Metrics

1. **Content Quality**: reads like human-written original content, never academic summary / template
2. **Angle Intelligence**: discovers a content gap (e.g. coordination overhead vs task division) rather than repeating saturated angles
3. **Pipeline Order**: retrieval always precedes landscape analysis
4. **Honest State**: status/generation_mode truthful; failed never shows 100% quality
5. **Gemini Efficiency**: minimum necessary real calls (measured, not imposed)
6. **Test Coverage**: 150 existing + ~25 new passing; 5 real E2E runs inspected
7. **UI**: content-first, dark premium, publishable-feeling results

---

## Approval Gate

This revised plan restores retrieval-before-analysis, removes the arbitrary call limit, makes Content Landscape a first-class intelligence system, enforces original synthesis (not paraphrase), mandates honest state reporting, and prioritizes backend over frontend.

**I will not begin implementation until the user approves this corrected plan.**