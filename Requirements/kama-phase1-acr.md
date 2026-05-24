# Kama — Phase 1 Technical ACR

**Version:** 1.0  
**Last updated:** May 2026  
**Owner:** Principal Engineer

---

## 1.0 Background job execution — implementation decision (May 2026)

**As-built:** Long-running work (ingestion agent, journal-summary regeneration, Qdrant recipe re-indexing) runs as **`asyncio` background tasks inside the FastAPI / uvicorn process**, scheduled via `app.services.background_runner.enqueue` (e.g. `run_ingestion_send(job_id)` → `enqueue(_run_ingestion, job_id)`). Periodic maintenance (**stuck-job reaper**, **ask session cleanup**) runs as **`asyncio` loops** started from FastAPI **lifespan** in `app.main`.

**What changed (vs. earlier docs):** The repo **no longer depends on Dramatiq** or a separate `dramatiq app.workers` process. Root **`pnpm dev:apps`** runs **Next.js + uvicorn** only.

**Why:** A **separate worker subprocess** (Dramatiq’s typical model) led to **`BrokenPipeError` cascades on logging** when that process was killed during development—**multiprocessing-related stdio pipes** could break, after which **`structlog`/logging** calls failed repeatedly. **In-process `asyncio` tasks** avoid that class of failure and simplify local dev (one Python process, shared DB pool and logger).

**What did not change:** **Redis** is still used for **SSE ingestion progress** (**pub/sub** so job events can be published from async tasks and consumed by the SSE HTTP handler). **Postgres** still holds **durable `IngestionJob` state**; **rerun**, **reaper**, and user-facing semantics are unchanged.

**Revisit — Dramatiq + Redis as a broker (reference path):** Putting jobs on **Redis** and consuming them with **Dramatiq** (or Celery/RQ) remains the right direction when you need **multiple dedicated worker replicas**, **survive API process restarts without losing queued messages**, or **isolate CPU-heavy ingestion from HTTP**. The code keeps a small **`enqueue()`** entry point so that swap can happen without rewriting route handlers. The subsections below under **“Background jobs: Dramatiq + Redis (reference / revisit)”** document why that stack was originally chosen.

---

## 1. Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend (web) | Next.js + TypeScript | App shell, routing, SSR, auth session |
| Frontend (mobile) | Expo / React Native (Phase 2+) | Shares contracts, API client, design tokens |
| Frontend state | TanStack Query + React Hook Form | Server state caching + form management |
| Frontend styling | Tailwind CSS | Fast iteration, maps to shared design tokens |
| Backend API | FastAPI (Python) | Owns all product/domain logic, REST + SSE |
| ORM + migrations | SQLAlchemy 2.0 + Alembic | Standard async-compatible ORM with migration tooling |
| Background jobs | **`background_runner`** (in-process `asyncio`) + **Redis** (SSE pub/sub) | Long jobs off the request thread; see **§1.0**. **Revisit:** Dramatiq + Redis broker for scaled/durable workers |
| Agent framework | PydanticAI | Type-safe tool calling, structured output validation, model-agnostic agent interface; thin layer over LLM tool-calling, not a workflow engine |
| Database | PostgreSQL + pgvector | Recipes, jobs, artifacts. pgvector available; primary vector search moves to Qdrant in Phase 2 |
| File storage | S3-compatible (AWS S3) | Images, source files, OCR outputs |
| Auth | Clerk | Token-based, works for web + mobile |
| Auth wiring | Clerk JWT verification via JWKS endpoint in FastAPI | Backend validates tokens using Clerk's published public keys |
| File uploads | Direct to S3 via presigned URLs | Client uploads directly; backend issues signed URL |
| Realtime | Server-Sent Events (SSE) from FastAPI | Ingestion job progress updates |
| LLM extraction | Anthropic Claude Sonnet (via API) | Strong structured extraction; wrapped behind a service abstraction for future model swaps |
| OCR | Google Cloud Vision API | Dedicated OCR service; superior handwriting support vs Textract |
| YouTube data | youtube-transcript-api + YouTube Data API v3 | Transcripts via lightweight library; metadata + comments via official API |
| Social media data | yt-dlp | Metadata, captions, and video download for Instagram, TikTok, Facebook |
| Speech-to-text | OpenAI Whisper API | Audio transcription for video-extracted recipes |
| URL fetching | httpx | Simple HTTP client for recipe webpages; Playwright fallback for JS-rendered pages added later |
| Monorepo tooling | Turborepo + pnpm workspaces | Task orchestration, caching, and clean dependency management across packages |
| Backend config | Pydantic Settings | Reads from env vars with type validation |
| Deployment (web) | Vercel | Best-in-class Next.js hosting |
| Deployment (backend) | Railway | Python API + Postgres + Redis in one platform |

---

## 2. Technology decision rationale

### Database: SQLAlchemy 2.0 + Alembic
**Why an ORM:** Kama has 12+ domain objects with relationships. Raw SQL at this scale becomes verbose and error-prone. SQLAlchemy translates Python objects into SQL automatically.

**Why SQLAlchemy over alternatives:** Rich JSONB support is critical — `IngestionJob.extractionPlan`, `NormalizedSourceArtifact.payload`, and `RecipeCandidate.fieldProvenanceMap` are all structured JSON in Postgres JSONB columns. SQLAlchemy has the strongest JSONB support of any Python ORM. Version 2.0 added native async support for FastAPI compatibility. pgvector extension support enables Phase 2 embeddings without ORM migration.

**Why not Tortoise ORM:** Weaker JSONB support, smaller community. **Why not SQLModel:** Merges DB models and API schemas into one class, but Kama's API response shapes intentionally diverge from DB schemas (e.g. `RecipeCandidate` API response includes `sourceContext` and `allowedActions` that aren't DB columns). **Why not raw SQL:** Too verbose for 12+ tables with relationships, no migration tooling.

**Alembic** is SQLAlchemy's companion migration tool. It auto-generates migration scripts by diffing Python models against current DB state. No other migration tool fully understands SQLAlchemy models.

### Background jobs: Dramatiq + Redis (reference / revisit)

**Current implementation:** See **§1.0** — work is scheduled with **`background_runner.enqueue`** (in-process `asyncio`). **Redis** is used for **SSE pub/sub**, not as a Dramatiq broker in the running codebase.

**Why a job queue was assumed:** Ingestion pipelines take 5–60 seconds (fetching, OCR, LLM calls, video processing). That work must not block the HTTP request; the API creates the job record and something asynchronous runs the agent while the user watches SSE progress.

**Why Dramatiq + Redis *as a broker* is still documented:** If you **revisit** scaling, it remains a strong option: clean decorator-based API, built-in retry with backoff, middleware support for logging/error handling, lighter than Celery. Dramatiq would manage **which process** runs work; **PydanticAI** still manages **what the agent does** inside that work.

**Why not Celery (when you revisit queues):** Heavier configuration and footprint than Dramatiq for the same class of problem. **Why not arq:** Very lightweight — limited retry strategies, less middleware. **Why not bare FastAPI `BackgroundTasks` alone:** No durable queue, easy to lose work on restart; fine for tiny post-response hooks, not a substitute for a broker-backed worker tier. **Why not Temporal:** Powerful durable workflows; higher ops and conceptual cost than Kama needs until reliability demands it.

**When to switch back to Dramatiq (or similar):** Multiple **worker replicas**, **broker-backed durability** across API deploys, or **hard isolation** of ingestion CPU from HTTP latency.

### Agent framework: PydanticAI
**Why an agent framework at all:** The ingestion pipeline requires dynamic decision-making — the next tool to call depends on what the previous tool discovered. A static plan executor can't handle cases like "the linked recipe page was actually an index page, try transcript instead." An agent loop with tool calling handles this naturally.

**Why PydanticAI:** Type-safe tool definitions using Pydantic models (which Kama already uses everywhere). Structured output validation — when the LLM returns a decision or extraction, PydanticAI validates it against Pydantic models and retries on malformed responses. Model-agnostic interface (works with Anthropic, OpenAI). Dependency injection for tool context. It's a thin layer over LLM tool-calling, not a state management framework — it doesn't sit between your code and your domain model.

