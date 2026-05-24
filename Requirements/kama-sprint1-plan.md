# Kama — Phase 1 Task Plan

**Format:** Task Master compatible — tasks with IDs, subtasks, dependencies, acceptance criteria.  
**Source:** PRD, Technical ACR, API Contracts, Frontend Screens doc.  
**Priority tiers:** P0 (scaffold) → P1 (agent backbone) → P2 (webpage extraction) → P3 (review agent + save flow) → P4 (text + image ingestion) → P5 (YouTube + social ingestion) → P6 (library + detail + journal) → P7 (draft promotion)

### Background jobs — implementation note (May 2026)

**As-built:** Ingestion, journal-summary regen, and search indexing use **`app.services.background_runner.enqueue`** (in-process **`asyncio`** on the FastAPI/uvicorn process). **Redis** is still used for **SSE pub/sub**. **Dramatiq** is **not** a runtime dependency.

**Why:** Separate worker subprocesses caused **logging / BrokenPipe** issues in dev when killed; single-process async avoided that.

**Revisit:** **Dramatiq + Redis broker** remains the documented upgrade path for dedicated workers and broker durability (see **Phase 1 ACR §1.0** and **§2 — Background jobs (reference / revisit)**).

**Dev scripts:** Use **`pnpm dev:apps`** (web + FastAPI); no `dramatiq app.workers` process.

Tasks **T-008.8**, **T-011**, **T-014**, **T-015.8**, **T-042–T-043**, **T-051** below retain original wording where helpful; sub-bullets marked **(as-built)** or **(revisit)** describe what shipped vs. optional future.

---

## P0 — Project scaffolding

### T-001: Initialize monorepo
**Description:** Set up Turborepo + pnpm workspaces with all package and app directories.
**Dependencies:** None
**Subtasks:**
- T-001.1: Init git repo with `.gitignore` (node_modules, .env, __pycache__, .venv, dist)
- T-001.2: Init pnpm workspace — `pnpm-workspace.yaml` referencing `apps/*` and `packages/*`
- T-001.3: Create `turbo.json` with task pipeline: build (depends on ^build), dev, typecheck, lint
- T-001.4: Create root `package.json` with workspace scripts (`dev`, `build`, `typecheck`, `lint`, `dev:all`)
- T-001.5: Verify `pnpm install` runs clean from root

**Acceptance:** `pnpm install` succeeds. `turbo build` runs (even if packages are empty). Workspace structure matches ACR section 3.

---

### T-002: Set up /packages/contracts
**Description:** Shared TypeScript domain types, DTOs, and enums used by web and api-client.
**Dependencies:** T-001
**Subtasks:**
- T-002.1: Init package with `package.json`, `tsconfig.json`
- T-002.2: Create `/src/domain/` — SourceAsset, IngestionJob, RecipeCandidate, DraftRecipe, CanonicalRecipe, RecipeRevision, RecipeMedia, Ingredient, CookJournalEntry, JournalEntryMedia, Tag types
- T-002.3: Create `/src/enums/` — JobStatus, InternalState, InternalErrorState, ErrorType, ArtifactType, ReviewMode, SourceType, MediaRole, TagDomain
- T-002.4: Create `/src/api/` — Request/response DTOs matching API contracts doc (ingestion, candidates, recipes, drafts, journal, tags, ingredients, media)
- T-002.5: Create `/src/schemas/` — Zod schemas for runtime validation if desired
- T-002.6: Export barrel file (`/src/index.ts`)
- T-002.7: Verify package builds with `turbo build`

**Acceptance:** All Phase 1 domain types from ACR section 4 are defined. All API DTOs from API contracts doc are defined. Package builds and exports cleanly.

---

### T-003: Set up /packages/api-client
**Description:** Typed FastAPI client wrappers and SSE subscription helpers.
**Dependencies:** T-002
**Subtasks:**
- T-003.1: Init package with `package.json`, `tsconfig.json`
- T-003.2: Create base client with configurable base URL + auth token attachment
- T-003.3: Create `/src/ingestion.ts` — `submitSource()`, `getJobStatus()`, `rerunJob()`
- T-003.4: Create `/src/sse.ts` — SSE subscription helper for ingestion job events, with reconnection logic (falls back to snapshot GET on disconnect)
- T-003.5: Create `/src/recipeCandidates.ts` — `getCandidate()`, `submitDecision()`
- T-003.6: Create `/src/recipes.ts` — `listRecipes()`, `getRecipe()`, `updateRecipe()`, `listRevisions()`, `restoreRevision()`
- T-003.7: Create `/src/drafts.ts` — `getDraft()`, `updateDraft()`, `reviewForCanonical()`, `promote()`
- T-003.8: Create `/src/journal.ts` — `listEntries()`, `createEntry()`, `deleteEntry()`
- T-003.9: Create `/src/tags.ts` — `listTags()`, `createOrReuseTag()`
- T-003.10: Create `/src/ingredients.ts` — `searchIngredients()`, `createIngredient()`
- T-003.11: Create `/src/media.ts` — `getPresignedUrl()`, `registerMedia()`, `updateMedia()`, `deleteMedia()`
- T-003.12: Export barrel file

**Acceptance:** Every Phase 1 API endpoint from the API contracts doc has a typed client function. SSE helper handles connection, reconnection, and event parsing.

---

### T-004: Set up /packages/shared
**Description:** Non-visual shared utilities, constants, and helpers.
**Dependencies:** T-002
**Subtasks:**
- T-004.1: Init package with `package.json`, `tsconfig.json`
- T-004.2: Create `/src/constants/` — job status display label mapping, review mode labels, error type labels
- T-004.3: Create `/src/utils/` — date formatting, time display helpers (e.g. "20 min"), ingredient text formatting
- T-004.4: Create `/src/query/` — TanStack Query key factories (`recipeKeys`, `jobKeys`, `tagKeys`, etc.)
- T-004.5: Export barrel file

**Acceptance:** Status-to-display mappings match API contracts doc SSE section. Query key factories cover all API data types.

---

### T-005: Set up /packages/ui
**Description:** Shared design system — tokens, primitives, and cross-platform components.
**Dependencies:** T-001
**Subtasks:**
- T-005.1: Init package with `package.json`, `tsconfig.json`
- T-005.2: Create `/src/tokens/` — color palette, typography scale, spacing scale, border radii, shadow definitions (platform-agnostic format)
- T-005.3: Create `/src/primitives/` — Button (with loading, disabled states), Input, Textarea, Badge, Chip/Tag
- T-005.4: Create `/src/components/` — placeholder structure for RecipeCard, IngredientRow, StepRow, JournalEntryCard (implementation after v0 design phase)
- T-005.5: Set up component pattern: `Button/index.ts`, `Button.tsx`, `Button.native.tsx` (native placeholder), `types.ts`

**Acceptance:** Token definitions exist and are importable. At least Button and Input are functional web components. Package builds.

---