**Why not LangGraph:** LangGraph's generic graph state would be less expressive than Kama's domain-specific `IngestionJob` with typed extraction plans, provenance, and state history. Framework abstractions hide the decisions that matter most. Observability becomes framework-dependent. Agent reasoning events, per-method tracking, and SSE emission are easier with direct control.

**Why not CrewAI / AutoGen:** Designed for multi-agent orchestration. Kama has one real agent (ingestion) and lighter tool-augmented patterns (Ask). Multi-agent coordination is not needed.

**Why not fully custom (no framework):** PydanticAI eliminates tedious boilerplate: tool serialization for LLM tool-calling protocol, structured output parsing and validation, retry on malformed responses, conversation history management. Writing this from scratch is error-prone and not where engineering time should go.

**How PydanticAI and background execution work together (as-built):** After `POST /api/ingestion`, **`run_ingestion_send(job_id)`** schedules **`_run_ingestion`** via **`enqueue`**. That coroutine opens a DB session, runs **`run_ingestion_agent`** (PydanticAI), updates **`IngestionJob`**, and publishes **SSE** events. **If you adopt Dramatiq later:** the actor body would be the same agent invocation; only the **dispatch layer** changes.

### Monorepo: Turborepo + pnpm workspaces
**Why a monorepo:** Kama has 4 shared packages + 2 apps that depend on each other. When a type changes in `/packages/contracts`, downstream packages need to pick up the change. A monorepo keeps everything in sync.

**pnpm workspaces** manage how JavaScript packages find and depend on each other. pnpm enforces strict dependency isolation — a package can only use dependencies it explicitly declares. This catches real bugs early and ensures shared packages are genuinely standalone (critical when mobile arrives later).

**Turborepo** handles task orchestration — running builds, linting, and type-checking across packages in the right order with caching. When you run `turbo build`, it builds `contracts → api-client → shared → ui → web` in dependency order, skipping unchanged packages.

**Why not Bazel:** Designed for Google-scale (500+ packages, multi-language). Setup takes weeks, JavaScript/Next.js support is community-maintained and lags behind. The learning curve is steep and the knowledge isn't transferable to target companies. **Why not Rush:** Designed for large-scale npm publishing with independent release cycles. Kama's packages are internal only — Rush's publishing orchestration features are irrelevant overhead. **Why not Nx:** More powerful than needed for 6 packages. Significantly more configuration and learning curve.

**Important:** Turborepo and pnpm only manage the JavaScript/TypeScript side. Python has no compile step — it runs directly as `.py` files. The Python backend uses its own dependency management (uv or Poetry) independently.

### Python dependency management: uv
**uv** is a fast, modern Python package manager. Drop-in replacement for pip with better performance and dependency resolution. Manages virtual environments and dependency locking. The backend runs `uv sync` to install dependencies — equivalent to `pnpm install` on the JS side.

### URL fetching: httpx
**Why httpx:** Most recipe pages are server-rendered — the HTML comes back with recipe content on the first request. httpx is async-native (fits FastAPI), fast, lightweight, handles redirects and timeouts cleanly.

**Why not Playwright/Selenium for everything:** Launching a headless browser for every URL is 3–10x slower, uses significantly more memory, requires Chromium installed in the deployment environment, and is unnecessary for the majority of recipe sites. Playwright can be added later as a specific processor variant for JS-rendered pages that httpx can't handle.

**Social media URLs:** httpx is not used for scraping social pages (Instagram, TikTok, Facebook are client-rendered and block automated requests). Social media data is acquired through yt-dlp instead. httpx is used only when following linked recipe page URLs found in social captions.

### Social media data: yt-dlp
**yt-dlp** is an open-source tool that extracts metadata, captions, and downloads video from Instagram, TikTok, Facebook, and hundreds of other platforms. It handles platform-specific authentication quirks, rate limiting, and format negotiation internally. For social media ingestion, yt-dlp replaces the need to scrape client-rendered pages.

### YouTube data: YouTube Data API v3 + youtube-transcript-api
**Why separate from yt-dlp:** YouTube's official API is more reliable and structured for YouTube specifically. `youtube-transcript-api` is a lightweight Python library that fetches transcripts without an API key. The Data API provides metadata and comments with proper pagination. Keeping YouTube on its dedicated API while using yt-dlp for other social platforms is cleaner and more reliable.

### OCR: Google Cloud Vision API
**Why dedicated OCR over multimodal LLM:** Dedicated OCR is more cost-efficient for text extraction at scale. Google Cloud Vision has superior handwriting recognition — critical for the "digitize mom's recipe diary" use case. The OCR result is stored as a `NormalizedSourceArtifact`, then a single LLM call does the structured recipe extraction from OCR text.

**Why Google Cloud Vision over AWS Textract:** Better handwriting support. Textract is stronger for structured documents/tables, which is less relevant for recipe images.

### LLM extraction: Anthropic Claude Sonnet
**Why Claude Sonnet:** Strong at structured extraction tasks, good instruction following for producing typed recipe output. Wrapped behind a service abstraction in `candidate_extraction_service` so the model can be swapped (to GPT-4o, Claude Haiku, etc.) without pipeline changes.

**The abstraction matters:** Different pipeline steps can use different models. Frame text extraction (simpler task) could later use a cheaper model like Haiku. Final structured extraction (needs more intelligence) stays on Sonnet. The service interface makes this a configuration change, not a rewrite.

### Speech-to-text: OpenAI Whisper API
**Purpose:** Audio transcription for social media videos where the recipe is spoken. No Anthropic equivalent exists for speech recognition. Cost is minimal ($0.006/minute). Produces timestamped segments stored as a `video_audio_transcript` artifact.

### Frontend state: TanStack Query + React Hook Form
**TanStack Query** manages all communication with the FastAPI backend — fetching, caching, background refetching, loading/error states, cache invalidation. Kama has 27 API endpoints and multiple screens that share data (recipe list and recipe detail both need recipe data). TanStack Query handles this lifecycle declaratively instead of requiring manual fetch/cache plumbing.

**React Hook Form** manages form interactions on complex editing screens. The candidate review screen has ingredient rows, step rows, tag selection, metadata fields, and a decision action — all at once. React Hook Form tracks field values, validation, and dirty state without re-rendering the entire form on every keystroke.

**Why not Redux/RTK Query:** Significantly more boilerplate for the same result. Redux's mental model (actions, reducers, dispatch) adds overhead that doesn't pay off at Kama's scale. **Why not MobX:** Excellent reactivity but doesn't solve server data management — you'd rebuild TanStack Query's caching, invalidation, and refetching features manually inside MobX stores. **Why not Zustand:** Good for pure UI state but weak as a server data layer. Can be added later if genuine cross-screen UI state emerges. **Why not SWR:** Less powerful than TanStack Query — weaker mutation support and cache control. Kama's SSE-driven ingestion flow benefits from TanStack Query's explicit cache API.

### Frontend styling: Tailwind CSS
**Why Tailwind:** Fast iteration (style as you build, no file switching), design tokens map to `tailwind.config.ts` as a single source of truth, excellent Next.js integration (zero config, default in `create-next-app`), production build strips unused classes for minimal CSS, and AI coding tools generate better Tailwind than any alternative due to training data representation.

**Why not CSS Modules:** Slower iteration (switching between markup and CSS files), no built-in design token system, responsive design requires manual media queries. **Why not styled-components/Emotion:** Runtime CSS injection conflicts with Next.js Server Components. The Next.js team has moved away from runtime CSS-in-JS. **Why not Vanilla Extract:** More verbose, smaller community, slower DX for rapid iteration.

**Mobile consideration:** Tailwind classes only work in browser context. For React Native `.native.tsx` variants in `/packages/ui`, options are NativeWind (Tailwind class names in React Native) or shared tokens with platform-specific StyleSheet. This decision is deferred to Phase 2 when mobile development begins. Design tokens in `/packages/ui/tokens` should be defined in a platform-agnostic format so they can map to either approach.

### Auth: Clerk with JWT verification
**Why Clerk:** Token-based auth that works for both web and future mobile. Clean Next.js integration. The backend verifies JWTs using Clerk's published JWKS endpoint — no session cookie coupling. FastAPI middleware validates the `Authorization: Bearer <token>` header on every request using PyJWT and Clerk's public keys.

### File uploads: presigned S3 URLs
**Why direct-to-S3:** Keeps the Python backend lean — large image files don't proxy through the API server. The flow: client requests a presigned URL from the backend, uploads directly to S3, then notifies the backend with the resulting `assetRef`. This works identically for web and future mobile clients.

### Deployment: Vercel (frontend) + Railway (backend)
**Why split deployment:** Next.js and Python have fundamentally different hosting needs. Next.js wants edge/serverless deployment with SSR optimization. Python needs **persistent** processes for **FastAPI** (HTTP + **SSE**). Today a **single** Python service (uvicorn) runs API + in-process background tasks; **optionally** add a **second Railway service** with the same image and a **worker entrypoint** if you move back to **Dramatiq** or another queue consumer.

**Vercel** gives Next.js best-in-class hosting: automatic deployment on git push, edge caching, image optimization, preview deployments per branch. Free tier covers personal usage.

**Railway** hosts everything Python: at minimum **FastAPI** as one container service; managed Postgres, managed Redis, and (Phase 2) Qdrant. **Optional second service:** dedicated worker (e.g. `dramatiq app.workers`) when using a broker-backed queue again.

**CORS:** Since frontend (Vercel) and backend (Railway) are on different domains, FastAPI needs CORS middleware. SSE connections cross the same boundary — standard CORS handling applies.

**Why not Railway for everything:** Lacks Vercel's edge network, image optimization, ISR caching, and preview deployments. **Why not Fly.io:** Requires more hands-on operational knowledge. **Why not self-hosted VPS:** Sysadmin distraction. **Why not AWS/GCP:** Massive complexity overhead for a personal project.

### Docker: containers for infrastructure and deployment
**Why Docker Compose for local dev:** Kama requires Postgres, Redis, and (Phase 2+) Qdrant running locally. Docker Compose starts them with `docker compose up`. Application code (**FastAPI** + **Next.js**) runs natively for hot reload; **no separate Dramatiq tab** is required with **`background_runner`**.

**Why Dockerfiles for deployment:** The backend has system dependencies beyond Python packages — `ffmpeg` is needed for video frame extraction in the ingestion pipeline, `yt-dlp` works best as a system-level tool. Railway's auto-detection won't install these. Explicit Dockerfiles make builds reproducible and portable. **One image** can serve **uvicorn only** (current default) **or** the same image with a **different CMD** for a future **Dramatiq** worker service.

**Docker Compose (local dev):**
```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: kama
      POSTGRES_USER: kama
      POSTGRES_PASSWORD: kama_local
    volumes: [postgres_data:/var/lib/postgresql/data]
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
volumes:
  postgres_data:
```

Qdrant is added to this file in Phase 2.

**Dockerfile (backend):**
```dockerfile
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
RUN pip install uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen
COPY . .
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Optional second container (revisit Dramatiq):** same image, different CMD, e.g. `CMD ["uv", "run", "dramatiq", "app.workers"]` — only if you reintroduce a broker-backed worker.

### Local development setup
```bash
docker compose up -d        # Starts Postgres, Redis (+ Qdrant/MinIO per compose file)
pnpm dev:apps                # Starts Next.js + FastAPI (ingestion runs in-process on FastAPI)
```

Legacy pattern (if Dramatiq is reintroduced): add a third process, e.g. `dramatiq app.workers`, consuming Redis-backed queues.

---

## 3. Repository structure

Monorepo with strong package boundaries from day one.

```
/
  docker-compose.yml              ← Local infrastructure (Postgres, Redis; Qdrant added in Phase 2)
  turbo.json
  package.json

/apps
  /web                            ← Next.js application
  /mobile                         ← Expo app (Phase 2+)

/packages
  /contracts                      ← Domain types, DTOs, enums, schemas
  /api-client                     ← FastAPI client wrappers, SSE helpers
  /shared                         ← Business helpers, constants, formatters
  /ui                             ← Shared design system (tokens, primitives, components)

/backend
  Dockerfile                      ← Backend container (FastAPI; includes ffmpeg)
  pyproject.toml
  /app
    /api                          ← FastAPI route handlers
    /core                         ← Config, auth middleware, DB bootstrap
    /domain                       ← Business enums, orchestration rules, processor catalogs
    /models                       ← SQLAlchemy / persistence models
    /schemas                      ← Pydantic request/response schemas
    /services                     ← Ingestion agent, extraction, review, promotion logic; `background_runner`
    /agents                       ← PydanticAI agent definitions, tool catalog, agent context
    /tools                        ← Individual tool implementations (httpx_fetch, ocr_extract, etc.)
    /workers                      ← In-process job entrypoints (`run_ingestion_send`, etc.); optional Dramatiq actors if revisited
    /repositories                 ← DB access layer
```

### Package ownership rules

1. `/ui` cannot import from `/web` or `/mobile`
2. `/contracts` contains zero app-specific or UI logic
3. `/api-client` depends on `/contracts`, not the reverse
4. `/shared` can depend on `/contracts`, not on `/web` or `/mobile`
5. `/web` and `/mobile` consume all packages but remain thin on domain logic

### Shared UI pattern

Platform-specific component implementations where needed:

```
/packages/ui/src/Button/
  index.ts               ← Re-exports the correct file
  Button.tsx             ← Web implementation
  Button.native.tsx      ← React Native implementation
  types.ts               ← Shared props interface