### T-006: Set up Next.js web app
**Description:** Configure `/apps/web` with Tailwind, Clerk auth, TanStack Query, and basic routing.
**Dependencies:** T-002, T-004, T-005
**Subtasks:**
- T-006.1: Create Next.js app with App Router (if not done in T-001)
- T-006.2: Configure Tailwind with design tokens from `/packages/ui/tokens` mapped into `tailwind.config.ts`
- T-006.3: Install and configure Clerk — wrap app in `<ClerkProvider>`, add sign-in/sign-up pages, protect routes with middleware
- T-006.4: Install and configure TanStack Query — `QueryClientProvider` in root layout
- T-006.5: Create app layout shell — sidebar or top nav with: Recipes, Ingest links. Placeholder pages for each route.
- T-006.6: Create route stubs for all Phase 1 routes: `/recipes`, `/recipes/[id]`, `/recipes/[id]/edit`, `/drafts/[id]`, `/drafts/[id]/promote`, `/ingest`, `/ingest/[jobId]`, `/ingest/[jobId]/review`
- T-006.7: Verify Clerk auth flow works — sign in → see protected page → sign out
- T-006.8: Verify TanStack Query is wired — create a test query against FastAPI health check

**Acceptance:** App runs at localhost. Auth works. All Phase 1 routes exist as placeholder pages. TanStack Query can fetch from backend.

---

### T-007: Set up FastAPI backend
**Description:** Configure `/backend` with project structure, database, auth middleware, and core infrastructure.
**Dependencies:** T-001
**Subtasks:**
- T-007.1: Create FastAPI application entry point (`/backend/app/main.py`) with CORS middleware, health check endpoint
- T-007.2: Create `/backend/app/core/config.py` — Pydantic Settings loading from env vars (DB URL, Redis URL, Clerk JWKS URL, S3 config, API keys)
- T-007.3: Create `/backend/app/core/database.py` — SQLAlchemy async engine, session factory, Base model
- T-007.4: Create `/backend/app/core/auth.py` — Clerk JWT verification dependency using JWKS endpoint. FastAPI `Depends()` that extracts and validates user ID from Bearer token.
- T-007.5: Create directory structure: `/api`, `/core`, `/domain`, `/models`, `/schemas`, `/services`, `/agents`, `/tools`, `/workers`, `/repositories`
- T-007.6: Install additional dependencies: `pydantic-ai`, `tenacity`, `structlog`, `google-cloud-vision`, `yt-dlp`, `openai` (for Whisper + embeddings)
- T-007.7: Configure `structlog` for structured JSON logging
- T-007.8: Verify auth middleware — protected endpoint returns 401 without token, 200 with valid Clerk token

**Acceptance:** FastAPI runs. CORS allows requests from Next.js origin. Auth middleware validates Clerk JWTs. Structured logging works. All directories exist.

---

### T-008: Docker Compose + Dockerfile
**Description:** Local infrastructure containers and backend deployment image.
**Dependencies:** T-007
**Subtasks:**
- T-008.1: Create `docker-compose.yml` at repo root with Postgres (pgvector/pgvector:pg16) and Redis (redis:7-alpine). Persistent volumes for Postgres data.
- T-008.2: Create `/backend/Dockerfile` — Python 3.12 slim, install ffmpeg, install uv, copy deps, copy code, expose 8000, uvicorn CMD
- T-008.3: Add `.env.example` with all required env vars documented
- T-008.4: Create `.env` for local dev (gitignored) with Postgres, Redis, Clerk, S3 config
- T-008.5: Verify `docker compose up -d` starts Postgres and Redis
- T-008.6: Verify FastAPI connects to Dockerized Postgres and Redis
- T-008.7: Verify `docker build` succeeds for backend image
- T-008.8: Add root-level `dev:apps` (or `dev:all`) using `concurrently`: Docker infra + Next.js + FastAPI **(as-built: no separate Dramatiq process; ingestion runs in-process — see header note)**

**Acceptance:** `docker compose up -d && pnpm dev:apps` starts stack. FastAPI connects to Postgres. Redis is reachable (SSE pub/sub). Backend Docker image builds.

---

### T-009: Database migrations — core tables
**Description:** Alembic setup and initial migration with all Phase 1 tables.
**Dependencies:** T-007, T-008
**Subtasks:**
- T-009.1: Init Alembic in `/backend` — `alembic init alembic`, configure `alembic.ini` to read DB URL from env
- T-009.2: Create SQLAlchemy models for: `SourceAsset`, `IngestionJob`, `NormalizedSourceArtifact`, `RecipeCandidate`
- T-009.3: Create SQLAlchemy models for: `CanonicalRecipe`, `DraftRecipe`, `RecipeRevision`, `RecipeMedia`
- T-009.4: Create SQLAlchemy models for: `Ingredient`, `Tag`, `CookJournalEntry`, `JournalEntryMedia`
- T-009.5: IngestionJob model includes: JSONB columns for `extractionPlan`, `stateHistory`, `metadata`; `lastHeartbeatAt` timestamp
- T-009.6: RecipeCandidate model includes: JSONB columns for `ingredients`, `steps`, `fieldConfidenceMap`, `fieldProvenanceMap`, `reviewFindings`
- T-009.7: CanonicalRecipe model includes: JSONB columns for `ingredients`, `steps`, `fieldProvenanceMap`; nullable `journalSummary` text column
- T-009.8: Tag model with `domain` enum column (recipe / journal)
- T-009.9: Generate initial Alembic migration: `alembic revision --autogenerate -m "initial schema"`
- T-009.10: Run migration: `alembic upgrade head` — verify all tables created
- T-009.11: Create indexes: IngestionJob.status, IngestionJob.sourceAssetId, CanonicalRecipe.userId, Tag.domain, CookJournalEntry.canonicalRecipeId

**Acceptance:** `alembic upgrade head` creates all 12 tables. Schema matches ACR domain model section 4. JSONB columns for rich objects. Indexes for common query patterns.

---

### T-010: S3 presigned URL endpoint
**Description:** Backend endpoint for generating presigned upload URLs. Client uploads directly to S3.
**Dependencies:** T-007
**Subtasks:**
- T-010.1: Add `boto3` dependency
- T-010.2: Create S3 client config in `/backend/app/core/s3.py`
- T-010.3: Create `POST /api/media/presigned-url` endpoint — accepts fileName, contentType, context → returns uploadUrl, assetRef, expiresAt
- T-010.4: S3 key format: `{context}/{userId}/{uuid}_{fileName}`
- T-010.5: Verify: call endpoint → receive presigned URL → upload a test file → file appears in S3

**Acceptance:** Endpoint returns valid presigned URL. Direct upload to S3 succeeds. AssetRef is usable for later media registration.

---