```

### Contract source of truth

Pydantic models in the Python backend are the authoritative source. TypeScript contracts in `/packages/contracts` mirror them. Do not invent separate frontend-only shapes.

---

## 3. Backend ownership (Phase 1)

### `/backend/app/api`
Ingestion routes, candidate routes, recipe routes, journal routes, tag routes, media routes, presigned URL routes.

### `/backend/app/domain`
Ingestion enums, artifact type registry, processor catalogs, extraction method definitions, status/error semantics.

### `/backend/app/schemas`
Pydantic models for: SourceAsset, IngestionJob, NormalizedSourceArtifact, RecipeCandidate, DraftRecipe, CanonicalRecipe, RecipeRevision, RecipeMedia, Ingredient, CookJournalEntry, JournalEntryMedia, Tag.

### `/backend/app/agents`
PydanticAI agent definitions. `ingestion_agent.py` — agent configuration, system prompt, tool registration, context model. `review_agent.py` — review agent configuration, review-specific system prompt, review tool catalog. Future agents (e.g. ask assistant) live here too.

### `/backend/app/tools`
Individual tool implementations. One file per tool or related tool group: `source_tools.py`, `fetch_tools.py`, `ocr_tools.py`, `video_tools.py`, `extraction_tools.py`, `evaluation_tools.py`, `review_tools.py` (ingredient lookup, artifact re-reading, normalization, coherence checks). Each tool is a PydanticAI-decorated async function returning a typed `ToolResult`.

### `/backend/app/services`
`ingestion_service` — Job creation, agent invocation orchestration, job finalization.  
`normalization_service` — Source normalization helpers used by tools.  
`review_service` — Candidate decision handling, draft promotion assessment.  
`recipe_service` — CRUD, revision management.  
`journal_service` — Entry creation/deletion, journalSummary regeneration trigger.  
`tag_service` — Tag lookup/creation.  
`media_service` — Presigned URL generation, media record management.

### `/backend/app/workers`
`ingestion_worker` — Entry point for ingestion: **`run_ingestion_send`** → **`background_runner.enqueue`** → **`_run_ingestion`** runs **`run_ingestion_agent`** (PydanticAI).  
`journal_summary_worker` — **`regenerate_journal_summary_send`** → **`enqueue`** for async **journalSummary** regeneration.  
`search_index_worker` — **`index_recipe_send`** → **`enqueue`** for Qdrant embedding upserts (Phase 2).  
`reaper_worker` / `ask_cleanup_worker` — **lifespan** `asyncio` loops, not `enqueue`.  
**Revisit:** wrap the same bodies in **Dramatiq actors** if moving to a Redis-backed broker.

### `/backend/app/repositories`
One repository per domain aggregate: source assets, jobs, artifacts, candidates, drafts, recipes, revisions, media, journal entries, tags, ingredients.

---

## 4. Domain model — Phase 1

### 4.1 SourceAsset

The raw user-submitted input. Immutable after creation.

```typescript
type SourceAsset = {
  id: string;
  userId: string;
  sourceType: "url" | "image" | "text";
  originalUrl?: string | null;
  rawTextInput?: string | null;
  fileAssetRef?: string | null;
  contextNote?: string | null;
  createdAt: string;
};
```

### 4.2 IngestionJob

The execution record for processing a source. Rich orchestration state.

```typescript
type IngestionJob = {
  id: string;
  sourceAssetId: string;

  // User-facing lifecycle
  status:
    | "queued"
    | "processing"
    | "review_ready"
    | "draft_ready"
    | "failed"
    | "unsupported";

  // Internal pipeline stage
  internalState:
    | "source_received"
    | "source_normalization"
    | "extraction_plan_building"
    | "recipe_extraction"
    | "quality_assessment"
    | "review_agent_processing"
    | "completed";

  // Internal failure classification (set when status = failed | unsupported)
  internalErrorState?: string | null;
  // Examples: "normalization_failed", "metadata_fetch_failed", "ocr_failed",
  // "transcript_fetch_failed", "extraction_failed", "assessment_failed",
  // "no_recipe_structure_detected", "unreadable_handwriting",
  // "linked_recipe_page_unreachable"

  // Execution identity
  processorFamily: string;   // e.g. "url", "image", "text"
  processorVariant?: string | null; // e.g. "youtube_linked_recipe_fallback"

  // Review
  reviewMode?: "quick" | "standard" | "reconstruction" | null;

  // Output linkage
  candidateId?: string | null;
  normalizedArtifactIds: string[];

  // Error / control
  errorType?: "internal" | "source_access" | "source_quality" | "parseability" | null;
  errorCode?: string | null;
  rerunAllowed: boolean;
  userRecoverable: boolean;

  // Orchestration
  extractionPlan: ExtractionMethodPlanEntry[];
  stateHistory: IngestionJobHistoryEvent[];

  // Metadata
  metadata?: Record<string, unknown>;

  // Timeline
  createdAt: string;
  startedAt?: string | null;
  completedAt?: string | null;
  updatedAt: string;
  lastHeartbeatAt?: string | null;   // Updated by agent on each tool call; used by reaper to detect stuck jobs
};
```

#### ExtractionMethodPlanEntry

Each method in the fallback ladder.

```typescript
type ExtractionMethodPlanEntry = {
  methodKey: string;
  priority: number;

  feasible: boolean;
  feasibilityReason?: string;
  requiredArtifacts: string[];
  addedBy: "initial_plan" | "agent_reasoning";

  status:
    | "pending"
    | "running"
    | "succeeded"
    | "failed"
    | "skipped"
    | "not_applicable"
    | "deferred"          // Agent decided to try something else first
    | "merged";           // Agent combined output with another method

  startedAt?: string | null;
  completedAt?: string | null;

  outputSummary?: {
    candidateCreated: boolean;
    canonicalEligible: boolean;
    draftEligible: boolean;
    confidenceLevel?: "low" | "medium" | "high";
    notes?: string[];
  } | null;

  failure?: {
    errorType?: "internal" | "source_access" | "source_quality" | "parseability";
    errorCode?: string;
    message?: string;
  } | null;

  stopDecision?: {
    stopPipeline: boolean;
    reason?: string;
  } | null;

  // Agent reasoning trace (set when agent made a non-deterministic decision)
  agentDecision?: {
    reasoning: string;
    alternativesConsidered: string[];
    deterministic: boolean;
  } | null;
};
```

#### IngestionJobHistoryEvent

Lightweight event log for debugging, SSE recovery, and observability.

```typescript
type IngestionJobHistoryEvent = {
  eventType:
    | "state_changed"
    | "plan_built"
    | "plan_modified"
    | "tool_called"
    | "tool_succeeded"
    | "tool_failed"
    | "agent_reasoning"
    | "candidate_created"
    | "candidate_improved"
    | "job_completed"
    | "job_failed"
    | "job_unsupported";

  timestamp: string;
  internalState?: string;
  methodKey?: string;
  status?: string;
  internalErrorState?: string;
  reasoning?: string;          // Agent's reasoning text (for agent_reasoning events)
  notes?: string[];
};
```

### 4.3 NormalizedSourceArtifact

Intermediate typed evidence derived from a source. Temporary retention with future expiry.

```typescript
type NormalizedSourceArtifact<TPayload = unknown> = {
  id: string;
  ingestionJobId: string;
  artifactType: ArtifactType;
  payload: TPayload;
  createdAt: string;
  expiresAt?: string | null;
};
```

`artifactType` is the discriminant. The payload shape is defined per type. See section 5 for the full artifact catalog.

### 4.4 RecipeCandidate

The structured extraction result ready for review. Created by the extraction pipeline.

```typescript
type RecipeCandidate = {
  id: string;
  sourceAssetId: string;
  ingestionJobId: string;

  // Structured content
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];    // Tag IDs

  // Review readiness
  canonicalEligible: boolean;
  draftEligible: boolean;
  reviewMode: "quick" | "standard" | "reconstruction";
  reviewFindings: ReviewFinding[];

  // Confidence (candidate-only, not carried to canonical)
  fieldConfidenceMap: Record<string, "low" | "medium" | "high">;

  // Provenance
  selectedExtractionMethod: string;
  sourceArtifactIds: string[];
  fieldProvenanceMap: Record<string, FieldProvenance>;

  createdAt: string;
};
```

#### Shared sub-types

```typescript
type RecipeIngredientRow = {
  text: string;
  ingredientId?: string | null;
  quantity?: string | null;    // Raw string, not normalized
  unit?: string | null;
};

type RecipeStepRow = {
  order: number;
  text: string;
  mediaRefs?: string[];       // RecipeMedia IDs
};

type FieldProvenance = {
  sourceType: string;          // e.g. "linked_recipe_page", "ocr_text", "transcript"
  artifactId: string;
  note?: string | null;
};

type ReviewFinding = {
  code: string;
  severity: "info" | "warning" | "error";
  field?: string | null;
  message: string;
  sourceArtifactId?: string | null;
};
```

### 4.5 DraftRecipe

A user-owned editable working recipe. Not trusted. Excluded from retrieval/ask/create.

```typescript
type DraftRecipe = {
  id: string;
  userId: string;
  originSourceAssetId: string;
  originRecipeCandidateId: string;

  // Editable structured content (same shape as candidate)
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];

  promotionEligible: boolean;

  createdAt: string;
  updatedAt: string;
};
```

**Lifecycle:** Created from a candidate review decision. Editable. Promotable to canonical via promotion review. Deleted after successful promotion.

### 4.6 CanonicalRecipe

The trusted saved recipe. Powers library, retrieval, ask, create.

```typescript
type CanonicalRecipe = {
  id: string;
  userId: string;

  // Structured content
  title: string;
  ingredients: RecipeIngredientRow[];
  steps: RecipeStepRow[];
  description?: string | null;
  prepTimeMinutes?: number | null;
  cookTimeMinutes?: number | null;
  servings?: number | null;
  recipeTags: string[];

  // Nutrition (from schema.org, LLM extraction, or multimodal — never guessed)
  nutrition?: NutritionInfo | null;

  // Chef's notes (tips, substitutions, storage, variations)
  notes: ChefNote[];

  // Media
  heroImageId?: string | null;

  // Journal-derived
  journalSummary?: string | null;

  // Provenance (retained from candidate, confidence dropped)
  fieldProvenanceMap: Record<string, FieldProvenance>;
  sourceAssetId?: string | null;
  originRecipeCandidateId?: string | null;

  // Promotion metadata (when created from draft)
  promotedFromDraft: boolean;
  promotedAt?: string | null;

  createdAt: string;
  updatedAt: string;
};

type NutritionInfo = {
  calories?: string | null;
  servingSize?: string | null;
  carbohydrates?: string | null;
  protein?: string | null;
  fat?: string | null;
  saturatedFat?: string | null;
  unsaturatedFat?: string | null;
  transFat?: string | null;
  cholesterol?: string | null;
  sodium?: string | null;
  fiber?: string | null;
  sugar?: string | null;
};

type ChefNoteType = "tip" | "substitution" | "storage" | "variation" | "general";

type ChefNote = {
  type: ChefNoteType;
  text: string;
};
```

### 4.7 RecipeRevision

Immutable snapshot of a prior canonical recipe state.

```typescript
type RecipeRevision = {
  id: string;
  canonicalRecipeId: string;
  snapshotPayload: object;     // Full content state at time of revision
  changeSummary?: string | null;
  createdAt: string;
};
```

Created automatically when meaningful recipe content changes (title, ingredients, steps, times, servings). Not created for tag changes, media changes, or note additions. Revisions start after the first edit — the initial canonical save is not revision v1.

### 4.8 RecipeMedia

Recipe-level media (extracted and user-uploaded).

```typescript
type RecipeMedia = {
  id: string;
  canonicalRecipeId: string;
  mediaType: "image";         // Extensible later
  role: "hero" | "source_gallery" | "step_reference" | "user_added_gallery";
  source: "extracted" | "uploaded";
  assetRef: string;            // S3 key / URL
  displayOrder?: number | null;
  createdAt: string;
};
```

### 4.9 Ingredient

Global ingredient knowledge layer.

```typescript
type IngredientCategory =
  | "produce"           // fruits, vegetables, fresh herbs
  | "meat_seafood"      // chicken, beef, shrimp, etc.
  | "dairy"             // milk, cheese, yogurt, butter, cream
  | "grains_bread"      // rice, pasta, flour, bread, oats
  | "spices_seasoning"  // cumin, salt, pepper, paprika, dried herbs
  | "oils_vinegars"     // olive oil, sesame oil, balsamic, soy sauce
  | "canned_jarred"     // canned tomatoes, beans, coconut milk, broth
  | "frozen"            // frozen peas, frozen berries
  | "baking"            // sugar, baking powder, vanilla extract, chocolate
  | "nuts_seeds"        // almonds, sesame seeds, peanut butter
  | "beverages"         // wine (cooking), stock, juice
  | "other";            // anything that doesn't fit

type Ingredient = {
  id: string;
  name: string;
  category: IngredientCategory;    // Required. Used by shopping list grouping and pantry UI
  aliases: string[];
  notes?: string | null;
  createdAt: string;
};
```

**Database index:** `Ingredient.category` has a B-tree index (`ix_ingredients_category`) for filtered queries and category-grouped listings.

### 4.10 Tag

Shared infrastructure, domain-separated vocabulary.

```typescript
type Tag = {
  id: string;
  domain: "recipe" | "journal";
  name: string;
  createdBySystem: boolean;
  createdByUserId?: string | null;
  createdAt: string;
};
```

### 4.11 CookJournalEntry

```typescript
type CookJournalEntry = {
  id: string;
  canonicalRecipeId: string;
  userId: string;
  body: string;
  cookedOn?: string | null;   // Date-only (YYYY-MM-DD)
  tags: string[];              // Tag IDs (journal domain)
  createdAt: string;
};
```

### 4.12 JournalEntryMedia

```typescript
type JournalEntryMedia = {
  id: string;
  journalEntryId: string;
  assetRef: string;
  source: string;
  displayOrder?: number | null;
  createdAt: string;
};
```

Maximum 2 images per journal entry.

---

## 5. Artifact catalog

Each artifact type has a defined payload contract. `artifactType` is the TypeScript discriminant.

```typescript
type ArtifactType =
  | "parseability_assessment"
  | "source_preview"
  | "url_metadata"
  | "cleaned_page_text"
  | "linked_recipe_urls"
  | "video_metadata"
  | "video_transcript"
  | "social_caption"
  | "creator_profile"
  | "bio_link_urls"
  | "video_audio_transcript"
  | "video_frame_text"
  | "image_analysis"
  | "ocr_text"
  | "cleaned_text"
  | "text_structure_analysis";
```

### 5.1 parseability_assessment

System's judgment about source viability. Drives routing and review mode.

```typescript
type ParseabilityAssessmentPayload = {
  sourceSubtypeDetected:
    | "recipe_webpage"
    | "generic_webpage"
    | "youtube_video"
    | "instagram_reel"
    | "instagram_post"
    | "tiktok_video"
    | "facebook_video"
    | "facebook_post"
    | "social_video_other"
    | "printed_recipe_image"
    | "handwritten_image"
    | "freeform_text"
    | "structured_recipe_text"
    | "unknown";

  recipeLikelihood: "low" | "medium" | "high";
  completenessLikelihood: "low" | "medium" | "high";

  hasTitleSignal: boolean;
  hasIngredientSignal: boolean;
  hasStepSignal: boolean;

  recommendedProcessor: string;
  reviewMode: "quick" | "standard" | "reconstruction";

  draftEligible: boolean;
  canonicalEligible: boolean;

  blockingIssues: string[];
  notes: string[];
};
```

### 5.2 source_preview

Human-readable context for job progress and review screens.

```typescript
type SourcePreviewPayload =
  | {
      previewKind: "image";
      previewUrl: string;
      width?: number;
      height?: number;
      summaryText: string;
    }
  | {
      previewKind: "link_card";
      title?: string;
      subtitle?: string;
      imageUrl?: string;
      sourceUrl: string;
      summaryText: string;
    }
  | {
      previewKind: "text_excerpt";
      excerpt: string;
      summaryText: string;
    };