### T-011: Background worker execution (`background_runner` + Redis SSE)
**Description:** Run ingestion (and related jobs) **outside the HTTP request**, with progress visible via SSE. **As-built:** `background_runner.enqueue` schedules **`asyncio`** tasks in the **FastAPI process**; **`run_ingestion_send(job_id)`** replaces a Dramatiq `.send()`. **Redis** is used for **SSE pub/sub** (not as a Dramatiq broker). **Revisit:** wire the same coroutines behind **Dramatiq + Redis** if you need a separate worker fleet.

**Dependencies:** T-007, T-008
**Subtasks:**
- T-011.1: ~~Configure Dramatiq broker~~ **(revisit)** — ensure **Redis** URL in env for **SSE** (`sse_service` pub/sub)
- T-011.2: Create `/backend/app/workers/ingestion_worker.py` — **`run_ingestion_send`** → **`enqueue(_run_ingestion, job_id)`**; `_run_ingestion` runs **`run_ingestion_agent`**
- T-011.3: ~~Stub actor~~ **Superseded** — full agent pipeline drives job status to `review_ready` / `draft_ready` / terminal errors
- T-011.4: Create `/backend/app/workers/journal_summary_worker.py` — **`regenerate_journal_summary_send`** → **`enqueue`**
- T-011.5: Create `/backend/app/workers/reaper_worker.py` — **`run_reaper_loop`** as **lifespan** `asyncio` task (stuck jobs: `lastHeartbeatAt` threshold)
- T-011.6: Verify: **`POST /api/ingestion`** → job moves to `processing` → completes; DB and SSE reflect state
- T-011.7: ~~`dramatiq app.workers`~~ **(revisit)** — **as-built:** only **uvicorn** required; optional second process if Dramatiq returns

**Acceptance:** Ingestion runs after POST without blocking the response. SSE streams events. Reaper runs. **(Optional)** Dramatiq reintroduction documented in ACR §1.0 / §2.

---

### T-012: PydanticAI integration
**Description:** Set up PydanticAI with Claude Sonnet and create the base agent scaffolding.
**Dependencies:** T-007
**Subtasks:**
- T-012.1: Add `pydantic-ai` dependency (if not already in T-007)
- T-012.2: Create `/backend/app/agents/base.py` — shared AgentContext model (job reference, existing artifacts, completed tools, iteration count)
- T-012.3: Create `/backend/app/agents/ingestion_agent.py` — PydanticAI agent definition with Claude Sonnet model, system prompt placeholder, empty tool catalog
- T-012.4: Create `/backend/app/agents/review_agent.py` — PydanticAI agent definition with system prompt placeholder, empty tool catalog
- T-012.5: Create `/backend/app/tools/base.py` — ToolResult type definition (success, artifacts, candidateUpdate, signals)
- T-012.6: Verify: create agent instance → run with a test prompt → receive structured response

**Acceptance:** PydanticAI agent initializes with Claude Sonnet. Agent can be invoked and returns a response. AgentContext and ToolResult types are defined. Both agent definitions exist (empty tool catalogs to be populated in later tasks).

---

### T-013: SSE endpoint
**Description:** Server-Sent Events endpoint for ingestion job progress streaming.
**Dependencies:** T-007, T-009
**Subtasks:**
- T-013.1: Create `GET /api/ingestion/jobs/{jobId}/events` SSE endpoint using FastAPI's `StreamingResponse` with `text/event-stream` content type
- T-013.2: Create SSE event emitter service — writes events to a Redis pub/sub channel keyed by jobId
- T-013.3: SSE endpoint subscribes to the Redis channel and streams events to client
- T-013.4: Define event serialization: `event: {eventType}\ndata: {json payload}\n\n`
- T-013.5: Include CORS headers for SSE endpoint
- T-013.6: Verify: publish test event to Redis channel → SSE client receives it

**Acceptance:** SSE endpoint streams events. Events match the schema from API contracts (eventType, jobId, sequence, timestamp, status). Redis pub/sub delivers events from worker to API server.

---

### T-014: Core ingestion API endpoints
**Description:** The submission and job tracking endpoints (without agent logic).
**Dependencies:** T-009, T-011, T-013
**Subtasks:**
- T-014.1: Create `/backend/app/repositories/source_asset_repo.py` — create, get_by_id
- T-014.2: Create `/backend/app/repositories/ingestion_job_repo.py` — create, get_by_id, update_status, update_heartbeat, find_stuck
- T-014.3: Create `/backend/app/schemas/ingestion.py` — Pydantic request/response models for ingestion submission and job status
- T-014.4: Create `POST /api/ingestion` — validate input, create SourceAsset, create IngestionJob (status: queued), **`run_ingestion_send(job_id)`** (background task), return sourceAssetId + jobId + sseUrl
- T-014.5: Create `GET /api/ingestion/jobs/{jobId}` — return full job snapshot including extractionPlan, stateHistory, metadata, lastHeartbeatAt
- T-014.6: Create `POST /api/ingestion/jobs/{jobId}/rerun` — verify rerunAllowed, create new IngestionJob linked to same SourceAsset, **`run_ingestion_send(new_job_id)`**, return new jobId
- T-014.7: Add auth dependency to all endpoints

**Acceptance:** POST creates source + job + schedules background ingestion. GET returns full job state. Rerun creates new job. All endpoints require auth. Response shapes match API contracts doc sections 1.1–1.4.

---

## P1 — Ingestion agent backbone

### T-015: Ingestion agent — core loop
**Description:** Replace the stub worker with the real PydanticAI ingestion agent loop.
**Dependencies:** T-011, T-012, T-014
**Subtasks:**
- T-015.1: Create `/backend/app/agents/ingestion_agent.py` — full system prompt describing the agent's role, available tools, decision principles (deterministic by default, LLM when ambiguous), stop conditions
- T-015.2: Implement AgentContext initialization: load job, load existing artifacts (for checkpoint resume), load completed tools
- T-015.3: Implement heartbeat update after each tool call
- T-015.4: Implement SSE event emission within the agent loop: tool_called, tool_succeeded, tool_failed, agent_reasoning, state_changed
- T-015.5: Implement stop condition checks: canonical-eligible candidate, draft-eligible with no better options, all tools exhausted, max iterations (15), wall-clock timeout
- T-015.6: Implement extraction plan creation and dynamic modification (entries with addedBy, status tracking, agentDecision)
- T-015.7: Implement job finalization: update job status (review_ready / draft_ready / failed / unsupported), emit terminal SSE event
- T-015.8: Wire agent into **`_run_ingestion`** / **`run_ingestion_send`** path (in-process worker; **revisit:** Dramatiq actor wrapper)

**Acceptance:** Agent loop runs inside **background ingestion task**. Heartbeat updates on each tool call. SSE events stream to client. Stop conditions enforced. Extraction plan tracked on job. Job reaches terminal state.

---

### T-016: Normalized artifact persistence
**Description:** Service and repository for creating and retrieving typed normalized artifacts.
**Dependencies:** T-009
**Subtasks:**
- T-016.1: Create `/backend/app/repositories/normalized_artifact_repo.py` — create, get_by_id, find_by_job_id
- T-016.2: Create artifact creation helper that accepts typed payloads and persists with correct artifactType
- T-016.3: Verify JSONB payload storage and retrieval for all artifact types
- T-016.4: Link artifact IDs to IngestionJob.normalizedArtifactIds on creation