```

### 5.3 url_metadata

Metadata fetched from a URL before recipe extraction.

```typescript
type UrlMetadataPayload = {
  sourceUrl: string;
  finalResolvedUrl?: string;
  domain?: string;
  platform?: "web" | "youtube" | "instagram" | "tiktok" | "other";
  title?: string;
  description?: string;
  author?: string;
  publishedAt?: string;
  heroImageUrl?: string;
  pageTypeHint?: string;
  fetchStatus: "success" | "failed" | "partial";
  notes?: string[];
};
```

### 5.4 cleaned_page_text

Primary extraction input for webpages.

```typescript
type CleanedPageTextPayload = {
  sourceUrl: string;
  title?: string;
  text: string;
  extractionMethod:
    | "schema_recipe"
    | "main_content_cleaning"
    | "readability_extraction"
    | "mixed";
  contentSections?: Array<{
    sectionType: "title" | "intro" | "ingredients" | "instructions" | "notes" | "unknown";
    text: string;
  }>;
  textLength: number;
};
```

### 5.5 linked_recipe_urls

External recipe links found in descriptions, comments, or page body.

```typescript
type LinkedRecipeUrlsPayload = {
  urls: Array<{
    url: string;
    source: "description" | "first_comment" | "page_body" | "other";
    anchorText?: string;
    position?: number;
    confidence: "low" | "medium" | "high";
  }>;
};
```

### 5.6 video_metadata

Video-specific metadata, distinct from transcript.

```typescript
type VideoMetadataPayload = {
  platform: "youtube" | "instagram" | "tiktok" | "facebook" | "other";
  sourceUrl: string;
  videoId?: string;
  title?: string;
  description?: string;
  creatorName?: string;
  thumbnailUrl?: string;
  durationSec?: number;
  firstCommentText?: string;
  transcriptAvailable: boolean;
  captionText?: string;
  notes?: string[];
};
```

### 5.7 video_transcript

Transcript content from YouTube platform transcripts (via youtube-transcript-api).

```typescript
type VideoTranscriptPayload = {
  sourceUrl: string;
  transcriptAvailable: boolean;
  text: string;
  segments?: Array<{
    startSec: number;
    endSec?: number;
    text: string;
  }>;
  transcriptSource: "platform" | "generated" | "other";
};
```

### 5.8 social_caption

Caption/description text extracted from social media posts via yt-dlp.

```typescript
type SocialCaptionPayload = {
  platform: "instagram" | "tiktok" | "facebook" | "other";
  sourceUrl: string;
  captionText: string;
  captionLength: number;
  hashtags: string[];
  mentionedUrls: string[];
  uploaderName?: string;
  postDate?: string;
};
```

### 5.9 creator_profile

Creator identity and public profile data from social platforms. Used to discover bio links and creator websites.

```typescript
type CreatorProfilePayload = {
  platform: "instagram" | "tiktok" | "facebook" | "youtube" | "other";
  creatorUsername: string;
  creatorDisplayName?: string;
  profileUrl: string;
  bioText?: string;
  bioUrls: string[];
  websiteUrl?: string;
  hasLinkInBio: boolean;
  linkInBioType?: "linktree" | "beacons" | "direct_website" | "other_aggregator" | "none";
};
```

### 5.10 bio_link_urls

Expanded and categorized links from creator bio/linktree resolution. Each link is classified by recipe relevance to avoid blindly crawling shops, social profiles, or unrelated pages.

```typescript
type BioLinkUrlsPayload = {
  sourceProfileUrl: string;
  linkInBioUrl?: string;
  expandedLinks: Array<{
    url: string;
    title?: string;
    category: "recipe_blog" | "website_home" | "social_profile" | "shop" | "other";
    recipeRelevance: "high" | "medium" | "low" | "none";
  }>;
  bestRecipeCandidate?: {
    url: string;
    reason: string;
  } | null;
};
```

### 5.11 video_audio_transcript

Audio transcription from a downloaded social/video file via Whisper.

```typescript
type VideoAudioTranscriptPayload = {
  sourceUrl: string;
  platform: "instagram" | "tiktok" | "facebook" | "youtube" | "other";
  text: string;
  segments: Array<{
    startSec: number;
    endSec: number;
    text: string;
  }>;
  language?: string;
  durationSec: number;
  transcriptionSource: "whisper";
  quality: "low" | "medium" | "high";
};
```

### 5.12 video_frame_text

Text extracted from video key frames via multimodal LLM.

```typescript
type VideoFrameTextPayload = {
  sourceUrl: string;
  framesAnalyzed: number;
  framesWithText: number;
  extractedBlocks: Array<{
    frameTimeSec: number;
    text: string;
    blockType: "ingredient_list" | "step_instruction" | "title" | "general_text" | "unknown";
    confidence: "low" | "medium" | "high";
  }>;
  combinedText: string;
};
```

### 5.13 image_analysis

Lightweight assessment of image type and readability.

```typescript
type ImageAnalysisPayload = {
  imageKind:
    | "handwritten_recipe"
    | "printed_recipe"
    | "screenshot"
    | "mixed_content"
    | "unknown";
  readability: "low" | "medium" | "high";
  handwritingDetected: boolean;
  likelyStructuredSections: boolean;
  width?: number;
  height?: number;
  notes?: string[];
};
```

### 5.14 ocr_text

Extracted text from images.

```typescript
type OCRTextPayload = {
  text: string;
  lineBlocks: Array<{
    index: number;
    text: string;
    confidence?: number;
  }>;
  ocrQuality: "low" | "medium" | "high";
  ocrSource: "printed_text" | "handwriting" | "mixed";
};
```

### 5.15 cleaned_text

Normalized pasted text input.

```typescript
type CleanedTextPayload = {
  originalLength: number;
  cleanedLength: number;
  text: string;
  cleanupApplied: Array<
    | "trim_whitespace"
    | "normalize_line_breaks"
    | "remove_noise"
    | "preserve_list_structure"
  >;
};
```

### 5.16 text_structure_analysis

Recipe-likeness assessment for pasted or cleaned text.

```typescript
type TextStructureAnalysisPayload = {
  textKind: "recipe_like" | "notes_like" | "mixed" | "unknown";
  hasTitleLikeLine: boolean;
  hasIngredientLikeLines: boolean;
  hasStepLikeLines: boolean;
  probableSections: Array<{
    sectionType: "title" | "ingredients" | "steps" | "notes" | "unknown";
    excerpt: string;
  }>;
  notes?: string[];
};
```

**Not all sources produce all artifact types.** Each processor path emits only the artifacts that make sense for that source.

---

## 6. Ingestion pipeline design

### 6.1 Processing model

Source-specific processors behind a common ingestion contract. Clean routing, no conditional spaghetti.

**Two-stage fallback planning:**

**Stage 1 — Capability discovery.** For a given source subtype, start with a full predefined list of possible extraction methods. The first normalization pass inspects the source and determines which methods are actually feasible. Infeasible methods are marked `not_applicable`.

**Stage 2 — Execute feasible subset in priority order.** The processor works through only feasible methods, stopping when it reaches a canonical-eligible candidate or the best possible draft-eligible result.

### 6.2 Extraction method catalogs (master lists)

#### Video URL — YouTube

Acquisition tools: YouTube Data API v3 + youtube-transcript-api.

| Priority | Method key | Description |
|---|---|---|
| 1 | `recipe_link_from_description` | Follow linked recipe page in video description |
| 2 | `recipe_link_from_first_comment` | Follow linked recipe page in first comment |
| 3 | `structured_recipe_text_from_description` | Extract recipe structure from description text |
| 4 | `structured_recipe_text_from_first_comment` | Extract recipe structure from comment text |
| 5 | `transcript_extraction` | Extract recipe from platform transcript via youtube-transcript-api |
| 6 | `video_content_extraction` | Download video, transcribe via Whisper + extract key frame text via multimodal LLM (last resort) |

#### Social URL — Instagram

Acquisition tool: yt-dlp (public posts/reels only).

| Priority | Method key | Description |
|---|---|---|
| 1 | `recipe_link_from_caption` | Scan caption for linked recipe page URL, follow with httpx |
| 2 | `creator_bio_link_resolution` | Fetch creator profile, expand bio/linktree links, find recipe-relevant URLs |
| 3 | `creator_site_recipe_discovery` | Search creator's website for a recipe matching video title/caption/ingredients |
| 4 | `structured_recipe_text_from_caption` | Extract recipe structure directly from caption text via LLM |
| 5 | `video_audio_transcription` | Download video via yt-dlp, transcribe audio via Whisper, extract recipe from transcript |
| 6 | `video_frame_text_extraction` | Extract key frames from video, use multimodal LLM to read text overlays |
| 7 | `combined_video_extraction` | Merge audio transcript + frame text, run LLM structured extraction on combined content |

Note: Methods 5, 6, and 7 execute as a group when reached — audio transcription and frame extraction run in parallel, then results are combined for final extraction.

**Bio link resolution flow (methods 2–3):** The agent fetches the creator's profile metadata via yt-dlp, producing a `creator_profile` artifact. If bio URLs exist, the agent expands them (following linktree/beacons/redirects), producing a `bio_link_urls` artifact with links categorized by recipe relevance. If a high-relevance recipe link is found (e.g. creator's recipe blog), the agent follows it with `httpx_fetch` and uses the webpage extraction tools. If the creator has a website but no direct recipe link, `discover_recipe_on_site` searches the site for a recipe matching the video content. The agent uses LLM reasoning to decide which bio links to follow and when to give up and fall back to caption/video extraction.

**Design rule:** Do not blindly crawl everything in a linktree. The agent should prioritize links categorized as `recipe_blog` or `website_home`, skip links categorized as `shop` or `social_profile`, and use LLM reasoning only when link categorization is ambiguous.

#### Social URL — TikTok

Acquisition tool: yt-dlp (public posts only).

| Priority | Method key | Description |
|---|---|---|
| 1 | `recipe_link_from_caption` | Scan description for linked recipe page URL, follow with httpx |
| 2 | `creator_bio_link_resolution` | Fetch creator profile, expand bio/linktree links, find recipe-relevant URLs |
| 3 | `creator_site_recipe_discovery` | Search creator's website for a recipe matching video content |
| 4 | `structured_recipe_text_from_caption` | Extract recipe structure from description text (often short on TikTok) |
| 5 | `video_audio_transcription` | Download video via yt-dlp, transcribe audio via Whisper |
| 6 | `video_frame_text_extraction` | Extract key frames, use multimodal LLM to read text overlays |
| 7 | `combined_video_extraction` | Merge transcript + frame text, run LLM structured extraction |

Note: TikTok descriptions tend to be shorter than Instagram captions. Bio link resolution (methods 2–3) is often the best path after direct caption links, because many TikTok creators link to their recipe blog in bio while keeping video descriptions minimal. The video processing path (methods 5–7) is the most commonly needed fallback for TikTok.

#### Social URL — Facebook

Acquisition tool: yt-dlp (public videos/posts only).

| Priority | Method key | Description |
|---|---|---|
| 1 | `recipe_link_from_caption` | Scan post text for linked recipe page URL, follow with httpx |
| 2 | `creator_bio_link_resolution` | Fetch creator profile/page info, find website or recipe links |
| 3 | `creator_site_recipe_discovery` | Search creator's website for matching recipe |
| 4 | `structured_recipe_text_from_caption` | Extract recipe structure from post text via LLM |
| 5 | `video_audio_transcription` | Download video via yt-dlp, transcribe audio via Whisper |
| 6 | `video_frame_text_extraction` | Extract key frames, use multimodal LLM to read text overlays |
| 7 | `combined_video_extraction` | Merge transcript + frame text, run LLM structured extraction |

Note: Facebook has the most restrictive access. Private group content and login-gated posts are not accessible. Facebook pages and public profiles are more likely to have website links than Instagram bio links. The `parseability_assessment` should detect and report inaccessible content clearly.

#### Recipe webpage URL

Acquisition tool: httpx.

| Priority | Method key | Description |
|---|---|---|
| 1 | `schema_recipe_markup` | Use JSON-LD / schema.org recipe data if present |
| 2 | `structured_page_extraction` | Extract from cleaned page content sections |
| 3 | `llm_page_extraction` | LLM-assisted extraction from full page text |

#### Image

Acquisition tool: direct file from S3 (user uploaded via presigned URL).

| Priority | Method key | Description |
|---|---|---|
| 1 | `printed_text_ocr_extraction` | Google Cloud Vision OCR + structured extraction for printed/screenshot text |
| 2 | `handwritten_ocr_extraction` | Google Cloud Vision handwriting OCR + assisted extraction |
| 3 | `llm_image_extraction` | Send image directly to multimodal LLM for extraction |

#### Text

Acquisition tool: raw text from SourceAsset.

| Priority | Method key | Description |
|---|---|---|
| 1 | `structured_text_parsing` | Parse well-structured pasted recipe text |
| 2 | `llm_text_extraction` | LLM-assisted extraction from freeform text |

### 6.3 Video processing pipeline (social platforms)

When caption/link-based methods are insufficient and the fallback ladder reaches video processing, the following pipeline executes:

**Step 1 — Video download.** yt-dlp downloads the video file to temporary storage. Metadata (duration, resolution) is captured.

**Step 2 — Audio extraction + transcription.** Audio track is extracted and sent to OpenAI Whisper API for transcription. Returns timestamped text segments.

**Step 3 — Key frame extraction.** Video is sampled at 2–3 second intervals. Frames are filtered for those containing visible text (simple heuristic or lightweight text detection).

**Step 4 — Frame text extraction.** Selected frames are sent to multimodal LLM (Claude or GPT-4o vision) to extract visible text overlays — ingredient lists, measurements, step instructions.

**Step 5 — Content merging.** Audio transcript and frame-extracted text are combined into a unified text document, deduplicated where audio and visual text overlap.

**Step 6 — Structured extraction.** Combined text is processed through the standard LLM extraction step to produce a RecipeCandidate.

Steps 2–3 run in parallel to minimize total processing time.

**Temporary storage:** Downloaded videos and extracted frames are stored temporarily and cleaned up after candidate creation. These are not persisted as NormalizedSourceArtifacts — only the resulting transcript and extracted text are stored as artifacts.

**Cost and time expectations:** This is the most expensive ingestion path. Expected processing time: 30–60 seconds. Expected cost: Whisper API call + 5–15 multimodal LLM frame calls + 1 extraction LLM call. The SSE event stream should surface clear progress indicators throughout.

**Review mode:** Recipes extracted via video processing always use `reconstruction` review mode. Confidence is expected to be lower than caption or linked-page extraction.

### 6.3 Stop conditions

The fallback ladder stops when one of these is met:
1. A canonical-eligible candidate is produced
2. No stronger feasible method remains and a draft-eligible candidate exists
3. All methods are exhausted with no usable candidate (job → `unsupported`)

### 6.4 Assessment model

**Hybrid assessment:** Light pre-check before extraction (source viability, routing decision). Deeper assessment after extraction (completeness, structural sanity, review mode, eligibility).

**Canonical eligibility rules:**
- Non-empty title
- At least 1 ingredient row
- At least 1 step block
- Ingredient rows contain usable text (not garbage fragments)
- Steps contain usable text
- No fatal blocking issue from parser
- Minimum thresholds are configurable

### 6.5 Cost principle

Minimize LLM/OCR calls per ingestion:
1. Use deterministic/non-LLM steps first (domain detection, metadata fetch, schema markup, transcript API, heuristic classification)
2. Use OCR only when the source is an image
3. Use a single LLM extraction pass to turn evidence into a structured candidate
4. Use rule-based quality assessment, not another LLM pass

---

## 7. API surface — Phase 1

### 7.1 Ingestion APIs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/ingestion` | Submit source, create SourceAsset + IngestionJob |
| GET | `/api/ingestion/jobs/{jobId}` | Fetch current job snapshot (for page refresh / reconnect) |
| GET | `/api/ingestion/jobs/{jobId}/events` | SSE stream for job progress updates |
| POST | `/api/ingestion/jobs/{jobId}/rerun` | Rerun (only if `rerunAllowed = true`). Creates new job. |

### 7.2 Candidate APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/recipe-candidates/{candidateId}` | Fetch candidate for review (includes review context) |
| POST | `/api/recipe-candidates/{candidateId}/decision` | Submit review decision: `save_canonical`, `save_draft`, `discard` with edited fields |

### 7.3 Draft APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/drafts/{draftId}` | Fetch draft |
| PATCH | `/api/drafts/{draftId}` | Update draft fields |
| POST | `/api/drafts/{draftId}/review-for-canonical` | Trigger promotion assessment |
| POST | `/api/drafts/{draftId}/promote` | Confirm promotion to canonical |

### 7.4 Recipe APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/recipes` | List recipes (supports filter by status, tags, search) |
| GET | `/api/recipes/{recipeId}` | Fetch recipe detail |
| PATCH | `/api/recipes/{recipeId}` | Edit recipe (backend determines revision-worthiness) |
| GET | `/api/recipes/{recipeId}/revisions` | List revision history |
| POST | `/api/recipes/{recipeId}/revisions/{revisionId}/restore` | Restore old version (creates new current) |

### 7.5 Media APIs

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/media/presigned-url` | Generate presigned S3 upload URL |
| POST | `/api/recipes/{recipeId}/media` | Register uploaded media on a recipe |
| PATCH | `/api/recipes/{recipeId}/media/{mediaId}` | Update role (e.g. set as hero) |
| DELETE | `/api/recipes/{recipeId}/media/{mediaId}` | Remove media |

### 7.6 Journal APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/recipes/{recipeId}/journal` | List journal entries (newest first) |
| POST | `/api/recipes/{recipeId}/journal` | Create journal entry (body, cookedOn, tags, up to 2 images) |
| DELETE | `/api/journal/{entryId}` | Delete journal entry + associated media |

### 7.7 Tag APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/tags?domain=recipe` | List tags by domain |
| POST | `/api/tags` | Create tag (if not exists in domain, create; if exists, return existing) |

### 7.8 Ingredient APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/ingredients?search=...&category=...` | Search ingredient DB (optional category filter) |
| POST | `/api/ingredients` | Create new ingredient (category required) |
| PATCH | `/api/ingredients/{ingredientId}` | Update aliases and/or category |

---

## 8. SSE event model

### Endpoint
`GET /api/ingestion/jobs/{jobId}/events`

### Event types