**Acceptance:** Artifacts are persisted with typed payloads. Retrievable by job ID. Job's normalizedArtifactIds array stays in sync.

---

### T-017: Circuit breaker infrastructure
**Description:** Circuit breaker instances for external services.
**Dependencies:** T-007
**Subtasks:**
- T-017.1: Create `/backend/app/core/circuit_breaker.py` — ServiceCircuitBreaker class with failure_threshold, reset_timeout, is_open(), record_failure(), record_success()
- T-017.2: Create instances: ocr_breaker, whisper_breaker, llm_breaker, youtube_breaker, social_breaker
- T-017.3: Create tenacity retry wrapper factory for external service calls

**Acceptance:** Circuit breakers track failures per service. Open circuit returns immediately. Breakers reset after timeout. Tenacity wrappers configured per ACR section 9.2 retry table.

---

## P2 — Recipe webpage extraction (gold path)

### T-018: classify_source tool
**Description:** Determine source subtype from URL domain or input type.
**Dependencies:** T-012, T-015
**Subtasks:**
- T-018.1: Create `/backend/app/tools/source_tools.py`
- T-018.2: Implement URL domain detection: YouTube, Instagram, TikTok, Facebook, generic webpage
- T-018.3: Implement input type routing: url → URL classifier, image → image classifier, text → text classifier
- T-018.4: Return ToolResult with sourceSubtype and suggested initial tool sequence in signals
- T-018.5: Register as PydanticAI tool on ingestion agent

**Acceptance:** Correctly classifies YouTube, Instagram, TikTok, Facebook URLs by domain. Returns appropriate source subtype. Generic URLs classified as recipe_webpage by default.

---

### T-019: httpx_fetch tool
**Description:** Fetch URL content via httpx with redirect following and timeout handling.
**Dependencies:** T-012, T-017
**Subtasks:**
- T-019.1: Create `/backend/app/tools/fetch_tools.py`
- T-019.2: Implement httpx_fetch: async GET with follow_redirects=True, configurable timeout (15s default), User-Agent header
- T-019.3: Return ToolResult with HTML content, resolved URL, response status
- T-019.4: Signals: has_recipe_schema (quick check for JSON-LD), looks_like_recipe_page, looks_like_recipe_index, page_title
- T-019.5: Wrap with tenacity retry (3 attempts, 1–10s backoff)
- T-019.6: Integrate circuit breaker (not typically needed for general web, but available)
- T-019.7: Create url_metadata artifact from response
- T-019.8: Create source_preview artifact (link_card variant) from page metadata
- T-019.9: Register as PydanticAI tool

**Acceptance:** Fetches pages successfully. Follows redirects. Handles timeouts gracefully. Produces url_metadata and source_preview artifacts. Signals indicate recipe-likeness.

---

### T-020: check_schema_markup tool
**Description:** Look for JSON-LD / schema.org recipe data in fetched HTML.
**Dependencies:** T-019
**Subtasks:**
- T-020.1: Add to `/backend/app/tools/extraction_tools.py`
- T-020.2: Parse HTML for `<script type="application/ld+json">` blocks
- T-020.3: Look for Recipe schema type in JSON-LD
- T-020.4: Return ToolResult: success=true with parsed recipe data in signals if found, success=false if not
- T-020.5: Register as PydanticAI tool

**Acceptance:** Detects JSON-LD recipe markup in real recipe page HTML. Returns structured recipe data when found. Returns clean failure when not found.

---

### T-021: schema_recipe_extract tool
**Description:** Parse a complete recipe candidate from JSON-LD / schema.org markup.
**Dependencies:** T-020
**Subtasks:**
- T-021.1: Add to `/backend/app/tools/extraction_tools.py`
- T-021.2: Map schema.org Recipe fields to RecipeCandidate fields: name→title, recipeIngredient→ingredients, recipeInstructions→steps, prepTime→prepTimeMinutes, cookTime→cookTimeMinutes, recipeYield→servings
- T-021.3: Parse ISO 8601 duration strings (PT30M → 30 minutes)
- T-021.4: Extract recipe images from schema
- T-021.5: Set provenance: sourceType "schema_recipe_markup" for all fields
- T-021.6: Return ToolResult with candidateUpdate and confidence signals
- T-021.7: Register as PydanticAI tool

**Acceptance:** Produces a near-complete RecipeCandidate from well-formed schema markup. Handles common schema variations. Provenance correctly set.

---

### T-022: extract_recipe_links tool
**Description:** Scan text content for URLs that might be recipe pages.
**Dependencies:** T-012
**Subtasks:**
- T-022.1: Add to `/backend/app/tools/source_tools.py`
- T-022.2: URL extraction from text via regex
- T-022.3: Filter for likely recipe URLs (exclude social media, CDNs, tracking links)
- T-022.4: Create linked_recipe_urls artifact
- T-022.5: Register as PydanticAI tool

**Acceptance:** Finds URLs in text content. Filters out obvious non-recipe links. Produces linked_recipe_urls artifact.

---

### T-023: assess_parseability tool
**Description:** Evaluate recipe-likeness and completeness of gathered content.
**Dependencies:** T-012, T-016
**Subtasks:**
- T-023.1: Add to `/backend/app/tools/evaluation_tools.py`
- T-023.2: Check for title, ingredient, and step signals in available artifacts
- T-023.3: Determine reviewMode (quick / standard / reconstruction) based on source quality
- T-023.4: Determine draftEligible and canonicalEligible flags
- T-023.5: Create parseability_assessment artifact
- T-023.6: Register as PydanticAI tool

**Acceptance:** Produces parseability_assessment artifact with correct source subtype, review mode, and eligibility flags.

---

### T-024: llm_structured_extract tool
**Description:** LLM extracts title, ingredients, steps from cleaned text using Claude Sonnet.
**Dependencies:** T-012
**Subtasks:**
- T-024.1: Add to `/backend/app/tools/extraction_tools.py`
- T-024.2: Create extraction prompt template: input is cleaned text, output is structured recipe JSON matching RecipeCandidate fields
- T-024.3: Use PydanticAI structured output with RecipeCandidate Pydantic model for validation
- T-024.4: Map extracted ingredient rows to RecipeIngredientRow (text, quantity, unit)
- T-024.5: Map extracted steps to RecipeStepRow (order, text)
- T-024.6: Set provenance per field based on source artifact
- T-024.7: Wrap with tenacity retry (2 attempts) and circuit breaker
- T-024.8: Return ToolResult with candidateUpdate and confidence signals
- T-024.9: Register as PydanticAI tool

**Acceptance:** Extracts structured recipe from cleaned text. Output validates against RecipeCandidate model. Provenance set. Retries on malformed output.

---