```typescript
type IngestionSSEEvent = {
  eventType:
    | "job.started"
    | "job.state_changed"
    | "job.plan_built"
    | "job.method_started"
    | "job.method_succeeded"
    | "job.method_failed"
    | "job.method_skipped"
    | "job.review_ready"
    | "job.draft_ready"
    | "job.failed"
    | "job.unsupported";

  jobId: string;
  sequence: number;
  timestamp: string;
  status: string;
  internalState?: string;
  methodKey?: string;
  candidateId?: string | null;
  rerunAllowed?: boolean;
  errorType?: string | null;
  errorCode?: string | null;
};
```

### User-facing status display mapping

Maintained in `/packages/shared` or `/packages/contracts`, not in the backend:

| Status | Display label |
|---|---|
| `queued` | Waiting to start |
| `processing` | Reading source / Extracting recipe / Preparing review |
| `review_ready` | Ready for review |
| `draft_ready` | Can be saved as draft |
| `failed` | We hit a system issue |
| `unsupported` | Couldn't extract a usable recipe |

### Reconnection

On SSE disconnect, the client fetches the current job snapshot via `GET /api/ingestion/jobs/{jobId}` and resumes. The `stateHistory` on the job object provides catch-up context.

---

## 9. Key architectural decisions

| Decision | Choice | Rationale |
|---|---|---|
| Pipeline vs CRUD architecture | Pipeline | Kama's core is content processing, not form submission |
| Raw/intermediate/trusted separation | Three-layer | Trust model requires clear boundaries |
| Source-specific processors | Common contract, isolated implementations | Clean routing, no conditional spaghetti |
| Fallback planning | Fixed catalog + feasible subset | Predictable, debuggable, sufficient for Phase 1 |
| Artifact storage | Modular typed objects | One artifact per concern, typed by `artifactType` |
| State signaling | 4 layers (status, internalState, internalErrorState, errorType) | Clean separation of user-facing, internal, and error concerns |
| Provenance | First-class, field-level | Core product theme for trust and debugging |
| Confidence | Candidate-only, dropped on canonical save | After user review, confidence is no longer meaningful |
| Draft as distinct object | Yes | Clear trust boundary, not just a status flag |
| Ingredient as global entity | Yes | Foundation for pantry, shopping, meal planning |
| Cook journal | Separate from revisions | Different jobs: lived experience vs content maintenance |
| Tag domains | Shared infra, split vocabularies | Recipe and journal tags serve different purposes |
| Auth | Clerk with JWT verification | Token-based works for web + future mobile |
| File upload | Presigned S3 URLs | Client uploads directly, backend stays lean |
| Realtime updates | SSE | Sufficient for server→client ingestion updates |
| **Job dispatch (as-built)** | **`background_runner.enqueue`** (in-process `asyncio`) | Long work off request thread; avoids dev **BrokenPipe** issues with separate worker processes; **Redis** still for SSE pub/sub — see **§1.0** |
| **Job dispatch (revisit)** | **Dramatiq + Redis broker** | Optional when scaling workers, broker durability, or CPU isolation from HTTP |
| Rerun policy | Internal failures only, full pipeline re-trigger | Prevents hiding quality issues behind retry |
| Review modes | Quick / Standard / Reconstruction | Source quality determines review intensity |

---

## 10.1 Ingredient DB — Seeding and growth strategy

### Initial seed

Ship a curated base set of ~300–500 common cooking ingredients covering pantry staples, proteins, produce, dairy, spices, herbs, grains, and condiments across major cuisines. Each entry includes a canonical name, an `IngredientCategory` value, and known aliases. Every seed ingredient must have a category assigned.

**Source options for the seed set (choose one or combine):**
- Curate manually from established recipe databases or ingredient taxonomies
- Extract from a public ingredient dataset (e.g. USDA FoodData Central ingredient names, Open Food Facts)
- Generate via LLM with manual review and deduplication

All seed entries are marked `createdBySystem: true`.

### Growth during ingestion

When the extraction pipeline produces ingredient rows for a RecipeCandidate, it attempts to map each row to an existing Ingredient record:

1. **Exact match** — Canonical name matches (case-insensitive, trimmed)
2. **Alias match** — Any alias matches
3. **Fuzzy match** — Lightweight similarity check (e.g. Levenshtein or trigram) to suggest a likely match with lower confidence
4. **No match** — Flag as unmapped; create a new Ingredient record if the text looks like a real ingredient

During review, the user sees the proposed mapping and can:
- Accept the mapping
- Change it to a different existing ingredient
- Create a new ingredient entry
- Leave it unmapped

User-created ingredients are marked `createdBySystem: false` with `createdByUserId` set.

### Alias accumulation

When a user confirms that a recipe line maps to an existing ingredient under a different name (e.g. "spring onion" → existing "green onion"), the system can add the new name as an alias on that ingredient. This improves future matching without manual alias management.

### What is deferred
- Nutrition data linkage
- Brand-specific ingredient variants
- Quantity normalization and unit conversion
- Pantry management (Phase 2)

---

### Priority 1 — Ingestion backbone
- SourceAsset, IngestionJob persistence
- NormalizedSourceArtifact storage
- Extraction plan model
- SSE event emission
- Job worker execution

### Priority 2 — Recipe webpage extraction (gold path)
- URL metadata fetch
- Cleaned page text extraction
- Schema markup detection
- LLM extraction fallback
- RecipeCandidate creation with provenance

### Priority 3 — Review + save flow
- Candidate fetch API
- Review decision API (canonical / draft / discard)
- CanonicalRecipe + DraftRecipe persistence
- Revision creation on edit
- Ingredient DB seeding + mapping (see section 9.1)

### Priority 4 — Text and image ingestion
- Pasted text extraction
- OCR pipeline for printed/screenshot images
- Handwritten OCR with reconstruction review mode

### Priority 5 — YouTube + social media ingestion
- YouTube metadata, transcript, and linked recipe extraction via Data API + youtube-transcript-api
- Social media metadata and caption extraction via yt-dlp (Instagram, TikTok, Facebook)
- Caption link following and caption text extraction methods
- Video processing pipeline: yt-dlp download → Whisper transcription → key frame extraction → multimodal LLM text extraction → content merging
- Fallback ladder execution across all social platform method catalogs
- `reconstruction` review mode for video-extracted candidates

### Priority 6 — Recipe library + detail + journal
- Recipe list/filter/search API
- Recipe detail page
- Recipe media management
- Cook journal CRUD
- Tag system

### Priority 7 — Draft promotion
- Draft editing
- Promotion assessment
- Promotion review + canonical creation
- Draft deletion post-promotion

---

## 11. Deferred technical decisions

| Topic | Status |
|---|---|
| Artifact/source retention and expiry policy | Deferred post-MVP. Model includes `expiresAt` field. |
| Revision retention rules (e.g. keep last N) | Deferred. Not a user-facing promise. |
| Duplicate/near-duplicate detection | Deferred to Phase 2+. |
| Ingredient quantity normalization | Deferred. Stored as raw string. |
| Unit normalization | Deferred. Stored as raw string. |
| Multi-recipe extraction per source | Deferred. MVP = one recipe per source. |
| Reviewer agent for automated quality assessment | Deferred. `reviewMode` preserved as a future hook. |
| Recipe embedding generation | Phase 2 (needed for Ask/Create). pgvector ready. |
| Full-text search implementation | Phase 2. Basic tag/title filtering in Phase 1. |

## 12. Infrastructure decisions to finalize during development

These are real decisions but none block initial development. Lock them as you reach the relevant implementation work.

| Topic | Recommendation | When to decide |
|---|---|---|
| Structured logging | Python `structlog` | When first service is running |
| Testing strategy | pytest (backend), Vitest (frontend), Playwright (e2e later) | Before first PR |
| CI/CD | GitHub Actions | After first working deploy |
| Rate limiting | `slowapi` FastAPI middleware | When API is exposed publicly |
| Image thumbnailing | S3 + CloudFront transforms or Pillow on upload | When library view needs optimized images |
| Error tracking | Sentry | After first deploy |
| API versioning | Prefix routes `/api/v1/` from day one if desired | Before first deploy |
| Ingredient DB seed source | USDA FoodData Central names + LLM curation | In parallel with Priority 3 implementation |
| Playwright fallback for JS-rendered recipe pages | Add as secondary URL processor variant | When simple httpx fetching proves insufficient |