### T-025: evaluate_candidate tool
**Description:** Check candidate completeness, structural sanity, and eligibility.
**Dependencies:** T-012
**Subtasks:**
- T-025.1: Add to `/backend/app/tools/evaluation_tools.py`
- T-025.2: Check: non-empty title, ≥1 ingredient, ≥1 step
- T-025.3: Check structural sanity: ingredient rows have usable text, steps have content
- T-025.4: Determine canonicalEligible and draftEligible
- T-025.5: Generate reviewFindings (structured: code, severity, field, message)
- T-025.6: Return ToolResult with eligibility and findings in signals
- T-025.7: Register as PydanticAI tool

**Acceptance:** Correctly identifies canonical-eligible vs draft-only candidates. Generates meaningful review findings.

---

### T-026: RecipeCandidate persistence
**Description:** Service and repository for creating and retrieving recipe candidates.
**Dependencies:** T-009, T-016
**Subtasks:**
- T-026.1: Create `/backend/app/repositories/recipe_candidate_repo.py` — create, get_by_id
- T-026.2: Create `/backend/app/services/ingestion_service.py` — orchestrates candidate creation from agent results: persists candidate with all fields, provenance, confidence, findings
- T-026.3: Link candidateId to IngestionJob on creation
- T-026.4: Create `GET /api/recipe-candidates/{candidateId}` endpoint — returns full candidate with sourceContext, allowedActions, reviewAgentSummary

**Acceptance:** Candidates persist with full JSONB fields. GET endpoint returns complete review payload matching API contracts doc section 2.1.

---

### T-027: End-to-end webpage ingestion test
**Description:** Verify the full flow: submit URL → agent processes → candidate ready for review.
**Dependencies:** T-015 through T-026
**Subtasks:**
- T-027.1: Submit a real recipe webpage URL via POST /api/ingestion
- T-027.2: Verify SSE events stream: job.started → tool_called (classify) → tool_called (httpx_fetch) → tool_called (check_schema_markup) → tool_called (schema_recipe_extract or llm_structured_extract) → tool_called (evaluate_candidate) → job.review_ready
- T-027.3: Verify GET /api/recipe-candidates returns complete candidate with provenance
- T-027.4: Verify extraction plan entries on job show correct tool sequence and statuses
- T-027.5: Test with: a recipe page with JSON-LD schema, a recipe page without schema (LLM fallback), a non-recipe URL (should reach unsupported)

**Acceptance:** Three test cases pass. SSE events match expected sequence. Candidate has correct provenance. Non-recipe URL is handled gracefully.

---

## P3 — Review agent + review/save flow

### T-028: Review agent implementation
**Description:** PydanticAI review agent with full tool catalog. Runs on every candidate before human review.
**Dependencies:** T-012, T-026
**Subtasks:**
- T-028.1: Create review agent system prompt: role, available tools, principles (fill gaps from evidence, don't invent, mark provenance as review_agent_enriched)
- T-028.2: Implement `lookup_ingredient` tool — search ingredient DB, fix unmapped/mismapped ingredient rows
- T-028.3: Implement `re_read_source_artifact` tool — LLM reads a specific artifact looking for missing info (cook time, prep time, servings)
- T-028.4: Implement `normalize_ingredient_row` tool — fix formatting, standardize unit abbreviations
- T-028.5: Implement `verify_step_coherence` tool — check steps reference existing ingredients, logical order
- T-028.6: Implement `estimate_missing_metadata` tool — find prep/cook time in source artifacts
- T-028.7: Implement `update_candidate_field` tool — modify field with review_agent_enriched provenance
- T-028.8: Implement `add_review_finding` / `resolve_review_finding` tools
- T-028.9: Wire review agent into ingestion pipeline: runs after candidate creation, before job status transitions to review_ready
- T-028.10: Implement safety limits: max 10 tool calls, 30-second wall-clock timeout
- T-028.11: Emit SSE events: review_agent.started, review_agent.tool_called, review_agent.completed (with summary)
- T-028.12: Populate reviewAgentSummary on candidate (fieldsEnriched, ingredientsMapped, findingsResolved, findingsAdded, totalToolCalls, durationMs)

**Acceptance:** Review agent runs on every candidate. Fills gaps from source artifacts. Maps ingredients to ingredient DB. Provenance marked as review_agent_enriched. SSE events stream. Safety limits enforced. reviewAgentSummary populated.

---

### T-029: Ingredient DB setup and seeding
**Description:** Ingredient model, repository, API endpoints, and initial seed data.
**Dependencies:** T-009
**Subtasks:**
- T-029.1: Create `/backend/app/repositories/ingredient_repo.py` — create, search (name + aliases), get_by_id
- T-029.2: Create `GET /api/ingredients?search=...` endpoint
- T-029.3: Create `POST /api/ingredients` endpoint (create new, 409 if exists)
- T-029.4: Create seed script: load 300–500 common ingredients from curated file (JSON/CSV) with names and aliases
- T-029.5: Run seed on first deployment / dev setup via management command
- T-029.6: Verify search matches on canonical names and aliases

**Acceptance:** Ingredient DB seeded with 300+ entries. Search finds ingredients by name and alias. Create endpoint works. API responses match contracts doc section 8.

---

### T-030: Candidate review decision API
**Description:** Endpoint to save candidate as canonical, draft, or discard.
**Dependencies:** T-026, T-029
**Subtasks:**
- T-030.1: Create `/backend/app/schemas/candidates.py` — decision request/response models
- T-030.2: Create `/backend/app/repositories/canonical_recipe_repo.py` — create with full fields, provenance, promotion metadata
- T-030.3: Create `/backend/app/repositories/draft_recipe_repo.py` — create with origin linkage
- T-030.4: Create `POST /api/recipe-candidates/{candidateId}/decision` endpoint
- T-030.5: Handle action=save_canonical: validate canonical eligibility, create CanonicalRecipe with provenance (drop confidence), return canonicalRecipeId
- T-030.6: Handle action=save_draft: create DraftRecipe from edited fields, return draftRecipeId
- T-030.7: Handle action=discard: mark candidate as discarded
- T-030.8: Prevent duplicate decisions (409 if already decided)

**Acceptance:** All three actions work. Canonical save validates eligibility. Provenance retained, confidence dropped. Draft created as distinct object. Response shapes match API contracts doc section 2.2.

---

### T-031: Tag system
**Description:** Tag model, repository, and API endpoints for recipe and journal domains.
**Dependencies:** T-009
**Subtasks:**
- T-031.1: Create `/backend/app/repositories/tag_repo.py` — list_by_domain, find_by_name_and_domain, create
- T-031.2: Create `GET /api/tags?domain=recipe|journal` endpoint
- T-031.3: Create `POST /api/tags` endpoint — create or reuse (return existing if name+domain match, else create new)
- T-031.4: Seed starter recipe tags: "under 30 mins", "vegetarian", "vegan", "kids favorite", "one pot", "high protein", "comfort food", "quick", "meal prep"
- T-031.5: Seed starter journal tags: "tweak", "success", "issue", "would make again", "timing note", "ingredient swap", "family liked it", "too spicy", "took longer"

**Acceptance:** Tags stored with domain. List filters by domain. Create-or-reuse logic works. Seed tags loaded. Response shapes match API contracts doc section 7.

---

## P4 — Text and image ingestion tools

### T-032: Text ingestion tools
**Description:** Tools for processing pasted text sources.
**Dependencies:** T-015, T-024
**Subtasks:**
- T-032.1: Extend classify_source for text input type
- T-032.2: Create cleaned_text artifact from raw input (trim whitespace, normalize line breaks, remove noise)
- T-032.3: Create text_structure_analysis artifact (detect recipe-likeness, probable sections)
- T-032.4: Wire text source through agent: classify → clean → analyze structure → llm_structured_extract → evaluate
- T-032.5: Test with: clean recipe text, messy copy-paste, non-recipe text

**Acceptance:** Pasted recipe text produces a candidate. Non-recipe text reaches unsupported. Messy text produces a draft-eligible candidate.

---

### T-033: OCR tools (Google Cloud Vision)
**Description:** Image ingestion via OCR + LLM extraction.
**Dependencies:** T-015, T-024, T-017
**Subtasks:**
- T-033.1: Create `/backend/app/tools/ocr_tools.py`
- T-033.2: Implement ocr_extract tool: send image to Google Cloud Vision, return text + line blocks + confidence + handwriting detection
- T-033.3: Create ocr_text artifact and image_analysis artifact from results
- T-033.4: Create source_preview artifact (image variant) for uploaded images
- T-033.5: Wrap with tenacity retry (3 attempts) and ocr_breaker circuit breaker
- T-033.6: Implement quality validation: near-empty text → low confidence signal, low OCR confidence → suggestion to try multimodal LLM
- T-033.7: Register ocr_extract as PydanticAI tool
- T-033.8: Wire image source through agent: classify → ocr_extract → assess_parseability → llm_structured_extract → evaluate
- T-033.9: Implement llm_image_extraction fallback: send original image directly to multimodal LLM when OCR quality is too low
- T-033.10: Set reviewMode to "reconstruction" for handwritten sources
- T-033.11: Test with: clear recipe screenshot, printed cookbook page, handwritten recipe card, blurry image

**Acceptance:** OCR extracts text from images. Handwriting detected. Quality signals drive agent decisions. Multimodal fallback works. Handwritten sources get reconstruction review mode.

---

## P5 — YouTube + social media ingestion tools

### T-034: YouTube ingestion tools
**Description:** YouTube-specific tools using Data API and transcript library.
**Dependencies:** T-015, T-019, T-022, T-024
**Subtasks:**
- T-034.1: Implement youtube_api_fetch tool: fetch metadata, description, first comment via YouTube Data API v3
- T-034.2: Create video_metadata artifact from API response
- T-034.3: Implement youtube_transcript_fetch tool: fetch transcript via youtube-transcript-api
- T-034.4: Create video_transcript artifact with timestamped segments
- T-034.5: Wrap both with tenacity retry and youtube_breaker circuit breaker
- T-034.6: Register both as PydanticAI tools
- T-034.7: Wire YouTube flow through agent: classify (youtube) → youtube_api_fetch → extract_recipe_links (in description/comment) → httpx_fetch (linked page) → schema/llm extract → evaluate. Fallback: youtube_transcript_fetch → llm_structured_extract from transcript → evaluate
- T-034.8: Test with: YouTube video with linked recipe blog, YouTube video with recipe in description, YouTube video with transcript only

**Acceptance:** YouTube metadata and transcripts fetched. Linked recipe pages followed preferentially. Transcript fallback works. Three test cases pass.

---

### T-035: Social media ingestion tools
**Description:** Instagram, TikTok, Facebook ingestion via yt-dlp + bio link resolution.
**Dependencies:** T-015, T-019, T-022, T-024, T-017
**Subtasks:**
- T-035.1: Implement yt_dlp_fetch_metadata tool: fetch caption, creator info, thumbnail via yt-dlp for Instagram/TikTok/Facebook
- T-035.2: Create social_caption artifact and video_metadata artifact from yt-dlp output
- T-035.3: Implement fetch_creator_profile tool: get creator profile metadata, bio text, bio URLs
- T-035.4: Create creator_profile artifact
- T-035.5: Implement expand_bio_links tool: follow linktree/beacons/redirect URLs, categorize links by recipe relevance (recipe_blog, website_home, shop, social_profile, other)
- T-035.6: Create bio_link_urls artifact with categorized links and bestRecipeCandidate
- T-035.7: Implement discover_recipe_on_site tool: search creator website for recipe matching video title/caption keywords using httpx fetch + LLM-assisted page matching
- T-035.8: Register all social tools as PydanticAI tools
- T-035.9: Wire social caption flow: classify → yt_dlp_fetch_metadata → extract_recipe_links (caption) → httpx_fetch (linked page) → extract → evaluate
- T-035.10: Wire social bio link flow: → fetch_creator_profile → expand_bio_links → httpx_fetch (best recipe link) → extract → evaluate
- T-035.11: Wire social site discovery flow: → discover_recipe_on_site → httpx_fetch → extract → evaluate
- T-035.12: Test with: Instagram post with recipe link in caption, Instagram post with "link in bio" to recipe blog, TikTok with short caption (no recipe text)

**Acceptance:** Social metadata and captions fetched via yt-dlp. Bio link resolution discovers recipe blogs. Link categorization works. Three test cases pass.

---

### T-036: Video processing tools
**Description:** Video download, audio transcription (Whisper), key frame extraction, frame text analysis.
**Dependencies:** T-035, T-017
**Subtasks:**
- T-036.1: Implement yt_dlp_download_video tool: download video to temp storage, return file path + duration
- T-036.2: Implement whisper_transcribe tool: extract audio → send to OpenAI Whisper API → return timestamped transcript
- T-036.3: Create video_audio_transcript artifact
- T-036.4: Implement extract_key_frames tool: sample frames via ffmpeg-python at 2–3s intervals, filter for frames with likely text content
- T-036.5: Implement llm_frame_extract tool: send selected frames to multimodal LLM, extract visible text with block type classification
- T-036.6: Create video_frame_text artifact
- T-036.7: Implement merge_partial_candidates tool: LLM-assisted merging of partial results from multiple sources (e.g. ingredients from caption + steps from transcript)
- T-036.8: Wrap all with tenacity retry and appropriate circuit breakers
- T-036.9: Register all as PydanticAI tools
- T-036.10: Wire video processing flow: yt_dlp_download_video → whisper_transcribe + extract_key_frames (parallel) → llm_frame_extract → merge_partial_candidates → evaluate
- T-036.11: Temp file cleanup after candidate creation
- T-036.12: Set reviewMode to "reconstruction" for video-extracted candidates
- T-036.13: Test with: recipe reel with spoken instructions + text overlays

**Acceptance:** Video downloads. Audio transcribes. Frames extracted and analyzed. Partial results merged. Temp files cleaned up. Reconstruction review mode set.

---

## P6 — Recipe library + detail + journal

### T-037: Recipe list API
**Description:** Paginated recipe listing with filters, search, and sort.
**Dependencies:** T-009, T-030
**Subtasks:**
- T-037.1: Create `GET /api/recipes` endpoint with query params: status, tags, search, sort, cursor, limit
- T-037.2: Implement cursor-based pagination
- T-037.3: Implement status filter (all / canonical / draft) — query both CanonicalRecipe and DraftRecipe tables when "all"
- T-037.4: Implement tag filter — recipes matching any provided tagIds
- T-037.5: Implement text search — title and description ILIKE
- T-037.6: Implement sort options: updated_desc, created_desc, title_asc
- T-037.7: Return recipe cards with: id, type, title, description, times, servings, heroImageUrl, recipeTags, journalEntryCount

**Acceptance:** Pagination works. All filter combinations work. Response matches API contracts doc section 4.1.

---

### T-038: Recipe detail API
**Description:** Full recipe detail endpoint with media, tags, provenance, journal count.
**Dependencies:** T-030
**Subtasks:**
- T-038.1: Create `GET /api/recipes/{recipeId}` endpoint
- T-038.2: Return composed payload: recipe content, heroImage, gallery, tags (expanded with names), provenance, journalSummary, revisionCount, journalEntryCount
- T-038.3: Handle recipe not found (404)

**Acceptance:** Returns complete recipe detail matching API contracts doc section 4.2.

---

### T-039: Recipe edit API
**Description:** Partial update with automatic revision detection.
**Dependencies:** T-038
**Subtasks:**
- T-039.1: Create `PATCH /api/recipes/{recipeId}` endpoint accepting partial fields
- T-039.2: Create `/backend/app/repositories/recipe_revision_repo.py` — create snapshot
- T-039.3: Determine revision-worthiness: title, ingredients, steps, times, servings changes → create revision. Tag-only changes → no revision.
- T-039.4: Create RecipeRevision snapshot before applying changes
- T-039.5: Return revisionCreated flag and revisionId
- T-039.6: Validate: edit cannot remove all ingredients or steps, cannot blank title

**Acceptance:** Partial updates work. Revisions created for meaningful changes only. Tags don't trigger revisions. Response matches API contracts doc section 4.3.

---

### T-040: Revision history + restore API
**Description:** List revisions and restore a previous version.
**Dependencies:** T-039
**Subtasks:**
- T-040.1: Create `GET /api/recipes/{recipeId}/revisions` endpoint
- T-040.2: Create `POST /api/recipes/{recipeId}/revisions/{revisionId}/restore` endpoint
- T-040.3: Restore creates a new current state (non-destructive) — saves current as new revision, then applies restored content

**Acceptance:** Revision list returns timestamps and change summaries. Restore is non-destructive. Response matches API contracts doc sections 4.4–4.5.

---

### T-041: Recipe media API
**Description:** Media registration, role management, and deletion for recipes.
**Dependencies:** T-010, T-038
**Subtasks:**
- T-041.1: Create `/backend/app/repositories/recipe_media_repo.py` — create, update, delete, find_by_recipe
- T-041.2: Create `POST /api/recipes/{recipeId}/media` — register uploaded media with role and displayOrder
- T-041.3: Create `PATCH /api/recipes/{recipeId}/media/{mediaId}` — update role (hero swap: demote previous hero)
- T-041.4: Create `DELETE /api/recipes/{recipeId}/media/{mediaId}` — remove media record

**Acceptance:** Media registration, hero swap, and deletion work. Response matches API contracts doc section 5.

---

### T-042: Cook journal API
**Description:** Journal entry CRUD with tags and media.
**Dependencies:** T-038, T-031
**Subtasks:**
- T-042.1: Create `/backend/app/repositories/journal_repo.py` — create, delete, list_by_recipe (newest first, cursor pagination)
- T-042.2: Create `GET /api/recipes/{recipeId}/journal` endpoint — paginated, newest first
- T-042.3: Create `POST /api/recipes/{recipeId}/journal` endpoint — body, optional cookedOn, tags, mediaRefs (max 2)
- T-042.4: Create `DELETE /api/journal/{entryId}` endpoint — hard delete entry + associated media
- T-042.5: On journal entry create/delete: trigger async journalSummary regeneration via **`regenerate_journal_summary_send`** (`enqueue`; **revisit:** Dramatiq)

**Acceptance:** Journal CRUD works. Max 2 images enforced. Newest-first ordering. journalSummary regeneration triggered. Response matches API contracts doc section 6.

---

### T-043: Journal summary generation
**Description:** Async LLM-generated journalSummary on canonical recipes.
**Dependencies:** T-042, T-011
**Subtasks:**
- T-043.1: Implement **`journal_summary_worker`**: **`_regenerate_journal_summary`** coroutine + **`regenerate_journal_summary_send`** → **`enqueue`** (**revisit:** Dramatiq actor)
- T-043.2: Load all journal entries for the recipe
- T-043.3: If zero entries, set journalSummary to null
- T-043.4: If entries exist, send to Claude Sonnet with summarization prompt: extract substitutions, timing deviations, family preferences, success/failure patterns, meaningful usage context. Exclude noise.
- T-043.5: Update CanonicalRecipe.journalSummary with generated summary
- T-043.6: Full regeneration from all entries (not incremental)

**Acceptance:** journalSummary generated after journal changes. Captures useful patterns. Excludes noise. Null when no entries exist.

---

## P7 — Draft promotion

### T-044: Draft APIs
**Description:** Draft fetch, edit, and promotion endpoints.
**Dependencies:** T-030
**Subtasks:**
- T-044.1: Create `GET /api/drafts/{draftId}` endpoint
- T-044.2: Create `PATCH /api/drafts/{draftId}` endpoint — partial update, recalculate promotionEligible
- T-044.3: Create `POST /api/drafts/{draftId}/review-for-canonical` — re-assess eligibility, return findings and allowedActions
- T-044.4: Create `POST /api/drafts/{draftId}/promote` — validate eligibility, create CanonicalRecipe with promotion metadata, delete draft, return canonicalRecipeId
- T-044.5: Promotion requires review-for-canonical to have been called first (409 otherwise)

**Acceptance:** Draft CRUD works. Promotion assessment checks required fields. Promotion creates canonical + deletes draft. Response matches API contracts doc section 3.

---

## Frontend tasks (parallel with backend)

### T-045: Design pipeline — research + visual system
**Description:** Execute design pipeline Phases 1–3 from Design Strategy doc.
**Dependencies:** T-006 (Tailwind configured)
**Subtasks:**
- T-045.1: Browse Mobbin for 2–3 hours — save 20–30 references organized by pattern type
- T-045.2: Explore Provecho.co for UX patterns
- T-045.3: Create FigJam flow map covering ingestion, recipe lifecycle, and draft promotion flows
- T-045.4: Design color palette in Figma — primary (warm/food-adjacent), neutrals, semantics, provenance indicators
- T-045.5: Design typography scale in Figma — pick typeface (Inter/Geist), define heading/body/caption sizes
- T-045.6: Design core components in Figma — recipe card (3 variants), ingredient row, tag chip, status badge, button variants, input variants, journal entry card
- T-045.7: Design recipe detail hero screen at full fidelity in Figma
- T-045.8: Export design tokens → update `/packages/ui/tokens` and `tailwind.config.ts`

**Acceptance:** Mobbin references saved. Figma has complete visual system + hero screen. Design tokens in Tailwind config.

---

### T-046: v0 screen generation — Phase 1 core screens
**Description:** Generate React + Tailwind code for all Phase 1 screens using v0.
**Dependencies:** T-045
**Subtasks:**
- T-046.1: Generate recipe card component (full, compact, selectable variants)
- T-046.2: Generate recipe detail page
- T-046.3: Generate recipe library page with filter bar
- T-046.4: Generate ingestion entry page (URL/image/text tabs)
- T-046.5: Generate ingestion progress page (SSE status visualization)
- T-046.6: Generate candidate review page (two-column: editor + context)
- T-046.7: Generate recipe edit page (ingredient/step editors)
- T-046.8: Generate draft detail page (with promotion banner)
- T-046.9: Generate draft promotion review page
- T-046.10: Generate journal composer + entry card components
- T-046.11: Design all empty states (empty library, empty journal, no search results)
- T-046.12: Design all loading skeletons (library cards, recipe detail, journal entries)

**Acceptance:** All Phase 1 screens generated with consistent visual language. Empty states and loading skeletons designed. Code uses Tailwind + shadcn/ui.

---

### T-047: Frontend wiring — ingestion flow
**Description:** Connect ingestion screens to real backend APIs.
**Dependencies:** T-046, T-014, T-013, T-026
**Subtasks:**
- T-047.1: Wire ingestion entry page: form submission → `POST /api/ingestion` via api-client → navigate to progress page
- T-047.2: Wire ingestion progress page: SSE subscription via api-client → update status display in real time → navigate to review on job.review_ready
- T-047.3: Wire candidate review page: fetch candidate → populate form (React Hook Form) → handle review findings display → submit decision → navigate to recipe/draft detail
- T-047.4: Handle all error states: submission failure, SSE disconnect + reconnect, review save failure
- T-047.5: Image upload flow on ingestion entry: presigned URL → direct S3 upload → submit with assetRef

**Acceptance:** Full ingestion flow works end-to-end in the browser: paste URL → watch progress → review candidate → save recipe.

---

### T-048: Frontend wiring — recipe management
**Description:** Connect recipe library, detail, edit, and journal screens to backend APIs.
**Dependencies:** T-046, T-037, T-038, T-039, T-041, T-042
**Subtasks:**
- T-048.1: Wire recipe library: fetch list → render cards → filter/search → pagination
- T-048.2: Wire recipe detail: fetch recipe → render content + media + tags + provenance → journal feed
- T-048.3: Wire recipe edit: populate form → save → revision feedback
- T-048.4: Wire journal composer: create entry → optimistic append → tag selection → image upload
- T-048.5: Wire journal delete: confirm → delete → optimistic remove
- T-048.6: Wire revision history drawer: fetch revisions → restore with confirmation
- T-048.7: Wire media management: upload → register → hero swap

**Acceptance:** All recipe management screens work with real data. Journal entries create and delete. Revisions viewable and restorable.

---

### T-049: Frontend wiring — drafts
**Description:** Connect draft detail and promotion screens.
**Dependencies:** T-046, T-044
**Subtasks:**
- T-049.1: Wire draft detail: fetch → edit form → save
- T-049.2: Wire promotion: review-for-canonical → assessment display → confirm promote → navigate to new recipe
- T-049.3: Draft badge display in recipe library

**Acceptance:** Draft edit and promotion flow works end-to-end.

---

## Cross-cutting

### T-050: Error handling + observability
**Description:** Structured logging, error tracking, and user-facing error states.
**Dependencies:** T-007
**Subtasks:**
- T-050.1: Configure structlog throughout backend — tool calls, agent decisions, state transitions log with job_id, tool_name, duration, outcome
- T-050.2: Create consistent error response middleware (error code + message + details shape)
- T-050.3: Implement user-friendly error messages for all known error types (see PRD failure handling section)
- T-050.4: Add Sentry integration (backend + frontend) — deferred until first deploy but task tracked

**Acceptance:** All API errors return consistent shape. Backend logs are structured JSON. Error messages are specific and actionable.

---

### T-051: Deployment
**Description:** Deploy to Vercel (frontend) + Railway (backend).
**Dependencies:** T-008, T-047, T-048
**Subtasks:**
- T-051.1: Create Railway project with: FastAPI service (from Dockerfile), managed Postgres, managed Redis (and Qdrant in Phase 2). **Optional second service:** dedicated worker if **Dramatiq** (or similar) is reintroduced — same image, different CMD.
- T-051.2: Configure Railway env vars: DB URL, Redis URL, Clerk keys, S3 credentials, Anthropic API key, Google Cloud Vision key, OpenAI key (Whisper), YouTube Data API key
- T-051.3: Run `alembic upgrade head` as part of Railway deploy command
- T-051.4: Run ingredient seed as one-time command
- T-051.5: Create Vercel project linked to `/apps/web` — configure env vars (Clerk publishable key, API base URL pointing to Railway)
- T-051.6: Verify end-to-end: sign in on Vercel → ingest recipe → SSE progress → review → save → view in library
- T-051.7: Configure custom domains if desired

**Acceptance:** App is live. Auth works. Ingestion pipeline runs. Recipe saves and displays. SSE streams across Vercel→Railway boundary.

---

## Task summary

| Priority | Tasks | Description |
|---|---|---|
| P0 | T-001 to T-014 | Scaffolding: repo, packages, backend, Docker, DB, auth, SSE, APIs |
| P1 | T-015 to T-017 | Agent backbone: loop, artifacts, circuit breakers |
| P2 | T-018 to T-027 | Webpage extraction: 8 tools, candidate persistence, e2e test |
| P3 | T-028 to T-031 | Review agent (8 tools), ingredient DB, save flow, tags |
| P4 | T-032 to T-033 | Text + image ingestion tools |
| P5 | T-034 to T-036 | YouTube + social + video processing tools |
| P6 | T-037 to T-043 | Recipe library, detail, edit, media, journal, journalSummary |
| P7 | T-044 | Draft promotion flow |
| Frontend | T-045 to T-049 | Design pipeline, v0 screens, frontend wiring |
| Cross-cutting | T-050 to T-051 | Error handling, observability, deployment |

**Total: 51 tasks, ~200 subtasks**
