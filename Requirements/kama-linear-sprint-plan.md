# Kama — Linear Project Setup: Complete Sprint Plan

**Total tasks:** 100  
**Total sprints:** 12  
**Phase 1:** Sprints 1–6 · 61 tasks (T-001–T-099)  
**Phase 2:** Sprints 7–12 · 39 tasks (T-059–T-097, T-100)

### Background jobs — implementation (May 2026)

**As-built:** **`background_runner.enqueue`** (in-process **`asyncio`**) instead of **Dramatiq**; **Redis** still used for **SSE pub/sub**. **Why / revisit:** see **Phase 1 ACR §1.0** and **`kama-sprint1-plan.md`** header note. Linear issues for **T-011**, **T-014**, etc. should reference that section when grooming.

---

## Linear setup guide

### Suggested labels
| Label | Use |
|---|---|
| `phase-1` | All Phase 1 tasks |
| `phase-2` | All Phase 2 tasks |
| `backend` | FastAPI, workers, agents, tools, DB |
| `frontend` | Next.js screens, wiring, components |
| `infrastructure` | Docker, CI/CD, deployment, monitoring |
| `design` | Design pipeline, v0 generation |
| `p0-scaffold` | Sprint 1 foundation |
| `p1-agent` | Sprint 2 agent + extraction |
| `p2-review` | Sprint 3 review + save |
| `p3-ingestion` | Sprint 4 text + image |
| `p4-social` | Sprint 5 social + APIs |
| `p5-deploy` | Sprint 6 deploy |
| `p6-embedding` | Sprint 7 embedding pipeline |
| `p7-search` | Sprint 8 search |
| `p8-ask` | Sprint 9 ask |
| `p9-artifacts` | Sprint 10 artifacts |
| `p10-pantry` | Sprint 11 pantry + meal plan |
| `p11-deploy2` | Sprint 12 Phase 2 deploy |

### Dependency notation
Each task lists its dependencies by ID. Create issues in dependency order or use Linear's dependency feature to link blocking issues.

---

## Sprint summary

| Sprint | Name | Goal | Tasks | Phase |
|---|---|---|---|---|
| 1 | Foundation | Stack running locally, auth + DB live | T-001–T-014, T-055 | 1 |
| 2 | Agent + Webpage extraction | Submit URL → candidate ready for review | T-015–T-027, T-045, T-046, T-056, T-098 | 1 |
| 3 | Review agent + Save flow | Candidate → canonical recipe or draft | T-028–T-031, T-047, T-052, T-054, T-099 | 1 |
| 4 | Text + Image ingestion | All three source types supported | T-032–T-033, T-048, T-053, T-057 | 1 |
| 5 | Social + YouTube + Recipe APIs | All ingestion types + full recipe CRUD live | T-034–T-044, T-049 | 1 |
| 6 | Phase 1 polish + deploy | Phase 1 live on Vercel + Railway | T-050–T-051, T-058 | 1 |
| 7 | Embedding + Indexing | All recipes indexed in Qdrant | T-059–T-066 | 2 |
| 8 | Search | Hybrid search live end to end | T-067–T-071 | 2 |
| 9 | Ask | Grounded Q&A with session follow-ups | T-072–T-078, T-100 | 2 |
| 10 | Artifacts + Shopping list | Shopping lists generated, saved, editable | T-079–T-083 | 2 |
| 11 | Pantry + Meal plan + Create hub | Full Phase 2 feature set complete | T-084–T-093 | 2 |
| 12 | Phase 2 polish + deploy | Phase 2 live on production | T-094–T-097 | 2 |

---

---

# SPRINT 1 — Foundation

**Goal:** Entire stack running locally. Auth works. DB schema live. **Background ingestion scheduled in-process** (`background_runner`; Redis for SSE). Core APIs exist as stubs.  
**Labels:** `phase-1` `p0-scaffold`

---

### T-001 · Initialize monorepo
**Labels:** `infrastructure`  
**Dependencies:** None

Set up Turborepo + pnpm workspaces with all package and app directories.

**Subtasks:**
- T-001.1: Init git repo with `.gitignore` (node_modules, .env, __pycache__, .venv, dist)
- T-001.2: Init pnpm workspace — `pnpm-workspace.yaml` referencing `apps/*` and `packages/*`
- T-001.3: Create `turbo.json` with task pipeline: build (depends on ^build), dev, typecheck, lint
- T-001.4: Create root `package.json` with workspace scripts (`dev`, `build`, `typecheck`, `lint`, `dev:all`)
- T-001.5: Verify `pnpm install` runs clean from root

**Acceptance:** `pnpm install` succeeds. `turbo build` runs. Workspace structure matches ACR section 3.

---

### T-002 · Set up /packages/contracts
**Labels:** `infrastructure`  
**Dependencies:** T-001

Shared TypeScript domain types, DTOs, and enums used by web and api-client.

**Subtasks:**
- T-002.1: Init package with `package.json`, `tsconfig.json`
- T-002.2: Create `/src/domain/` — SourceAsset, IngestionJob, RecipeCandidate, DraftRecipe, CanonicalRecipe, RecipeRevision, RecipeMedia, Ingredient, CookJournalEntry, JournalEntryMedia, Tag types
- T-002.3: Create `/src/enums/` — JobStatus, InternalState, InternalErrorState, ErrorType, ArtifactType, ReviewMode, SourceType, MediaRole, TagDomain
- T-002.4: Create `/src/api/` — request/response DTOs matching all Phase 1 API endpoints
- T-002.5: Create `/src/schemas/` — Zod schemas for runtime validation
- T-002.6: Export barrel file (`/src/index.ts`)
- T-002.7: Verify package builds with `turbo build`

**Acceptance:** All Phase 1 domain types defined. All API DTOs match API contracts doc. Package builds and exports cleanly.

---

### T-003 · Set up /packages/api-client
**Labels:** `infrastructure`  
**Dependencies:** T-002

Typed FastAPI client wrappers and SSE subscription helpers.

**Subtasks:**
- T-003.1: Init package with `package.json`, `tsconfig.json`
- T-003.2: Create base client with configurable base URL + auth token attachment
- T-003.3: Create `/src/ingestion.ts` — `submitSource()`, `getJobStatus()`, `rerunJob()`
- T-003.4: Create `/src/sse.ts` — SSE subscription helper with reconnection logic (fallback to snapshot GET on disconnect)
- T-003.5: Create `/src/recipeCandidates.ts` — `getCandidate()`, `submitDecision()`
- T-003.6: Create `/src/recipes.ts` — `listRecipes()`, `getRecipe()`, `updateRecipe()`, `deleteRecipe()`, `listRevisions()`, `restoreRevision()`
- T-003.7: Create `/src/drafts.ts` — `getDraft()`, `updateDraft()`, `deleteDraft()`, `reviewForCanonical()`, `promote()`
- T-003.8: Create `/src/journal.ts` — `listEntries()`, `createEntry()`, `deleteEntry()`
- T-003.9: Create `/src/tags.ts` — `listTags()`, `createOrReuseTag()`
- T-003.10: Create `/src/ingredients.ts` — `searchIngredients()`, `createIngredient()`, `updateIngredientAliases()`
- T-003.11: Create `/src/media.ts` — `getPresignedUrl()`, `registerMedia()`, `updateMedia()`, `deleteMedia()`
- T-003.12: Export barrel file

**Acceptance:** Every Phase 1 API endpoint has a typed client function. SSE helper handles connection, reconnection, and event parsing.

---

### T-004 · Set up /packages/shared
**Labels:** `infrastructure`  
**Dependencies:** T-002

Non-visual shared utilities, constants, and helpers.

**Subtasks:**
- T-004.1: Init package with `package.json`, `tsconfig.json`
- T-004.2: Create `/src/constants/` — job status display label mapping, review mode labels, error type labels
- T-004.3: Create `/src/utils/` — date formatting, time display helpers (e.g. "20 min"), ingredient text formatting
- T-004.4: Create `/src/query/` — TanStack Query key factories (`recipeKeys`, `jobKeys`, `tagKeys`, `ingredientKeys`, `journalKeys`, `artifactKeys`, `pantryKeys`, `askKeys`)
- T-004.5: Export barrel file

**Acceptance:** Status-to-display mappings match API contracts SSE section. Query key factories cover all API data types including Phase 2.

---

### T-005 · Set up /packages/ui
**Labels:** `infrastructure` `design`  
**Dependencies:** T-001

Shared design system — tokens, primitives, and cross-platform components.

**Subtasks:**
- T-005.1: Init package with `package.json`, `tsconfig.json`
- T-005.2: Create `/src/tokens/` — color palette, typography scale, spacing scale, border radii, shadow definitions (platform-agnostic format)
- T-005.3: Create `/src/primitives/` — Button (loading, disabled states), Input, Textarea, Badge, Chip/Tag
- T-005.4: Create `/src/components/` — placeholder structure for RecipeCard, IngredientRow, StepRow, JournalEntryCard
- T-005.5: Set up component pattern: `Button/index.ts`, `Button.tsx`, `Button.native.tsx` (native placeholder), `types.ts`

**Acceptance:** Token definitions importable. Button and Input are functional web components. Package builds.

---

### T-006 · Set up Next.js web app
**Labels:** `frontend` `infrastructure`  
**Dependencies:** T-002, T-004, T-005

Configure `/apps/web` with Tailwind, Clerk auth, TanStack Query, and basic routing.

**Subtasks:**
- T-006.1: Create Next.js app with App Router
- T-006.2: Configure Tailwind with design tokens from `/packages/ui/tokens` mapped into `tailwind.config.ts`
- T-006.3: Install and configure Clerk — `<ClerkProvider>`, sign-in/sign-up pages, protect routes with middleware
- T-006.4: Install and configure TanStack Query — `QueryClientProvider` in root layout
- T-006.5: Create app layout shell — sidebar/top nav with Recipes, Ingest links and placeholder pages
- T-006.6: Create route stubs for all Phase 1 routes: `/recipes`, `/recipes/[id]`, `/recipes/[id]/edit`, `/drafts/[id]`, `/drafts/[id]/promote`, `/ingest`, `/ingest/[jobId]`, `/ingest/[jobId]/review`
- T-006.7: Verify Clerk auth flow — sign in → see protected page → sign out
- T-006.8: Verify TanStack Query — create a test query against FastAPI health check

**Acceptance:** App runs at localhost. Auth works. All Phase 1 routes exist as placeholder pages. TanStack Query can fetch from backend.

---

### T-007 · Set up FastAPI backend
**Labels:** `backend` `infrastructure`  
**Dependencies:** T-001

Configure `/backend` with project structure, database, auth middleware, and core infrastructure.

**Subtasks:**
- T-007.1: Create FastAPI entry point (`/app/main.py`) with CORS middleware, health check endpoint
- T-007.2: Create `/app/core/config.py` — Pydantic Settings loading from env vars (DB URL, Redis URL, Clerk JWKS URL, S3 config, API keys)
- T-007.3: Create `/app/core/database.py` — SQLAlchemy async engine, session factory, Base model
- T-007.4: Create `/app/core/auth.py` — Clerk JWT verification dependency using JWKS endpoint. FastAPI `Depends()` extracting and validating user ID from Bearer token
- T-007.5: Create full directory structure: `/api`, `/core`, `/domain`, `/models`, `/schemas`, `/services`, `/agents`, `/tools`, `/workers`, `/repositories`
- T-007.6: Install dependencies: `pydantic-ai`, `tenacity`, `structlog`, `google-cloud-vision`, `yt-dlp`, `openai`, `trafilatura`, `boto3`
- T-007.7: Configure `structlog` for structured JSON logging
- T-007.8: Verify auth middleware — 401 without token, 200 with valid Clerk token

**Acceptance:** FastAPI runs. CORS allows Next.js origin. Auth validates Clerk JWTs. Logging works. All directories exist.

---

### T-008 · Docker Compose + Dockerfile
**Labels:** `infrastructure`  
**Dependencies:** T-007

Local infrastructure containers and backend deployment image.

**Subtasks:**
- T-008.1: Create `docker-compose.yml` — Postgres (pgvector/pgvector:pg16) and Redis (redis:7-alpine) with persistent volumes
- T-008.2: Create `/backend/Dockerfile` — Python 3.12 slim, install ffmpeg, install uv, copy deps, copy code, expose 8000, uvicorn CMD
- T-008.3: Add `.env.example` with all required env vars documented
- T-008.4: Create `.env` for local dev (gitignored) with Postgres, Redis, Clerk, S3 config
- T-008.5: Verify `docker compose up -d` starts Postgres and Redis
- T-008.6: Verify FastAPI connects to Dockerized Postgres and Redis
- T-008.7: Verify `docker build` succeeds for backend image
- T-008.8: Add root-level `dev:apps` / `dev:all` using `concurrently`: Docker infra + Next.js + FastAPI **(no separate Dramatiq process — see doc header § Background jobs)**

**Acceptance:** `docker compose up -d && pnpm dev:all` starts entire stack. All services connect. Backend Docker image builds.

---

### T-009 · Database migrations — core tables
**Labels:** `backend`  
**Dependencies:** T-007, T-008

Alembic setup and initial migration for all Phase 1 tables.

**Subtasks:**
- T-009.1: Init Alembic — `alembic init alembic`, configure `alembic.ini` to read DB URL from env
- T-009.2: Create SQLAlchemy models: `SourceAsset`, `IngestionJob`, `NormalizedSourceArtifact`, `RecipeCandidate`
- T-009.3: Create SQLAlchemy models: `CanonicalRecipe`, `DraftRecipe`, `RecipeRevision`, `RecipeMedia`
- T-009.4: Create SQLAlchemy models: `Ingredient`, `Tag`, `CookJournalEntry`, `JournalEntryMedia`
- T-009.5: IngestionJob JSONB columns: `extractionPlan`, `stateHistory`, `metadata`; `lastHeartbeatAt` timestamp
- T-009.6: RecipeCandidate JSONB columns: `ingredients`, `steps`, `fieldConfidenceMap`, `fieldProvenanceMap`, `reviewFindings`
- T-009.7: CanonicalRecipe JSONB columns: `ingredients`, `steps`, `fieldProvenanceMap`; nullable `journalSummary` text column
- T-009.8: Tag model with `domain` enum column (recipe / journal)
- T-009.9: **Ingredient model: add `category` column** — `VARCHAR(32)`, indexed, default `"other"`. Uses `IngredientCategory` enum with 12 values:
  - `produce` — fruits, vegetables, fresh herbs
  - `meat_seafood` — chicken, beef, shrimp, etc.
  - `dairy` — milk, cheese, yogurt, butter, cream
  - `grains_bread` — rice, pasta, flour, bread, oats
  - `spices_seasoning` — cumin, salt, pepper, paprika, dried herbs
  - `oils_vinegars` — olive oil, sesame oil, balsamic, soy sauce
  - `canned_jarred` — canned tomatoes, beans, coconut milk, broth
  - `frozen` — frozen peas, frozen berries
  - `baking` — sugar, baking powder, vanilla extract, chocolate
  - `nuts_seeds` — almonds, sesame seeds, peanut butter
  - `beverages` — wine (cooking), stock, juice
  - `other` — anything that doesn't fit
  Used by shopping list generation (T-081) and pantry UI (T-087) to group items by aisle/section without an LLM call.
- T-009.10: Generate initial Alembic migration: `alembic revision --autogenerate -m "initial schema"`; separate migration for `add_ingredient_category`
- T-009.11: Run migration: `alembic upgrade head` — verify all tables created
- T-009.12: Create indexes: IngestionJob.status, IngestionJob.sourceAssetId, CanonicalRecipe.userId, Tag.domain, CookJournalEntry.canonicalRecipeId, **Ingredient.category**

**Acceptance:** `alembic upgrade head` creates all 12 tables. Schema matches ACR domain model. JSONB columns and indexes created. Ingredient table has `category` column with index.

---

### T-010 · S3 presigned URL endpoint
**Labels:** `backend`  
**Dependencies:** T-007

Backend endpoint for generating presigned upload URLs for direct client-to-S3 uploads.

**Subtasks:**
- T-010.1: Create S3 client config in `/app/core/s3.py`
- T-010.2: Create `POST /api/media/presigned-url` — accepts `fileName`, `contentType`, `context` (`recipe_media | journal_media | source_upload`) → returns `uploadUrl`, `assetRef`, `expiresAt`
- T-010.3: S3 key format: `{context}/{userId}/{uuid}_{fileName}`
- T-010.4: Add auth dependency
- T-010.5: Verify: call endpoint → receive presigned URL → upload test file → file appears in S3

**Acceptance:** Endpoint returns valid presigned URL. Direct S3 upload succeeds. AssetRef usable for media registration.

---

### T-011 · Background worker execution (`background_runner` + Redis SSE)
**Labels:** `backend` `infrastructure`  
**Dependencies:** T-007, T-008

Run ingestion outside the HTTP request; SSE for progress. **As-built:** `run_ingestion_send` → `background_runner.enqueue` (in-process `asyncio`). **Redis:** SSE pub/sub. **Revisit:** Dramatiq + Redis broker.

**Subtasks:**
- T-011.1: **Redis** for SSE (not Dramatiq broker in current code); **(revisit)** Dramatiq broker config
- T-011.2: **`/workers/ingestion_worker.py`** — `run_ingestion_send` / `_run_ingestion` + agent
- T-011.3: Full pipeline (replaces stub)
- T-011.4: **`/workers/journal_summary_worker.py`** — `enqueue` pattern
- T-011.5: **`/workers/reaper_worker.py`** — lifespan `asyncio` loop
- T-011.6: Verify POST ingestion → job progresses in DB + SSE
- T-011.7: **(revisit)** `dramatiq app.workers` — **as-built:** uvicorn only

**Acceptance:** Ingestion runs asynchronously. SSE works. Reaper runs.

---

### T-012 · PydanticAI integration
**Labels:** `backend`  
**Dependencies:** T-007

Set up PydanticAI with Claude Sonnet and create base agent scaffolding.

**Subtasks:**
- T-012.1: Create `/agents/base.py` — shared `AgentContext` model (job reference, existing artifacts, completed tools, iteration count)
- T-012.2: Create `/agents/ingestion_agent.py` — PydanticAI agent with Claude Sonnet model, system prompt placeholder, empty tool catalog
- T-012.3: Create `/agents/review_agent.py` — PydanticAI agent definition with system prompt placeholder, empty tool catalog
- T-012.4: Create `/tools/base.py` — `ToolResult` type definition (success, artifacts, candidateUpdate, signals)
- T-012.5: Verify: create agent instance → run with a test prompt → receive structured response

**Acceptance:** PydanticAI agent initializes with Claude Sonnet. Agent can be invoked and returns a response. Both agent definitions and base types exist.

---

### T-013 · SSE endpoint
**Labels:** `backend`  
**Dependencies:** T-007, T-009

Server-Sent Events endpoint for ingestion job progress streaming.

**Subtasks:**
- T-013.1: Create `GET /api/ingestion/jobs/{jobId}/events` SSE endpoint using FastAPI `StreamingResponse` with `text/event-stream` content type
- T-013.2: Create SSE event emitter service — writes events to Redis pub/sub channel keyed by jobId
- T-013.3: SSE endpoint subscribes to the Redis channel and streams events to client
- T-013.4: Define event serialization: `event: {eventType}\ndata: {json payload}\n\n`
- T-013.5: Include CORS headers for SSE endpoint
- T-013.6: Verify: publish test event to Redis channel → SSE client receives it

**Acceptance:** SSE endpoint streams events. Events match API contracts schema (eventType, jobId, sequence, timestamp, status). Redis pub/sub delivers events from worker to API server.

---

### T-014 · Core ingestion API endpoints
**Labels:** `backend`  
**Dependencies:** T-009, T-011, T-013

Submission and job tracking endpoints (without agent logic).

**Subtasks:**
- T-014.1: Create `/repositories/source_asset_repo.py` — create, get_by_id
- T-014.2: Create `/repositories/ingestion_job_repo.py` — create, get_by_id, update_status, update_heartbeat, find_stuck
- T-014.3: Create `/schemas/ingestion.py` — Pydantic request/response models
- T-014.4: Create `POST /api/ingestion` — validate input, create SourceAsset, create IngestionJob (status: queued), **`run_ingestion_send(job_id)`** (background task), return sourceAssetId + jobId + sseUrl
- T-014.5: Create `GET /api/ingestion/jobs/{jobId}` — return full job snapshot including extractionPlan, stateHistory, metadata, lastHeartbeatAt
- T-014.6: Create `POST /api/ingestion/jobs/{jobId}/rerun` — verify rerunAllowed, create new IngestionJob linked to same SourceAsset, **`run_ingestion_send(new_job_id)`**, return new jobId
- T-014.7: Add auth dependency to all endpoints

**Acceptance:** POST creates source + job + schedules background ingestion. GET returns full job state. Rerun creates new job. All endpoints auth-protected. Shapes match API contracts sections 1.1–1.4.

---

### T-055 · Testing infrastructure
**Labels:** `infrastructure`  
**Dependencies:** T-007, T-006

Set up pytest (backend) and Vitest (frontend) with CI-ready test configuration.

**Subtasks:**
- T-055.1: Set up pytest in `/backend` — configure `pytest.ini`, test database URL, async test support (`pytest-asyncio`)
- T-055.2: Create test fixtures: test DB session, FastAPI TestClient, mock Clerk auth header
- T-055.3: Create `/backend/tests/` structure: `unit/`, `integration/`, `conftest.py`
- T-055.4: Set up Vitest in `/apps/web` — configure `vitest.config.ts`, React Testing Library
- T-055.5: Create `/apps/web/tests/` structure and first smoke test
- T-055.6: Write first backend integration test: `POST /api/ingestion` → 201 with jobId
- T-055.7: Verify `pnpm test` runs from root via Turborepo task pipeline

**Acceptance:** `pytest` runs backend tests. `vitest` runs frontend tests. Test DB isolated from dev DB. First integration test passes.

---

---

# SPRINT 2 — Agent backbone + Webpage extraction

**Goal:** Submit a real recipe URL, watch SSE events stream, get a structured candidate ready for review. Gold path works end to end.  
**Labels:** `phase-1` `p1-agent`

---

### T-015 · Ingestion agent — core loop
**Labels:** `backend`  
**Dependencies:** T-011, T-012, T-014

Replace the stub worker with the real PydanticAI ingestion agent loop.

**Subtasks:**
- T-015.1: Full system prompt — role, available tools, decision principles (deterministic by default, LLM when ambiguous), stop conditions
- T-015.2: AgentContext initialization — load job, existing artifacts, completed tools (checkpoint resume on rerun)
- T-015.3: Heartbeat update after each tool call
- T-015.4: SSE event emission within loop: `tool_called`, `tool_succeeded`, `tool_failed`, `agent_reasoning`, `state_changed`, `candidate_created`, `candidate_improved`
- T-015.5: Stop condition checks: canonical-eligible candidate produced, all tools exhausted, max 15 iterations, 5-minute wall-clock timeout
- T-015.6: Extraction plan creation and dynamic modification (entries with methodKey, status, addedBy, agentDecision)
- T-015.7: Job finalization — update status (review_ready / draft_ready / failed / unsupported), emit terminal SSE event
- T-015.8: Wire agent into **`_run_ingestion`** / **`run_ingestion_send`** (**revisit:** Dramatiq actor wrapper)

**Acceptance:** Agent loop runs inside worker. Heartbeat updates on each tool call. SSE events stream to client. Stop conditions enforced. Job reaches terminal state.

---

### T-016 · Normalized artifact persistence
**Labels:** `backend`  
**Dependencies:** T-009

Service and repository for creating and retrieving typed normalized artifacts.

**Subtasks:**
- T-016.1: Create `/repositories/normalized_artifact_repo.py` — create, get_by_id, find_by_job_id
- T-016.2: Create artifact creation helper that accepts typed payloads and persists with correct artifactType
- T-016.3: Verify JSONB payload storage and retrieval for all artifact types defined in ACR section 5
- T-016.4: Link artifact IDs to `IngestionJob.normalizedArtifactIds` on creation

**Acceptance:** Artifacts persist with typed payloads. Retrievable by job ID. normalizedArtifactIds array stays in sync.

---

### T-017 · Circuit breaker infrastructure
**Labels:** `backend`  
**Dependencies:** T-007

Circuit breaker instances for all external services.

**Subtasks:**
- T-017.1: Create `/core/circuit_breaker.py` — `ServiceCircuitBreaker` class with `failure_threshold`, `reset_timeout`, `is_open()`, `record_failure()`, `record_success()`
- T-017.2: Create instances: `ocr_breaker`, `whisper_breaker`, `llm_breaker`, `youtube_breaker`, `social_breaker`
- T-017.3: Create tenacity retry wrapper factory for external service calls (configurable: attempts, min/max backoff, which exceptions to retry)

**Acceptance:** Circuit breakers track failures per service. Open circuit returns immediately. Breakers reset after timeout. Tenacity wrappers configured per service type.

---

### T-018 · classify_source tool
**Labels:** `backend`  
**Dependencies:** T-012, T-015

Determine source subtype from URL domain or input type.

**Subtasks:**
- T-018.1: Create `/tools/source_tools.py`
- T-018.2: URL domain detection: YouTube, Instagram, TikTok, Facebook, generic webpage
- T-018.3: Input type routing: url → URL classifier, image → image classifier, text → text classifier
- T-018.4: Return ToolResult with sourceSubtype and suggested initial tool sequence in signals
- T-018.5: Register as PydanticAI tool

**Acceptance:** Correctly classifies YouTube, Instagram, TikTok, Facebook URLs by domain. Returns appropriate sourceSubtype.

---

### T-019 · httpx_fetch tool
**Labels:** `backend`  
**Dependencies:** T-012, T-017

Fetch URL content via httpx with redirect following and timeout handling.

**Subtasks:**
- T-019.1: Create `/tools/fetch_tools.py`
- T-019.2: Implement `httpx_fetch`: async GET, `follow_redirects=True`, 15s timeout, User-Agent header
- T-019.3: Return HTML content, resolved URL, response status
- T-019.4: Signals: `has_recipe_schema` (quick JSON-LD check), `looks_like_recipe_page`, `looks_like_recipe_index`, `page_title`
- T-019.5: Wrap with tenacity retry (3 attempts, 1–10s backoff)
- T-019.6: Create `url_metadata` artifact from response metadata (title, description, heroImageUrl, domain, platform)
- T-019.7: Create `source_preview` artifact (link_card variant) from page metadata
- T-019.8: Register as PydanticAI tool

**Acceptance:** Fetches pages. Follows redirects. Handles timeouts gracefully. Produces url_metadata and source_preview artifacts. Signals indicate recipe-likeness.

---

### T-020 · check_schema_markup tool
**Labels:** `backend`  
**Dependencies:** T-019

Look for JSON-LD / schema.org recipe data in fetched HTML.

**Subtasks:**
- T-020.1: Add to `/tools/extraction_tools.py`
- T-020.2: Parse HTML for `<script type="application/ld+json">` blocks
- T-020.3: Look for Recipe schema type in JSON-LD
- T-020.4: Return success with parsed recipe data in signals if found; clean failure if not
- T-020.5: Register as PydanticAI tool

**Acceptance:** Detects JSON-LD recipe markup. Returns structured data when found. Clean failure when absent.

---

### T-021 · schema_recipe_extract tool
**Labels:** `backend`  
**Dependencies:** T-020

Parse a complete recipe candidate from JSON-LD / schema.org markup.

**Subtasks:**
- T-021.1: Map schema.org Recipe fields to RecipeCandidate: name→title, recipeIngredient→ingredients, recipeInstructions→steps, prepTime→prepTimeMinutes, cookTime→cookTimeMinutes, recipeYield→servings
- T-021.2: Parse ISO 8601 duration strings (PT30M → 30 minutes)
- T-021.3: Extract recipe images from schema (hero image, step images)
- T-021.4: Set provenance: sourceType `schema_recipe_markup` for all fields
- T-021.5: Return ToolResult with candidateUpdate and confidence signals
- T-021.6: Register as PydanticAI tool

**Acceptance:** Produces near-complete RecipeCandidate from well-formed schema markup. Duration parsing works. Provenance correctly set.

---

### T-022 · extract_recipe_links tool
**Labels:** `backend`  
**Dependencies:** T-012

Scan text content for URLs that might be recipe pages.

**Subtasks:**
- T-022.1: Add to `/tools/source_tools.py`
- T-022.2: URL extraction from text via regex
- T-022.3: Filter for likely recipe URLs (exclude social media, CDNs, tracking links)
- T-022.4: Create `linked_recipe_urls` artifact with url, source (description/comment/page_body), confidence
- T-022.5: Register as PydanticAI tool

**Acceptance:** Finds URLs in text content. Filters non-recipe links. Produces linked_recipe_urls artifact.

---

### T-023 · assess_parseability tool
**Labels:** `backend`  
**Dependencies:** T-012, T-016

Evaluate recipe-likeness and completeness of gathered content.

**Subtasks:**
- T-023.1: Add to `/tools/evaluation_tools.py`
- T-023.2: Check for title, ingredient, and step signals in available artifacts
- T-023.3: Determine reviewMode (quick / standard / reconstruction) based on source quality
- T-023.4: Determine draftEligible and canonicalEligible flags
- T-023.5: Create `parseability_assessment` artifact with sourceSubtypeDetected, recipeLikelihood, reviewMode, eligibility flags, blockingIssues
- T-023.6: Register as PydanticAI tool

**Acceptance:** Produces parseability_assessment with correct review mode and eligibility flags.

---

### T-024 · llm_structured_extract tool
**Labels:** `backend`  
**Dependencies:** T-012

LLM extracts title, ingredients, steps from cleaned text using Claude Sonnet.

**Subtasks:**
- T-024.1: Add to `/tools/extraction_tools.py`
- T-024.2: Create extraction prompt template — input is cleaned text, output is structured recipe JSON matching RecipeCandidate fields
- T-024.3: Use PydanticAI structured output with RecipeCandidate Pydantic model for validation
- T-024.4: Map extracted ingredient rows to RecipeIngredientRow (text, quantity, unit)
- T-024.5: Map extracted steps to RecipeStepRow (order, text)
- T-024.6: Set provenance per field based on source artifact
- T-024.7: Wrap with tenacity retry (2 attempts) and llm_breaker circuit breaker
- T-024.8: Return ToolResult with candidateUpdate and confidence signals
- T-024.9: Register as PydanticAI tool

**Acceptance:** Extracts structured recipe from cleaned text. Output validates against RecipeCandidate model. Provenance set. Retries on malformed output.

---

### T-025 · evaluate_candidate tool
**Labels:** `backend`  
**Dependencies:** T-012

Check candidate completeness, structural sanity, and canonical eligibility.

**Subtasks:**
- T-025.1: Add to `/tools/evaluation_tools.py`
- T-025.2: Check: non-empty title, ≥1 ingredient, ≥1 step
- T-025.3: Check structural sanity: ingredient rows have usable text, steps have content
- T-025.4: Determine canonicalEligible and draftEligible
- T-025.5: Generate reviewFindings (code, severity, field, message)
- T-025.6: Return ToolResult with eligibility and findings in signals
- T-025.7: Register as PydanticAI tool

**Acceptance:** Correctly identifies canonical vs draft-only candidates. Generates meaningful review findings.

---

### T-026 · RecipeCandidate persistence
**Labels:** `backend`  
**Dependencies:** T-009, T-016

Service and repository for creating and retrieving recipe candidates.

**Subtasks:**
- T-026.1: Create `/repositories/recipe_candidate_repo.py` — create, get_by_id
- T-026.2: Create `/services/ingestion_service.py` — orchestrates candidate creation from agent results, persists with all fields, provenance, confidence, findings
- T-026.3: Link candidateId to IngestionJob on creation
- T-026.4: Create `GET /api/recipe-candidates/{candidateId}` endpoint — full candidate with sourceContext, allowedActions, reviewAgentSummary

**Acceptance:** Candidates persist with full JSONB fields. GET returns complete review payload matching API contracts section 2.1.

---

### T-027 · End-to-end webpage ingestion test
**Labels:** `backend`  
**Dependencies:** T-015–T-026, T-098

Verify the full flow: submit URL → agent processes → candidate ready for review.

**Subtasks:**
- T-027.1: Submit a real recipe webpage URL via `POST /api/ingestion`
- T-027.2: Verify SSE event sequence: started → classify → httpx_fetch → check_schema → extract_page_text (if needed) → llm_structured_extract → evaluate → review_ready
- T-027.3: Verify `GET /api/recipe-candidates/{id}` returns complete candidate with provenance
- T-027.4: Verify extraction plan entries show correct tool sequence and statuses
- T-027.5: Test three cases: recipe page with JSON-LD schema; recipe page without schema (LLM fallback via extract_page_text); non-recipe URL (reaches unsupported)

**Acceptance:** All three test cases pass. SSE events match expected sequence. Non-recipe URL handled gracefully.

---

### T-045 · Design pipeline — research + visual system
**Labels:** `design` `frontend`  
**Dependencies:** T-006

Execute design pipeline phases 1–3: research, visual language, and design tokens.

**Subtasks:**
- T-045.1: Browse Mobbin for 2–3 hours — save 20–30 references organized by pattern type (library, ingestion, review, journal)
- T-045.2: Explore Provecho.co for UX patterns
- T-045.3: Create FigJam flow map covering ingestion, recipe lifecycle, and draft promotion flows
- T-045.4: Design color palette in Figma — primary (warm/food-adjacent), neutrals, semantics, provenance indicators
- T-045.5: Design typography scale in Figma — pick typeface (Inter/Geist), define heading/body/caption sizes
- T-045.6: Design core components in Figma — recipe card (3 variants), ingredient row, tag chip, status badge, button variants, input variants, journal entry card
- T-045.7: Design recipe detail hero screen at full fidelity
- T-045.8: Export design tokens → update `/packages/ui/tokens` and `tailwind.config.ts`

**Acceptance:** Mobbin references saved. Figma has complete visual system + hero screen. Design tokens in Tailwind config.

---

### T-046 · v0 screen generation — Phase 1 core screens
**Labels:** `design` `frontend`  
**Dependencies:** T-045

Generate React + Tailwind code for all Phase 1 screens using v0.

**Subtasks:**
- T-046.1: Generate recipe card component (full, compact, selectable variants)
- T-046.2: Generate recipe detail page (hero, ingredients, steps, gallery, provenance panel, journal section)
- T-046.3: Generate recipe library page with filter bar
- T-046.4: Generate ingestion entry page (URL/image/text tabs, context note)
- T-046.5: Generate ingestion progress page (source preview, animated status steps, collapsible agent timeline feed, all error/unsupported states)
- T-046.6: Generate candidate review page (two-column: recipe editor + source context + review findings)
- T-046.7: Generate recipe edit page (ingredient rows with mapping selector, step rows, tag selector)
- T-046.8: Generate draft detail page (draft status banner, promotion CTA, field completeness indicators)
- T-046.9: Generate draft promotion review page (assessment results, confirm/back actions)
- T-046.10: Generate journal composer + entry card components
- T-046.11: Design all empty states (empty library, empty journal, no search results, no drafts)
- T-046.12: Design all loading skeletons (library cards, recipe detail, journal entries, candidate review)

**Acceptance:** All Phase 1 screens generated with consistent visual language. Empty states and skeletons designed. Code uses Tailwind + shadcn/ui.

---

### T-056 · CI/CD — GitHub Actions
**Labels:** `infrastructure`  
**Dependencies:** T-007, T-055

Automated test and lint pipeline on every PR.

**Subtasks:**
- T-056.1: Create `.github/workflows/ci.yml` — runs on push to main and all PRs
- T-056.2: Backend CI job: checkout, install uv, install deps, run pytest
- T-056.3: Frontend CI job: checkout, install pnpm, install deps, run Vitest, run typecheck, run lint
- T-056.4: Fail PR if any CI job fails
- T-056.5: Add status badges to README

**Acceptance:** CI runs on every PR. Backend and frontend tests both pass. Failing tests block merge.

---

### T-098 · extract_page_text tool
**Labels:** `backend`  
**Dependencies:** T-019

Extract readable text content from raw HTML. Produces the `cleaned_page_text` artifact that enables non-schema webpage extraction.

**Subtasks:**
- T-098.1: Add `trafilatura` to backend dependencies (already added to T-007 dep list)
- T-098.2: Implement `extract_page_text` tool in `/tools/fetch_tools.py`
- T-098.3: Take HTML string from the url_metadata/httpx_fetch result → use trafilatura main content extraction to strip navigation, headers, footers, ads, sidebars, scripts
- T-098.4: Detect and label content sections — scan extracted text for section markers (ingredient-like lines, numbered steps, title candidates) → produce `contentSections` array with sectionType labels (title / ingredients / instructions / notes / unknown)
- T-098.5: Create `cleaned_page_text` artifact: sourceUrl, title, text, extractionMethod (`main_content_cleaning` or `readability_extraction`), contentSections, textLength
- T-098.6: Quality signal: if extracted text < 200 chars or looks like an index page (many links, no structured sections) → return low-quality signal to agent
- T-098.7: Register as PydanticAI tool
- T-098.8: Wire into agent flow: after httpx_fetch → check_schema_markup → if no schema → extract_page_text → llm_structured_extract with cleaned text
- T-098.9: Test with: recipe page with schema (schema path, skip this tool); recipe page without schema (extract_page_text + llm); index/category page (quality signal → agent tries another path)

**Acceptance:** Produces `cleaned_page_text` artifact for any recipe webpage. contentSections identifies ingredient/step blocks. Quality signal fires on low-content pages. Non-schema recipe pages extract end-to-end.

---

---

# SPRINT 3 — Review agent + Save flow

**Goal:** A candidate can be reviewed by a human and saved as a canonical recipe or draft. Ingredient DB is live. Tags work. Media is materialized. Recipes can be deleted.  
**Labels:** `phase-1` `p2-review`

---

### T-028 · Review agent implementation
**Labels:** `backend`  
**Dependencies:** T-012, T-026

PydanticAI review agent with full tool catalog. Runs automatically on every candidate before human review.

**Subtasks:**
- T-028.1: Review agent system prompt — role, available tools, principles (fill gaps from evidence, don't invent, mark provenance as `review_agent_enriched`)
- T-028.2: Implement `lookup_ingredient` tool — search ingredient DB, fix unmapped/mismapped ingredient rows
- T-028.3: Implement `re_read_source_artifact` tool — LLM reads a specific artifact looking for missing metadata (cook time, prep time, servings)
- T-028.4: Implement `normalize_ingredient_row` tool — fix formatting, standardize unit abbreviations
- T-028.5: Implement `verify_step_coherence` tool — check steps reference existing ingredients, logical order
- T-028.6: Implement `estimate_missing_metadata` tool — find prep/cook time in source artifacts
- T-028.7: Implement `update_candidate_field` tool — modify field with review_agent_enriched provenance
- T-028.8: Implement `add_review_finding` and `resolve_review_finding` tools
- T-028.9: Wire review agent into ingestion pipeline — runs after candidate creation, before job status transitions to review_ready
- T-028.10: Safety limits: max 10 tool calls, 30-second wall-clock timeout (pass whatever exists to human review on timeout)
- T-028.11: Emit SSE events: `review_agent_started`, `review_agent_tool_called`, `review_agent_completed`
- T-028.12: Populate `reviewAgentSummary` on candidate (fieldsEnriched, ingredientsMapped, findingsResolved, findingsAdded, totalToolCalls, durationMs)

**Acceptance:** Review agent runs on every candidate. Fills gaps from source artifacts. Provenance marked as review_agent_enriched. SSE events stream. Safety limits enforced.

---

### T-029 · Ingredient DB setup and seeding
**Labels:** `backend`  
**Dependencies:** T-009

Ingredient model, repository, API endpoints, fuzzy search, and initial seed data. **Each ingredient has a `category` field** (see T-009.9 for valid values) that is used downstream by shopping list generation (T-081) and pantry UI grouping (T-087).

**Subtasks:**
- T-029.1: Create `/repositories/ingredient_repo.py` — create (with `category`), search (name + aliases), get_by_id, update_aliases
- T-029.2: Enable `pg_trgm` extension in a new Alembic migration; add trigram GIN index on `Ingredient.name`
- T-029.3: Implement three-tier search: (1) exact match on canonical name, (2) alias ILIKE match, (3) trigram similarity fallback — return matches with confidence level
- T-029.4: Create `GET /api/ingredients?search=...` endpoint — returns items with id, name, **category**, aliases, matchConfidence
- T-029.5: Create `POST /api/ingredients` endpoint — **`category` is required** (validated against 12-value `IngredientCategory` enum, 422 if invalid); 409 if canonical name already exists
- T-029.6: Create `PATCH /api/ingredients/{ingredientId}` endpoint — append new aliases (deduplicate)
- T-029.7: Create seed script — load **393 common ingredients** from curated list, **each with a `category` assigned** from the 12-value enum (produce: 96, meat_seafood: 50, dairy: 28, grains_bread: 56, spices_seasoning: 37, oils_vinegars: 37, canned_jarred: 27, frozen: 11, baking: 25, nuts_seeds: 19, beverages: 7)
- T-029.8: Run seed on first deployment / dev setup via management command (`uv run python -m app.seeds.seed_data`)
- T-029.9: Verify all three matching tiers work: exact ("garlic"), alias ("garlic cloves"), fuzzy ("garlic pdr" → "garlic powder")
- T-029.10: Verify `category` is returned in all search and create responses

**Acceptance:** DB seeded with 393 entries across 12 categories (matching `IngredientCategory` enum). Three-tier search works. `category` included in all responses. `POST` requires valid `category`. PATCH appends aliases. Responses match API contracts section 8.

---

### T-030 · Candidate review decision API
**Labels:** `backend`  
**Dependencies:** T-026, T-029

Endpoint to save candidate as canonical, draft, or discard.

**Subtasks:**
- T-030.1: Create candidate decision request/response Pydantic schemas
- T-030.2: Create `/repositories/canonical_recipe_repo.py` — create with full fields, provenance, promotion metadata
- T-030.3: Create `/repositories/draft_recipe_repo.py` — create with origin linkage
- T-030.4: Create `POST /api/recipe-candidates/{candidateId}/decision` endpoint
- T-030.5: Handle `save_canonical` — validate eligibility, create CanonicalRecipe with provenance (drop confidence), call media materialization service (T-099), return canonicalRecipeId
- T-030.6: Handle `save_draft` — create DraftRecipe from edited fields, return draftRecipeId
- T-030.7: Handle `discard` — mark candidate as discarded
- T-030.8: Prevent duplicate decisions (409 if already decided)

**Acceptance:** All three actions work. Canonical save validates eligibility. Media materialized on canonical save. Response shapes match API contracts section 2.2.

---

### T-031 · Tag system
**Labels:** `backend`  
**Dependencies:** T-009

Tag model, repository, API endpoints, and seed data for recipe and journal domains.

**Subtasks:**
- T-031.1: Create `/repositories/tag_repo.py` — list_by_domain, find_by_name_and_domain, create
- T-031.2: Create `GET /api/tags?domain=recipe|journal` endpoint (optional `search` substring filter)
- T-031.3: Create `POST /api/tags` endpoint — create or reuse (same name+domain → return existing)
- T-031.4: Seed recipe tags: "under 30 mins", "vegetarian", "vegan", "kids favorite", "one pot", "high protein", "comfort food", "quick", "meal prep", "weeknight", "weekend project", "dairy-free", "gluten-free"
- T-031.5: Seed journal tags: "tweak", "success", "issue", "would make again", "timing note", "ingredient swap", "family liked it", "too spicy", "took longer", "easier than expected"

**Acceptance:** Tags stored with domain. List filters by domain. Create-or-reuse logic works. Seed tags loaded. Responses match API contracts section 7.

---

### T-052 · Recipe delete endpoint
**Labels:** `backend` `frontend`  
**Dependencies:** T-030

`DELETE /api/recipes/{recipeId}` with full cascade.

**Subtasks:**
- T-052.1: Create `DELETE /api/recipes/{recipeId}` endpoint
- T-052.2: Cascade delete: RecipeRevisions, RecipeMedia records, CookJournalEntries, JournalEntryMedia
- T-052.3: Delete S3 objects for all associated media assetRefs
- T-052.4: Return 204 No Content on success; 404 if not found or wrong user
- T-052.5: Note: Phase 2 Qdrant point cleanup is handled by T-065 — no Qdrant interaction needed here
- T-052.6: Wire delete action in recipe detail overflow menu — confirm dialog → DELETE → navigate to /recipes

**Acceptance:** Recipe and all associated data deleted. S3 objects removed. 404 for wrong user. Frontend confirm + delete flow works.

---

### T-054 · Ingredient alias accumulation
**Labels:** `backend`  
**Dependencies:** T-029, T-030

When a user confirms an ingredient mapping using a name variant not yet in the DB, add it as an alias.

**Subtasks:**
- T-054.1: In the candidate decision handler (T-030), after saving — for each ingredient row where `ingredientId` is set and the row's `text` differs from the canonical name and all existing aliases: call ingredient_repo.update_aliases to append the text as a new alias
- T-054.2: Deduplicate aliases before saving (case-insensitive, trimmed)
- T-054.3: Wire `PATCH /api/ingredients/{ingredientId}` from T-029.6 to support this from the review UI as well (user can manually trigger alias addition)
- T-054.4: Test: confirm "spring onion" maps to "green onion" → "spring onion" appears in aliases on subsequent ingredient search

**Acceptance:** New ingredient text variants accumulate as aliases automatically. No duplicates created. Future matching uses accumulated aliases.

---

### T-047 · Frontend wiring — ingestion flow
**Labels:** `frontend`  
**Dependencies:** T-046, T-014, T-013, T-026, T-030

Connect all ingestion screens to real backend APIs.

**Subtasks:**
- T-047.1: Wire ingestion entry page — form submission → `POST /api/ingestion` → navigate to `/ingest/[jobId]`
- T-047.2: Wire ingestion progress page — SSE subscription → update animated status steps → handle both `job.review_ready` (navigate to review with "Review recipe" CTA) and `job.draft_ready` (navigate to review with "Review draft" CTA) events → handle `job.failed` + rerun button (`POST /api/ingestion/jobs/{jobId}/rerun` → navigate to new jobId) → handle `job.unsupported`
- T-047.3: Wire candidate review page — fetch candidate → populate React Hook Form (ingredients, steps, metadata, tags) → display review findings sidebar → handle provenance indicators on agent-enriched fields → submit decision → navigate to `/recipes/[id]` or `/drafts/[id]`
- T-047.4: Handle all error states: submission failure, SSE disconnect + automatic reconnect (fetch snapshot GET + resume), review save failure with field-level errors
- T-047.5: Image upload flow on ingestion entry image tab — presigned URL → direct S3 upload → show preview → submit with assetRef
- T-047.6: Ingredient mapping UI in review — search dropdown per ingredient row (`GET /api/ingredients?search=...`), create-new option inline

**Acceptance:** Full ingestion flow works end-to-end in browser: paste URL → watch progress → review candidate → save recipe. Rerun button works. Draft-ready flow works. SSE reconnect recovers gracefully.

---

### T-099 · Media materialization on ingestion save
**Labels:** `backend`  
**Dependencies:** T-030, T-041, T-010

Download extracted image URLs from source and register as RecipeMedia when a canonical recipe is saved.

**Subtasks:**
- T-099.1: Create `/services/media_materialization_service.py` — `materialize_extracted_images(candidate, canonical_recipe_id, user_id)`
- T-099.2: Inspect candidate for extracted image URLs — from schema markup (heroImageUrl in candidateUpdate signals from T-021), from `url_metadata` artifact (heroImageUrl field)
- T-099.3: For each image URL (limit: 1 hero + up to 3 source gallery images): download via httpx with 10s timeout, upload to S3 using boto3 client (same config as T-010), generate assetRef
- T-099.4: Register each as RecipeMedia via recipe_media_repo — first image: role=hero, source="extracted"; additional: role=source_gallery, source="extracted"
- T-099.5: Call `materialize_extracted_images` from the `save_canonical` handler in T-030 after creating CanonicalRecipe
- T-099.6: Failure tolerance — if image download or upload fails for any image, log warning and continue. Canonical recipe save must never fail due to image materialization errors.
- T-099.7: Test: save canonical recipe from a schema page that has a hero image → verify RecipeMedia record exists with role=hero and accessible S3 URL

**Acceptance:** Canonical recipes from web sources have hero images registered automatically. Image failures don't block recipe save. Source gallery images captured up to limit.

---

---

# SPRINT 4 — Text + Image ingestion

**Goal:** All three source types supported. Recipe management screens wired to real data. Rate limiting in place.  
**Labels:** `phase-1` `p3-ingestion`

---

### T-032 · Text ingestion tools
**Labels:** `backend`  
**Dependencies:** T-015, T-024

Tools for processing pasted text sources.

**Subtasks:**
- T-032.1: Extend `classify_source` for text input type — detect structured recipe text vs freeform notes
- T-032.2: Implement text cleaning — trim whitespace, normalize line breaks, remove noise → create `cleaned_text` artifact
- T-032.3: Implement text structure analysis — detect recipe-likeness, identify probable sections (title/ingredients/steps) → create `text_structure_analysis` artifact
- T-032.4: Create `source_preview` artifact (text_excerpt variant) for pasted text sources
- T-032.5: Wire text source through agent: classify → clean → analyze structure → llm_structured_extract → evaluate
- T-032.6: Test with: clean recipe text (canonical-eligible), messy copy-paste (draft-eligible), non-recipe text (unsupported)

**Acceptance:** Pasted recipe text produces a candidate. Non-recipe text reaches unsupported. Messy text produces draft-eligible candidate.

---

### T-033 · OCR tools — Google Cloud Vision
**Labels:** `backend`  
**Dependencies:** T-015, T-024, T-017

Image ingestion via OCR + LLM extraction.

**Subtasks:**
- T-033.1: Create `/tools/ocr_tools.py`
- T-033.2: Implement `ocr_extract` tool — send image to Google Cloud Vision, return text + line blocks + confidence + handwriting detection → create `ocr_text` and `image_analysis` artifacts
- T-033.3: Create `source_preview` artifact (image variant) for uploaded images
- T-033.4: Wrap with tenacity retry (3 attempts) and ocr_breaker circuit breaker
- T-033.5: Quality validation: near-empty OCR text → low confidence signal; low overall OCR confidence → suggest multimodal LLM fallback
- T-033.6: Register `ocr_extract` as PydanticAI tool
- T-033.7: Wire image source through agent: classify → ocr_extract → assess_parseability → llm_structured_extract → evaluate
- T-033.8: Implement `llm_image_extraction` fallback — send original image directly to multimodal Claude when OCR quality too low
- T-033.9: Set reviewMode to `reconstruction` for handwritten sources
- T-033.10: Test with: clear recipe screenshot, printed cookbook page, handwritten recipe card, blurry image

**Acceptance:** OCR extracts text. Handwriting detected. Quality signals drive agent decisions. Multimodal fallback works. Handwritten sources get reconstruction review mode.

---

### T-053 · Draft delete endpoint
**Labels:** `backend` `frontend`  
**Dependencies:** T-030

`DELETE /api/drafts/{draftId}` for discarding unwanted drafts.

**Subtasks:**
- T-053.1: Create `DELETE /api/drafts/{draftId}` endpoint
- T-053.2: Hard delete draft record
- T-053.3: Return 204 No Content on success; 404 if not found or wrong user
- T-053.4: Wire discard/delete action on draft detail page — confirm dialog → DELETE → navigate to /recipes

**Acceptance:** Draft deleted cleanly. 404 for wrong user. Frontend confirm + delete flow works.

---

### T-057 · Rate limiting
**Labels:** `backend` `infrastructure`  
**Dependencies:** T-007

slowapi rate limiting middleware on the FastAPI app.

**Subtasks:**
- T-057.1: Add `slowapi` dependency
- T-057.2: Configure rate limiter middleware on FastAPI app using Redis as the backend store
- T-057.3: Apply per-user limits: `POST /api/ingestion` — 10 requests/minute; all other POST/PATCH/DELETE — 60 requests/minute; GET endpoints — 120 requests/minute
- T-057.4: Return 429 Too Many Requests with `Retry-After` header on limit exceeded
- T-057.5: Verify rate limiting works in integration test

**Acceptance:** Rate limits enforced per-user via Clerk userId. 429 returned with Retry-After header.

---

### T-048 · Frontend wiring — recipe management
**Labels:** `frontend`  
**Dependencies:** T-046, T-037, T-038, T-039, T-041, T-042, T-052

Connect recipe library, detail, edit, and journal screens to backend APIs.

**Subtasks:**
- T-048.1: Wire recipe library — `GET /api/recipes` → render cards → filter bar (status, tags, search, sort) → pagination (load more with cursor)
- T-048.2: Wire recipe detail — `GET /api/recipes/[id]` → render content + hero image + gallery + tags + provenance panel (expandable) + journal section
- T-048.3: Wire recipe edit — `GET /api/recipes/[id]` → populate React Hook Form → `PATCH /api/recipes/[id]` → revision feedback toast → navigate to detail
- T-048.4: Wire journal composer — `POST /api/recipes/[id]/journal` → optimistic append → tag selector with create-new → image upload (max 2, presigned URL flow)
- T-048.5: Wire journal delete — confirm dialog → `DELETE /api/journal/[id]` → optimistic remove
- T-048.6: Wire revision history drawer — `GET /api/recipes/[id]/revisions` → restore with confirm dialog → `POST .../restore` → refresh detail
- T-048.7: Wire media management — upload → presigned URL → register → hero swap
- T-048.8: Wire recipe delete — overflow menu → confirm dialog → `DELETE /api/recipes/[id]` → navigate to /recipes

**Acceptance:** All recipe management screens work with real data. Journal entries create and delete. Revisions viewable and restorable. Recipe delete works end to end.

---

---

# SPRINT 5 — Social + YouTube + Recipe APIs

**Goal:** All ingestion source types complete. All recipe, draft, journal, and media APIs live. Draft promotion works.  
**Labels:** `phase-1` `p4-social`

---

### T-034 · YouTube ingestion tools
**Labels:** `backend`  
**Dependencies:** T-015, T-019, T-022, T-024

YouTube-specific tools using Data API v3 and youtube-transcript-api.

**Subtasks:**
- T-034.1: Implement `youtube_api_fetch` tool — fetch metadata, description, first comment via YouTube Data API v3 → create `video_metadata` artifact
- T-034.2: Implement `youtube_transcript_fetch` tool — fetch transcript via youtube-transcript-api → create `video_transcript` artifact with timestamped segments
- T-034.3: Wrap both with tenacity retry and youtube_breaker circuit breaker; register as PydanticAI tools
- T-034.4: Wire YouTube fallback ladder: (1) youtube_api_fetch → extract_recipe_links in description → httpx_fetch linked page → schema/llm extract; (2) extract_recipe_links in first comment → httpx_fetch; (3) structured text from description → llm_structured_extract; (4) youtube_transcript_fetch → llm_structured_extract; (5) video_content_extraction (T-036)
- T-034.5: Test with: YouTube video with linked recipe blog; video with full recipe in description; transcript-only video

**Acceptance:** YouTube metadata and transcripts fetched. Linked pages followed preferentially. Transcript fallback works. Three test cases pass.

---

### T-035 · Social media ingestion tools
**Labels:** `backend`  
**Dependencies:** T-015, T-019, T-022, T-024, T-017

Instagram, TikTok, Facebook ingestion via yt-dlp + bio link resolution.

**Subtasks:**
- T-035.1: Implement `yt_dlp_fetch_metadata` tool — fetch caption, creator info, thumbnail via yt-dlp for Instagram/TikTok/Facebook → create `social_caption` and `video_metadata` artifacts
- T-035.2: Implement `fetch_creator_profile` tool — get creator profile metadata, bio text, bio URLs → create `creator_profile` artifact
- T-035.3: Implement `expand_bio_links` tool — follow linktree/beacons/redirect URLs, categorize each link (recipe_blog, website_home, shop, social_profile, other), identify bestRecipeCandidate → create `bio_link_urls` artifact
- T-035.4: Implement `discover_recipe_on_site` tool — search creator's website for recipe matching video title/caption keywords using httpx_fetch + LLM-assisted page matching
- T-035.5: Register all as PydanticAI tools
- T-035.6: Wire caption flow: classify → yt_dlp_fetch_metadata → extract_recipe_links (caption) → httpx_fetch → extract → evaluate
- T-035.7: Wire bio link flow: → fetch_creator_profile → expand_bio_links → httpx_fetch (best recipe link) → extract → evaluate
- T-035.8: Wire site discovery flow: → discover_recipe_on_site → httpx_fetch → extract → evaluate
- T-035.9: Test with: post with recipe link in caption; "link in bio" pointing to recipe blog; TikTok with short caption and no direct link

**Acceptance:** Social metadata and captions fetched via yt-dlp. Bio link resolution finds recipe blogs. Link categorization works. Three test cases pass.

---

### T-036 · Video processing tools
**Labels:** `backend`  
**Dependencies:** T-035, T-017

Video download, audio transcription (Whisper), key frame extraction, frame text analysis.

**Subtasks:**
- T-036.1: Implement `yt_dlp_download_video` tool — download video to temp storage, return file path + duration
- T-036.2: Implement `whisper_transcribe` tool — extract audio → OpenAI Whisper API → timestamped transcript → create `video_audio_transcript` artifact
- T-036.3: Implement `extract_key_frames` tool — sample frames via ffmpeg-python at 2–3s intervals, filter for frames with likely text content → store as temp files
- T-036.4: Implement `llm_frame_extract` tool — send selected frames to multimodal Claude, extract visible text with block type classification → create `video_frame_text` artifact
- T-036.5: Implement `merge_partial_candidates` tool — LLM-assisted merging of partial results (ingredients from caption + steps from transcript)
- T-036.6: Wire video processing flow: yt_dlp_download_video → whisper_transcribe + extract_key_frames (parallel) → llm_frame_extract → merge_partial_candidates → llm_structured_extract → evaluate
- T-036.7: Temp file cleanup after candidate creation
- T-036.8: Set reviewMode to `reconstruction` for video-extracted candidates
- T-036.9: Wrap all with tenacity retry and appropriate circuit breakers
- T-036.10: Test with: recipe reel with spoken instructions; TikTok with on-screen text overlays

**Acceptance:** Video downloads. Audio transcribes. Frames extracted and analyzed. Partial results merged. Temp files cleaned. Reconstruction mode set.

---

### T-037 · Recipe list API
**Labels:** `backend`  
**Dependencies:** T-009, T-030

Paginated recipe listing with filters, search, and sort.

**Subtasks:**
- T-037.1: Create `GET /api/recipes` with query params: `status`, `tags`, `search`, `sort`, `cursor`, `limit`
- T-037.2: Implement cursor-based pagination
- T-037.3: Status filter (all / canonical / draft) — query both CanonicalRecipe and DraftRecipe tables when "all"
- T-037.4: Tag filter — recipes matching any provided tagIds
- T-037.5: Text search — title and description ILIKE (will be upgraded to hybrid search in T-071)
- T-037.6: Sort options: updated_desc, created_desc, title_asc
- T-037.7: Return recipe card payload: id, type, title, description, times, servings, heroImageUrl, recipeTags (expanded), journalEntryCount

**Acceptance:** All filter combinations work. Pagination works. Response matches API contracts section 4.1.

---

### T-038 · Recipe detail API
**Labels:** `backend`  
**Dependencies:** T-030

Full recipe detail endpoint with media, tags, provenance, and journal count.

**Subtasks:**
- T-038.1: Create `GET /api/recipes/{recipeId}` endpoint
- T-038.2: Return composed payload: recipe content, heroImage, gallery (ordered), tags expanded, fieldProvenanceMap, sourceAssetId, journalSummary, revisionCount, journalEntryCount
- T-038.3: Handle 404 if recipe not found or wrong user

**Acceptance:** Returns complete recipe detail matching API contracts section 4.2.

---

### T-039 · Recipe edit API
**Labels:** `backend`  
**Dependencies:** T-038

Partial update with automatic revision detection.

**Subtasks:**
- T-039.1: Create `PATCH /api/recipes/{recipeId}` accepting partial fields
- T-039.2: Create `/repositories/recipe_revision_repo.py` — create snapshot before applying changes
- T-039.3: Revision-worthiness check: title, ingredients, steps, times, servings changes → create revision. Tag-only changes → no revision.
- T-039.4: Return revisionCreated flag and revisionId
- T-039.5: Validate: cannot blank title, cannot remove all ingredients or steps

**Acceptance:** Partial updates work. Revisions created for meaningful changes only. Matches API contracts section 4.3.

---

### T-040 · Revision history + restore API
**Labels:** `backend`  
**Dependencies:** T-039

List revisions and restore a previous version.

**Subtasks:**
- T-040.1: Create `GET /api/recipes/{recipeId}/revisions` — list with timestamps and change summaries
- T-040.2: Create `POST /api/recipes/{recipeId}/revisions/{revisionId}/restore` — non-destructive: save current state as new revision, apply restored content as current

**Acceptance:** Revision list returns summaries. Restore is non-destructive. Matches API contracts sections 4.4–4.5.

---

### T-041 · Recipe media API
**Labels:** `backend`  
**Dependencies:** T-010, T-038

Media registration, role management, and deletion for recipes.

**Subtasks:**
- T-041.1: Create `/repositories/recipe_media_repo.py` — create, update, delete, find_by_recipe
- T-041.2: Create `POST /api/recipes/{recipeId}/media` — register with role and displayOrder
- T-041.3: Create `PATCH /api/recipes/{recipeId}/media/{mediaId}` — update role (hero swap demotes previous hero to source_gallery)
- T-041.4: Create `DELETE /api/recipes/{recipeId}/media/{mediaId}` — cannot delete last hero image (409)

**Acceptance:** Media registration, hero swap, deletion work. Matches API contracts section 5.

---

### T-042 · Cook journal API
**Labels:** `backend`  
**Dependencies:** T-038, T-031

Journal entry CRUD with tags and media.

**Subtasks:**
- T-042.1: Create `/repositories/journal_repo.py` — create, delete, list_by_recipe (newest first, cursor pagination)
- T-042.2: Create `GET /api/recipes/{recipeId}/journal` — paginated, newest first
- T-042.3: Create `POST /api/recipes/{recipeId}/journal` — body, optional cookedOn, tags (journal domain), mediaRefs (max 2)
- T-042.4: Create `DELETE /api/journal/{entryId}` — hard delete entry + associated JournalEntryMedia records
- T-042.5: On entry create/delete: trigger journalSummary regen via **`regenerate_journal_summary_send`** (`enqueue`; **revisit:** Dramatiq)

**Acceptance:** Journal CRUD works. Max 2 images enforced. Newest-first ordering. journalSummary regeneration triggered. Matches API contracts section 6.

---

### T-043 · Journal summary generation
**Labels:** `backend`  
**Dependencies:** T-042, T-011

Async LLM-generated journalSummary on canonical recipes.

**Subtasks:**
- T-043.1: Implement **`journal_summary_worker`** with **`enqueue`** entrypoint (**revisit:** Dramatiq actor)
- T-043.2: Load all journal entries for the recipe
- T-043.3: If zero entries, set journalSummary to null
- T-043.4: If entries exist, send to Claude Sonnet with summarization prompt — extract: substitutions that worked, timing deviations, family/household preferences, success/failure signals, meaningful usage context. Exclude conversational noise.
- T-043.5: Update `CanonicalRecipe.journalSummary` with generated summary
- T-043.6: Full regeneration from all entries (not incremental)

**Acceptance:** journalSummary generated after journal changes. Captures useful patterns. Null when no entries exist.

---

### T-044 · Draft APIs
**Labels:** `backend`  
**Dependencies:** T-030

Draft fetch, edit, and promotion endpoints.

**Subtasks:**
- T-044.1: Create `GET /api/drafts/{draftId}` endpoint
- T-044.2: Create `PATCH /api/drafts/{draftId}` — partial update, recalculate `promotionEligible`
- T-044.3: Create `POST /api/drafts/{draftId}/review-for-canonical` — re-assess eligibility, return findings and allowedActions
- T-044.4: Create `POST /api/drafts/{draftId}/promote` — validate eligibility, create CanonicalRecipe with promotion metadata, delete draft, return canonicalRecipeId
- T-044.5: Promotion requires review-for-canonical to have been called first (409 otherwise)

**Acceptance:** Draft CRUD and promotion works. Matches API contracts section 3.

---

### T-049 · Frontend wiring — drafts
**Labels:** `frontend`  
**Dependencies:** T-046, T-044, T-053

Connect draft detail and promotion screens.

**Subtasks:**
- T-049.1: Wire draft detail — `GET /api/drafts/[id]` → edit form (same structure as recipe edit) → `PATCH /api/drafts/[id]` → draft banner with missing field indicators → promotion CTA enabled/disabled based on `promotionEligible`
- T-049.2: Wire promotion flow — "Review for trusted save" → `POST /api/drafts/[id]/review-for-canonical` → display assessment (eligible/not eligible, findings list) → confirm → `POST /api/drafts/[id]/promote` → navigate to `/recipes/[newId]`
- T-049.3: Draft badge display in recipe library (type=draft shown with clear label)
- T-049.4: Wire draft delete — confirm dialog → `DELETE /api/drafts/[id]` → navigate to /recipes

**Acceptance:** Draft edit, promotion, and delete flows work end to end.

---

---

# SPRINT 6 — Phase 1 polish + deploy

**Goal:** Phase 1 is live on Vercel + Railway. Error handling is solid. Images are optimized.  
**Labels:** `phase-1` `p5-deploy`

---

### T-050 · Error handling + observability
**Labels:** `backend` `frontend` `infrastructure`  
**Dependencies:** T-007

Structured logging, error tracking, and user-facing error states.

**Subtasks:**
- T-050.1: Configure structlog throughout backend — all tool calls, agent decisions, and state transitions log with job_id, tool_name, duration, outcome
- T-050.2: Create consistent error response middleware — all errors return `{error: {code, message, details}}` shape
- T-050.3: Implement user-friendly error messages for all known error types (source_access, source_quality, parseability, internal)
- T-050.4: Add Sentry integration (backend + frontend) — capture exceptions, configure environment tags

**Acceptance:** All API errors return consistent shape. Backend logs are structured JSON. Error messages are specific and actionable. Sentry capturing exceptions.

---

### T-051 · Deployment — Phase 1
**Labels:** `infrastructure`  
**Dependencies:** T-008, T-047, T-048

Deploy to Vercel (frontend) + Railway (backend).

**Subtasks:**
- T-051.1: Create Railway project: FastAPI service, Postgres, Redis. **Optional second service** if Dramatiq (or similar) returns.
- T-051.2: Configure Railway env vars: DB URL, Redis URL, Clerk keys, S3 credentials, Anthropic API key, Google Cloud Vision key, OpenAI key (Whisper), YouTube Data API key
- T-051.3: Set deploy command: `alembic upgrade head && uvicorn ...`
- T-051.4: Run ingredient seed as one-time command on first deploy
- T-051.5: Create Vercel project linked to `/apps/web` — configure env vars (Clerk publishable key, API base URL → Railway)
- T-051.6: Verify end-to-end on production: sign in → ingest URL → SSE progress → review → save → view in library

**Acceptance:** App is live. Auth works. Ingestion pipeline runs. SSE streams across Vercel→Railway boundary.

---

### T-058 · Image thumbnailing + optimization
**Labels:** `backend` `infrastructure`  
**Dependencies:** T-041, T-010

Generate thumbnail variants for recipe media to optimize library view load times.

**Subtasks:**
- T-058.1: Choose approach: Pillow on upload (simpler) vs CloudFront image transforms (deferred infra)
- T-058.2: On media registration (T-041 and T-099): generate 400px-wide thumbnail with Pillow, store as separate S3 key (`{assetRef}_thumb`)
- T-058.3: Return both `url` (full-size) and `thumbnailUrl` in all media API responses
- T-058.4: Update RecipeMedia model to include `thumbnailUrl` field
- T-058.5: Use thumbnailUrl on recipe cards and library view; full url on recipe detail and lightbox

**Acceptance:** Library view loads thumbnail-sized images. Recipe detail uses full-size. RecipeMedia API responses include thumbnailUrl.

---

---

# SPRINT 7 — Embedding + Indexing pipeline

**Goal:** Every canonical recipe has dense + sparse vectors in Qdrant. Vectors stay current as recipes and journals change.  
**Labels:** `phase-2` `p6-embedding`

---

### T-059 · Qdrant setup + collection configuration
**Labels:** `infrastructure`  
**Dependencies:** T-051

Deploy Qdrant and configure the recipe search collection.

**Subtasks:**
- T-059.1: Add Qdrant service to Railway (Qdrant Cloud or self-hosted container)
- T-059.2: Add `QDRANT_URL` and `QDRANT_API_KEY` to env vars (Railway, Vercel, .env.example)
- T-059.3: Add Qdrant to `docker-compose.yml` for local dev: `qdrant/qdrant:latest`, port 6333, persistent volume
- T-059.4: Create `/app/core/qdrant.py` — async Qdrant client configuration
- T-059.5: Create collection `kama_recipes` with: named dense vector "dense" (size=1536, distance=Cosine) + named sparse vector "sparse" (BM25)
- T-059.6: Define payload schema + enable payload indexes: `recipeId` (keyword), `userId` (keyword), `tagIds` (keyword[]), `ingredientIds` (keyword[]), `prepTimeMinutes` (int), `cookTimeMinutes` (int), `servings` (int), `createdAt` (datetime), `updatedAt` (datetime)
- T-059.7: Verify: create collection → confirm vector config and payload schema in Qdrant dashboard

**Acceptance:** Qdrant running and reachable locally and on Railway. Collection created with correct dense + sparse + payload config.

---

### T-060 · RecipeSearchIndexStatus model + migration
**Labels:** `backend`  
**Dependencies:** T-009, T-059

Postgres tracking model for embedding status per recipe.

**Subtasks:**
- T-060.1: Create SQLAlchemy model `RecipeSearchIndexStatus` — canonicalRecipeId (FK, unique), sourceText (text), embeddingModel (string), indexedAt (datetime), stale (bool, default true), staleReason (nullable string), staleSince (nullable datetime)
- T-060.2: Generate and run Alembic migration
- T-060.3: Create `/repositories/recipe_search_index_repo.py` — create, get_by_recipe_id, mark_stale, mark_indexed, find_all_stale

**Acceptance:** Model and migration applied. Repo functions work. New canonical recipes get an index status record (stale=true) on creation.

---

### T-061 · Embedding service — dense vectors
**Labels:** `backend`  
**Dependencies:** T-060

OpenAI text-embedding-3-small integration for dense recipe embeddings.

**Subtasks:**
- T-061.1: Create `/services/embedding_service.py`
- T-061.2: Implement source text composition: `{title}. {description}. Ingredients: {ingredient names joined}. Tags: {tag names joined}. {journalSummary}`
- T-061.3: Implement `generate_dense_embedding(text: str) -> list[float]` — calls OpenAI text-embedding-3-small, returns 1536-dimension vector
- T-061.4: Token length guard — if source text exceeds token limit, truncate intelligently (drop journalSummary first, then description)
- T-061.5: Wrap with tenacity retry (3 attempts, backoff) and llm_breaker circuit breaker

**Acceptance:** Dense embedding generated for any recipe source text. Returns 1536-dimension vector. Token limit handled gracefully.

---

### T-062 · BM25 sparse vector generation
**Labels:** `backend`  
**Dependencies:** T-061

Sparse BM25 vector generation for lexical keyword matching.

**Subtasks:**
- T-062.1: Evaluate approach: Qdrant's built-in FastEmbed sparse encoder vs Python `rank_bm25`. Document decision in code comments.
- T-062.2: Implement `generate_sparse_vector(text: str) -> SparseVector` — returns `{indices: list[int], values: list[float]}`
- T-062.3: Consistent tokenization with the embedding service — lowercase, normalize punctuation
- T-062.4: Unit test: generate sparse vector for a sample recipe, verify indices and values shape are valid

**Acceptance:** Sparse BM25 vector generated for any text. Returns valid `{indices, values}` sparse vector.

---

### T-063 · Qdrant client service
**Labels:** `backend`  
**Dependencies:** T-059, T-061, T-062

Service layer for all Qdrant operations — upsert, hybrid search, and delete.

**Subtasks:**
- T-063.1: Create `/services/qdrant_client_service.py`
- T-063.2: Implement `upsert_recipe_point(recipe_id, dense_vector, sparse_vector, payload)` — upsert to kama_recipes collection
- T-063.3: Implement `hybrid_search(dense_vector, sparse_vector, payload_filter, limit, offset)` — single Qdrant hybrid query with RRF fusion, returns ranked recipe IDs with scores
- T-063.4: Implement `delete_recipe_point(recipe_id)` — remove point
- T-063.5: Implement `get_recipe_point(recipe_id)` — retrieve point for debug/verify
- T-063.6: Handle Qdrant connection errors — log and raise domain-specific `QdrantUnavailableError`
- T-063.7: Integration test: upsert → search → verify appears → delete → verify gone

**Acceptance:** Upsert, hybrid search, delete all work. Connection errors handled cleanly.

---

### T-064 · Search index worker
**Labels:** `backend`  
**Dependencies:** T-063, T-011

**As-built:** Async background task (**`index_recipe_send`** → **`background_runner.enqueue`**) that generates and upserts recipe embeddings to Qdrant. **Revisit:** Dramatiq actor consuming a Redis queue.

**Subtasks:**
- T-064.1: Create `/workers/search_index_worker.py` — **`index_recipe_send(recipe_id)`** → **`enqueue(_index_recipe, …)`** (**revisit:** Dramatiq actor `index_recipe`)
- T-064.2: Load canonical recipe from Postgres (title, description, ingredients, tags, journalSummary)
- T-064.3: Compose source text via embedding_service
- T-064.4: Generate dense embedding via embedding_service
- T-064.5: Generate sparse BM25 vector via embedding_service
- T-064.6: Compose payload metadata (userId, tagIds, ingredientIds, times, servings, dates)
- T-064.7: Upsert point to Qdrant via qdrant_client_service
- T-064.8: Update RecipeSearchIndexStatus: stale=false, indexedAt=now, sourceText, embeddingModel
- T-064.9: On failure: log error, do not crash (stale Qdrant point still searchable during next run)
- T-064.10: Integration test: create recipe → **`index_recipe_send`** → verify point exists in Qdrant

**Acceptance:** Worker generates and upserts both vectors. Index status updated. Failures logged without crashing.

---

### T-065 · Staleness triggers
**Labels:** `backend`  
**Dependencies:** T-064, T-039, T-042, T-031, T-052

Mark RecipeSearchIndexStatus stale and trigger re-indexing on recipe changes.

**Subtasks:**
- T-065.1: After canonical recipe save (T-030 decision handler) — create RecipeSearchIndexStatus record (stale=true), **`index_recipe_send`**
- T-065.2: After recipe content edit (T-039 PATCH handler, revision-worthy changes only) — mark stale, **`index_recipe_send`**
- T-065.3: After journalSummary update (T-043 worker completion) — mark stale, **`index_recipe_send`**
- T-065.4: After recipe tag change — mark stale, **`index_recipe_send`**
- T-065.5: After recipe delete (T-052 handler) — delete Qdrant point via qdrant_client_service, delete RecipeSearchIndexStatus record
- T-065.6: Test: edit recipe title → status becomes stale → **`index_recipe_send`** runs → stale=false → Qdrant point updated

**Acceptance:** All five trigger points fire correctly. Deleted recipes removed from Qdrant. No duplicate re-indexing on tag-only non-content changes.

---

### T-066 · Backfill job for existing recipes
**Labels:** `backend`  
**Dependencies:** T-064, T-065

One-time job to index all existing canonical recipes that don't yet have a Qdrant point.

**Subtasks:**
- T-066.1: Create `POST /api/admin/embeddings/backfill` endpoint — enqueues backfill via **`index_recipe_send`** / batch (**revisit:** Dramatiq `backfill_embeddings` job)
- T-066.2: **Backfill logic** — find canonical recipes needing index, **`index_recipe_send`** each (**revisit:** Dramatiq actor batching)
- T-066.3: Log progress: recipes processed, remaining, errors
- T-066.4: Create `POST /api/admin/recipes/{recipeId}/regenerate-embedding` — single-recipe debug regeneration
- T-066.5: Add admin-only middleware check on `/api/admin/*` endpoints
- T-066.6: Run backfill on Phase 2 deployment; verify all recipes have non-stale index status + Qdrant points

**Acceptance:** Backfill indexes all existing canonical recipes. Admin endpoints work. After backfill, all recipes searchable.

---

---

# SPRINT 8 — Search

**Goal:** Users can search their recipe corpus using natural language, ingredient filters, tag filters, and time constraints.  
**Labels:** `phase-2` `p7-search`

---

### T-067 · Query parser service
**Labels:** `backend`  
**Dependencies:** T-012, T-059

LLM-assisted decomposition of natural language search queries into structured filters + semantic text.

**Subtasks:**
- T-067.1: Create `/services/query_parser_service.py`
- T-067.2: Design parsing prompt — input: raw query; output: ParsedQuery (structuredFilters + semanticQuery + queryIntent)
- T-067.3: Use PydanticAI structured output with `ParsedQuery` Pydantic model validation
- T-067.4: Structured filter extraction: "under 30 min" → maxCookTimeMinutes: 30; "vegetarian" → resolve tagId; "with paneer" → resolve ingredientId
- T-067.5: Tag and ingredient resolution — match extracted terms to actual DB IDs via ingredient_repo and tag_repo
- T-067.6: queryIntent detection: `"search"` (find recipes), `"ask"` (question-style), `"ambiguous"`
- T-067.7: Handle empty/short queries gracefully — return empty filters, pass query as-is
- T-067.8: Wrap with tenacity retry + llm_breaker
- T-067.9: Unit tests: "quick vegetarian pasta" → `{tagIds: [tag_vegetarian], semanticQuery: "quick pasta"}`; "recipes I should remake" → `{semanticQuery: "recipes worth remaking", queryIntent: "search"}`; "what can I make with chickpeas?" → `{queryIntent: "ask"}`

**Acceptance:** Natural language queries decomposed correctly. Tag/ingredient IDs resolved. queryIntent classified. Retries on malformed output.

---

### T-068 · Hybrid search service
**Labels:** `backend`  
**Dependencies:** T-063, T-067, T-061, T-062

Orchestrates query parsing → embedding → single Qdrant hybrid query → Postgres hydration.

**Subtasks:**
- T-068.1: Create `/services/search_service.py`
- T-068.2: Implement `search_recipes(query, filters, user_id, limit, cursor) -> SearchResults`
- T-068.3: Parse query via query_parser_service; merge explicit filters with LLM-extracted ones
- T-068.4: Generate dense query embedding via embedding_service
- T-068.5: Generate sparse BM25 query vector via embedding_service
- T-068.6: Build Qdrant payload filter from structuredFilters — userId scoping always applied
- T-068.7: Execute single hybrid Qdrant query: payload filter + dense + sparse + RRF fusion
- T-068.8: Hydrate full recipe card objects from Postgres using returned recipe IDs (maintaining ranked order)
- T-068.9: Compose `matchReasons` per result (tag match, time constraint, semantic relevance)
- T-068.10: Handle filters-only case (no query text) — Qdrant payload-only filter query, sorted by updatedAt
- T-068.11: Implement cursor-based pagination using Qdrant offset
- T-068.12: Graceful degradation: if Qdrant unavailable, fall back to Postgres ILIKE with `searchQualityReduced: true` flag in response

**Acceptance:** Single Qdrant call per search. Results ranked by RRF fusion. Hydrated from Postgres. Pagination works. Graceful Qdrant fallback.

---

### T-069 · Search API endpoint
**Labels:** `backend`  
**Dependencies:** T-068

`POST /api/search` exposing hybrid search.

**Subtasks:**
- T-069.1: Create `POST /api/search` with request body: `query` (optional), `filters` (optional), `limit`, `cursor`
- T-069.2: Validate request — at least one of query or filters required
- T-069.3: Call search_service with user_id from auth token
- T-069.4: Return: `items` (recipe cards with `relevanceScore` and `matchReasons`), `parsedQuery` (shows interpretation), `nextCursor`, `hasMore`, `searchQualityReduced` (if Qdrant fallback used)
- T-069.5: Add auth dependency
- T-069.6: Integration test: submit search → verify response shape matches Phase 2 API contracts section 1

**Acceptance:** Search endpoint works. Response includes parsedQuery transparency. Results user-scoped. Matches Phase 2 API contracts section 1.1.

---

### T-070 · Search UI
**Labels:** `frontend`  
**Dependencies:** T-069

`/search` route with search input, filter bar, results, and pagination.

**Subtasks:**
- T-070.1: Generate search page using v0 — search input, filter bar (tag multi-select, max cook time input, ingredient search), results grid
- T-070.2: Wire search — debounced `POST /api/search` as user types (400ms debounce)
- T-070.3: Wire filter bar — tag multi-select, maxCookTimeMinutes input, ingredient ID filter
- T-070.4: Display parsedQuery interpretation below search bar ("Searching for: quick pasta · Filtered to: vegetarian, under 30 min")
- T-070.5: Display `matchReasons` on each result card (subtle chips: "tag: vegetarian", "semantic match")
- T-070.6: Handle empty results, loading skeletons, initial empty state (no search yet)
- T-070.7: Implement load-more / infinite scroll pagination using `nextCursor`
- T-070.8: Persist active filters in URL query params for shareability and back-button support
- T-070.9: If `searchQualityReduced: true` in response, show subtle "Search quality reduced" indicator

**Acceptance:** Search returns results as user types. Pagination works. parsedQuery interpretation shown. URL params updated. Reduced quality indicator shown on Qdrant fallback.

---

### T-071 · Search integration in recipe library
**Labels:** `backend` `frontend`  
**Dependencies:** T-069, T-037

Replace basic ILIKE library search with hybrid search.

**Subtasks:**
- T-071.1: Update `GET /api/recipes` — when `search` param provided, proxy to hybrid search service instead of ILIKE. Return queryIntent in response metadata.
- T-071.2: Preserve existing filter behavior (status, tags, sort) alongside search results
- T-071.3: Update recipe library frontend — search input uses hybrid search results
- T-071.4: Graceful fallback if search service unavailable

**Acceptance:** Library search uses hybrid search. Existing filters still work. Graceful fallback on failure.

---

---

# SPRINT 9 — Ask

**Goal:** Users can ask natural language questions over their recipe corpus with grounded answers, follow-up support, and recipe-scoped chef persona.  
**Labels:** `phase-2` `p8-ask`

---

### T-072 · AskSession model + repository
**Labels:** `backend`  
**Dependencies:** T-009

Persist Ask sessions and message history.

**Subtasks:**
- T-072.1: Create SQLAlchemy models: `AskSession` (id, userId, status, createdAt, lastActiveAt, closedAt) and `AskMessage` (id, sessionId, role, content, retrievedRecipeIds JSONB, citedRecipeIds JSONB, createdAt)
- T-072.2: Generate and run Alembic migration
- T-072.3: Create `/repositories/ask_session_repo.py` — create_session, get_session, add_message, list_messages, close_session, find_expired_sessions

**Acceptance:** Models created. Migration applied. Repo functions work.

---

### T-073 · Ask retrieval service
**Labels:** `backend`  
**Dependencies:** T-068, T-072

Retrieve relevant recipes for an Ask query using hybrid search.

**Subtasks:**
- T-073.1: Create `/services/ask_service.py`
- T-073.2: Implement `retrieve_for_ask(question, session_context, user_id) -> list[CanonicalRecipe]`
- T-073.3: Parse question via query_parser_service → run hybrid search → retrieve top-8 relevant recipes
- T-073.4: Hydrate full recipe objects including ingredients, steps, journalSummary
- T-073.5: For follow-ups: combine current question with prior session context (retrievedRecipeIds) to improve retrieval quality

**Acceptance:** Retrieval returns relevant canonical recipes. Follow-up questions leverage session context.

---

### T-074 · Ask generation service
**Labels:** `backend`  
**Dependencies:** T-073

LLM grounded answer generation with recipe citations.

**Subtasks:**
- T-074.1: Design Ask system prompt — grounded recipe assistant, cite by recipe name/ID, no drafts, no open web knowledge
- T-074.2: Implement `generate_answer(question, retrieved_recipes, session_messages) -> AskAnswer`
- T-074.3: Construct LLM prompt: system + session history + retrieved recipe content + user question
- T-074.4: Use PydanticAI structured output — validate `content` and `citedRecipeIds`
- T-074.5: Verify all citedRecipeIds exist in retrieved set (prevent hallucinated citations)
- T-074.6: Wrap with tenacity retry + llm_breaker
- T-074.7: Chef persona mode — when `recipe_id` provided: load single recipe as full context, use expert chef system prompt for cooking-specific questions about that recipe

**Acceptance:** Answers grounded in retrieved recipes. citedRecipeIds extracted and validated. Session history included for follow-ups. Chef persona works.

---

### T-075 · Ask API endpoints
**Labels:** `backend`  
**Dependencies:** T-074

All Ask session endpoints.

**Subtasks:**
- T-075.1: Create `POST /api/ask/sessions` — create session, run retrieval + generation, return sessionId + answer + citedRecipes
- T-075.2: Create `POST /api/ask/sessions/{sessionId}/messages` — validate session active (409 if closed), run retrieval + generation with history, return answer + citedRecipes
- T-075.3: Create `POST /api/ask/sessions/{sessionId}/close` — mark closed
- T-075.4: Create `GET /api/ask/sessions/{sessionId}` — full session with message history (for page refresh/recovery)
- T-075.5: Auth dependency on all endpoints; update `lastActiveAt` on every message
- T-075.6: Integration test: create session → send follow-up → verify session history maintained

**Acceptance:** All four endpoints work. Session context flows through follow-ups. Matches Phase 2 API contracts section 2.

---

### T-076 · Session timeout + cleanup worker
**Labels:** `backend`  
**Dependencies:** T-072, T-011

Periodic worker that closes expired sessions and cleans up old data.

**Subtasks:**
- T-076.1: Create `/workers/ask_cleanup_worker.py` — **`run_ask_cleanup_loop`** from FastAPI lifespan (**asyncio**; **revisit:** Dramatiq periodic actor)
- T-076.2: Close sessions inactive for > 15 minutes (lastActiveAt stale)
- T-076.3: Delete sessions older than 7 days
- T-076.4: Log summary: sessions closed, deleted

**Acceptance:** Expired sessions auto-closed. Old sessions cleaned up after 7 days. Worker runs without errors.

---

### T-077 · Ask UI
**Labels:** `frontend`  
**Dependencies:** T-075

`/ask` and `/ask/[sessionId]` routes.

**Subtasks:**
- T-077.1: Generate Ask entry page using v0 — question input, welcome state with 3 suggested questions
- T-077.2: Wire first question — `POST /api/ask/sessions` → navigate to `/ask/[sessionId]`
- T-077.3: Generate Ask session page — chat-style message thread (user bubbles + assistant responses with cited recipe cards), follow-up input fixed at bottom, session status indicator
- T-077.4: Wire follow-up — `POST /api/ask/sessions/{sessionId}/messages` → append user message → show typing indicator → append assistant response
- T-077.5: Cited recipe cards inline — compact recipe card (hero thumbnail, title, cook time), clickable to `/recipes/[id]`
- T-077.6: Handle closed session — thread visible as read-only, input disabled, "Start new question" link → `/ask`
- T-077.7: Handle loading: typing indicator on assistant side while generating
- T-077.8: Handle empty corpus — "You don't have any saved recipes yet" with link to /ingest
- T-077.9: `GET /api/ask/sessions/{sessionId}` on page load for refresh/recovery

**Acceptance:** Ask flow works end to end. Cited recipes displayed inline. Follow-ups maintain context. All states handled.

---

### T-078 · Recipe-scoped Ask — chef persona
**Labels:** `backend` `frontend`  
**Dependencies:** T-075, T-074

Contextual Ask on recipe detail page using an expert chef persona.

**Subtasks:**
- T-078.1: Add "Ask about this recipe" section to recipe detail page UI — positioned below gallery, above journal section
- T-078.2: Wire question input — `POST /api/ask/sessions` with `recipeId` field in request body
- T-078.3: Backend: detect `recipeId` in session request → use chef persona system prompt + full recipe context (ingredients, steps, journalSummary) → skip corpus-wide retrieval
- T-078.4: Display answer inline on recipe detail (not full-page navigation)
- T-078.5: Surface 3 example questions in the UI: "What can I substitute for cream in this?", "Can I make this ahead?", "How do I know when it's done?"
- T-078.6: Wire follow-up questions within the same recipe context

**Acceptance:** Chef persona answers cooking questions about the specific recipe. Distinct from corpus-wide Ask. Follow-ups work inline.

---

### T-100 · Search/Ask intent routing
**Labels:** `frontend`  
**Dependencies:** T-069, T-077

Route question-intent queries from search to the Ask surface.

**Subtasks:**
- T-100.1: On library search and `/search` page: after receiving search results, check `parsedQuery.queryIntent`
- T-100.2: If `queryIntent === "ask"` — display non-intrusive banner: "This looks like a question. Try asking Kama →" with button navigating to `/ask?q={encodedQuery}`
- T-100.3: On `/ask` page: read `q` query param on mount, pre-fill question input with the decoded value
- T-100.4: On `/search` initial state: show subtle prompt distinguishing search from ask — "Looking for a recipe? Search here. Want to ask a question? Try Ask →"

**Acceptance:** Question-intent queries show Ask suggestion in search. Pre-fill works when navigating from search to Ask. Surfaces are clearly differentiated.

---

---

# SPRINT 10 — Artifacts + Shopping list

**Goal:** Users can generate a shopping list from selected recipes. Artifacts are saved, editable, versioned.  
**Labels:** `phase-2` `p9-artifacts`

---

### T-079 · Artifact model + repository
**Labels:** `backend`  
**Dependencies:** T-009

Artifact domain model — base for all Create outputs.

**Subtasks:**
- T-079.1: Create SQLAlchemy model `Artifact` — id, userId, artifactType (shopping_list | meal_plan | pantry_feasibility), title, content JSONB, sourceRecipeIds JSONB, status (active | archived), createdAt, updatedAt
- T-079.2: Create SQLAlchemy model `ArtifactRevision` — id, artifactId, snapshotPayload JSONB, changeSummary, createdAt
- T-079.3: Generate and run Alembic migration
- T-079.4: Create `/repositories/artifact_repo.py` — create, get_by_id, list_by_user, update, archive, create_revision, list_revisions, get_revision

**Acceptance:** Artifact and ArtifactRevision models created. All repo functions work. Migration applied.

---

### T-080 · Artifact revision handling
**Labels:** `backend`  
**Dependencies:** T-079

Revision creation on content edit and non-destructive restore.

**Subtasks:**
- T-080.1: On every content PATCH to an artifact — create ArtifactRevision snapshot before applying change
- T-080.2: Auto-generate changeSummary on revision creation (brief description of what changed)
- T-080.3: Create `GET /api/artifacts/{artifactId}/revisions` endpoint
- T-080.4: Create `POST /api/artifacts/{artifactId}/revisions/{revisionId}/restore` — non-destructive: save current as revision, apply restored content

**Acceptance:** Every content edit creates a revision. Restore is non-destructive. Matches Phase 2 API contracts sections 3.6–3.7.

---

### T-081 · Shopping list generation service
**Labels:** `backend`  
**Dependencies:** T-079, T-068

Generate a grouped, deduplicated shopping list from one or more canonical recipes. **Groups by `ingredient.category` directly** for mapped ingredients — no LLM call needed. LLM classification is a **fallback only for unmapped ingredients** (no `ingredientId` → no category → heuristic guess, then LLM if ambiguous).

**Subtasks:**
- T-081.1: Create `/services/shopping_list_service.py`
- T-081.2: Implement `generate_shopping_list(session, recipe_ids, user_id, title) -> dict`
- T-081.3: Hydrate all recipe ingredients from Postgres
- T-081.4: Deduplicate ingredients by `ingredientId` — combine `displayText` and `sourceRecipeIds` where possible
- T-081.5: **For mapped ingredients** (have `ingredientId`): look up `ingredient.category` from DB → use directly as shopping section
- T-081.6: **For unmapped ingredients** (no `ingredientId`): use heuristic keyword matching to guess category; LLM call is a last-resort fallback only
- T-081.7: Build sections in consistent display order (Produce → Dairy & Eggs → Meat & Poultry → Seafood → … → Other) using `CATEGORY_DISPLAY_ORDER`
- T-081.8: Build ShoppingListContent structure — sections with `category`, `displayName`, items with `sourceRecipeIds` and `checked=false`
- T-081.9: Persist as Artifact with `sourceRecipeIds`
- T-081.10: Handle null `sourceRecipeIds` gracefully in GET responses (for deleted recipes — return item with recipeId: null, recipeTitle: "Deleted recipe")
- T-081.11: Auto-generate list title from recipe names if not provided

**Acceptance:** Shopping list generated from any recipe selection. Ingredients deduplicated via `ingredientId`. **Grouped by `ingredient.category` from DB** (no LLM needed for mapped ingredients). Unmapped items fall back to heuristic/LLM. Sections ordered consistently. Saved as Artifact.

---

### T-082 · Shopping list + artifact API endpoints
**Labels:** `backend`  
**Dependencies:** T-081, T-080

Full CRUD for artifacts.

**Subtasks:**
- T-082.1: Create `POST /api/artifacts/generate` — routes to correct service based on artifactType, returns Artifact
- T-082.2: Create `GET /api/artifacts/{artifactId}` — return full artifact with content
- T-082.3: Create `GET /api/artifacts` — paginated list, optional type filter and status filter (active / archived)
- T-082.4: Create `PATCH /api/artifacts/{artifactId}` — partial update (title, content), creates revision, returns revisionCreated flag
- T-082.5: Create `POST /api/artifacts/{artifactId}/archive` — status → archived
- T-082.6: Auth dependency on all endpoints
- T-082.7: Integration tests for all five endpoints

**Acceptance:** All artifact endpoints work. Auth scoped correctly. Matches Phase 2 API contracts section 3.

---

### T-083 · Shopping list UI + Artifacts library
**Labels:** `frontend`  
**Dependencies:** T-082

`/create/shopping-list/new`, `/artifacts`, and `/artifacts/[id]`.

**Subtasks:**
- T-083.1: Generate shopping list generator page using v0 — two-step flow: Step 1 (recipe selection with searchable checkboxes, selected recipe chips, optional instructions field, "Generate" button); Step 2 (generated list displayed inline before saving, fully editable: check items, add/remove items, edit quantities, edit title)
- T-083.2: Wire recipe selection — search input calls `POST /api/search` as user types → compact selectable recipe cards with checkboxes
- T-083.3: Wire generation — `POST /api/artifacts/generate` → render generated list inline as Step 2 (do not navigate yet)
- T-083.4: Wire inline editing in Step 2 — check/uncheck, add item, remove item, edit quantity → build up edited content client-side
- T-083.5: Wire save — `POST /api/artifacts/generate` or `PATCH /api/artifacts/{id}` → navigate to `/artifacts/[id]`
- T-083.6: Generate artifact detail page — shopping list view: category sections with checkboxes, source recipe indicator per item, title editable
- T-083.7: Wire post-save editing in artifact detail — PATCH on any change
- T-083.8: Generate artifacts library page — list with type icon, title, source recipe count, created/updated date; filter bar: type (all / shopping list / meal plan / pantry feasibility), status toggle (active / archived)
- T-083.9: Wire artifacts library — `GET /api/artifacts` → cards → click → `/artifacts/[id]`
- T-083.10: Wire archive — confirm → `POST /api/artifacts/{id}/archive` → navigate to /artifacts

**Acceptance:** Shopping list generation two-step flow works end to end. Generated list editable before and after saving. Artifacts library shows all saved artifacts with type and status filter.

---

---

# SPRINT 11 — Pantry + Meal plan + Create hub

**Goal:** Full Phase 2 feature set complete — pantry, feasibility, meal plans, and Create hub all working.  
**Labels:** `phase-2` `p10-pantry`

---

### T-084 · PantryItem model + repository
**Labels:** `backend`  
**Dependencies:** T-009

Persistent pantry ingredient inventory.

**Subtasks:**
- T-084.1: Create SQLAlchemy model `PantryItem` — id, userId, ingredientId (FK to Ingredient), addedAt
- T-084.2: Add unique constraint: (userId, ingredientId) — no duplicates
- T-084.3: Generate and run Alembic migration
- T-084.4: Create `/repositories/pantry_repo.py` — add_items, remove_items, get_all_by_user, get_ingredient_ids_for_user

**Acceptance:** PantryItem model created. Unique constraint prevents duplicates. Repo functions work.

---

### T-085 · Pantry service
**Labels:** `backend`  
**Dependencies:** T-084, T-029

Pantry CRUD, text matching, and deterministic feasibility matching.

**Subtasks:**
- T-085.1: Create `/services/pantry_service.py`
- T-085.2: Implement `add_pantry_items(ingredient_ids, user_id) -> AddResult` — adds new, returns alreadyInPantry for duplicates
- T-085.3: Implement `add_from_text(text, user_id) -> TextAddResult` — three-tier ingredient search (exact/alias/fuzzy via T-029), add if match found, return suggestions if not
- T-085.4: Implement `remove_pantry_items(pantry_item_ids, user_id)`
- T-085.5: Implement `check_feasibility(user_id, filters, limit) -> FeasibilityResult` — deterministic, no LLM: get pantry ingredient IDs, for each canonical recipe compare ingredient IDs against pantry set
- T-085.6: Feasibility classification: fully feasible (all ingredients in pantry), partially feasible (≥50% in pantry), not feasible (<50%)
- T-085.7: Sort partially feasible by feasibilityScore descending; apply tag/time filters to narrow checked recipes

**Acceptance:** All operations work. Text matching uses fuzzy search. Feasibility matching is deterministic (no LLM).

---

### T-086 · Pantry API endpoints
**Labels:** `backend`  
**Dependencies:** T-085

All five pantry endpoints.

**Subtasks:**
- T-086.1: Create `GET /api/pantry` — all pantry items with ingredient names
- T-086.2: Create `POST /api/pantry` — add by ingredientIds array
- T-086.3: Create `POST /api/pantry/from-text` — add by text, return match or suggestions
- T-086.4: Create `DELETE /api/pantry` — remove by pantryItemIds array
- T-086.5: Create `POST /api/pantry/feasibility` — run feasibility check with optional filters
- T-086.6: Auth dependency on all endpoints
- T-086.7: Integration tests

**Acceptance:** All endpoints work. Matches Phase 2 API contracts section 4.

---

### T-087 · Pantry UI
**Labels:** `frontend`  
**Dependencies:** T-086

`/pantry` and `/pantry/feasibility` routes. **Pantry items can be grouped by `ingredient.category`** (returned from the ingredient search API) for organized display.

**Subtasks:**
- T-087.1: Generate pantry page using v0 — ingredient search/add section (autocomplete + free text), current pantry list with remove buttons, item count, "What can I cook?" CTA
- T-087.2: Wire ingredient search autocomplete — debounced `GET /api/ingredients?search=...` → dropdown shows `name` + `category` badge → select → `POST /api/pantry`
- T-087.3: Wire free text input — `POST /api/pantry/from-text` → handle match/no-match (show suggestions) → add confirmed item
- T-087.4: Wire remove — `DELETE /api/pantry` → optimistic remove with undo toast
- T-087.5: **Group pantry items by `category`** (e.g., "Produce", "Dairy & Eggs", "Spices & Herbs") — use `ingredient.category` from the API response directly. Items without a mapped ingredient default to "Other" section
- T-087.6: Generate pantry feasibility page — three sections (fully feasible / partially feasible / not feasible) with recipe cards and feasibility badges
- T-087.7: Wire feasibility page — `POST /api/pantry/feasibility` → display three-tier results
- T-087.8: Display missing ingredients per recipe in partially feasible section (expandable per recipe card)
- T-087.9: Wire "Make shopping list for missing" — pre-select partially feasible recipes → navigate to `/create/shopping-list/new` with those recipes pre-selected
- T-087.10: Wire "Save this check" → `POST /api/artifacts/generate` (pantry_feasibility type) → navigate to `/artifacts/[id]`

**Acceptance:** Pantry management works. **Items grouped by category in the UI.** Feasibility results display in three tiers. Missing ingredients shown. Save to artifact works.

---

### T-088 · Pantry feasibility badges on recipe library
**Labels:** `backend` `frontend`  
**Dependencies:** T-086, T-037

Show feasibility status on recipe cards when pantry is populated.

**Subtasks:**
- T-088.1: Add optional `pantry=true` query param to `GET /api/recipes` — when true and user has pantry items, run feasibility check alongside recipe list and return `feasibilityStatus` per card
- T-088.2: Return `feasibilityStatus: "fully_feasible" | "partially_feasible" | "not_feasible" | "unknown"` on recipe cards in list response
- T-088.3: Display feasibility badge on recipe cards in library (only visible when pantry has items)
- T-088.4: Add pantry filter toggle to library filter bar: "All" / "Can make now" / "Almost there"

**Acceptance:** Feasibility badges appear on recipe cards. Filter works. Badges only shown when pantry has items.

---

### T-089 · Meal plan generation service
**Labels:** `backend`  
**Dependencies:** T-081, T-068

Generate a structured meal plan from saved recipes using constraints and instructions.

**Subtasks:**
- T-089.1: Implement `generate_meal_plan(instructions, recipe_ids, days, meals_per_day, title, user_id) -> Artifact`
- T-089.2: If recipe_ids null — use hybrid search based on instructions to retrieve relevant recipes
- T-089.3: Hydrate full recipe objects
- T-089.4: LLM call with recipe data + instructions — generate MealPlanContent: days array with dayLabel, meals array with mealSlot (breakfast/lunch/dinner/snack), recipeId, recipeTitle, notes
- T-089.5: Validate generated structure against MealPlanContent Pydantic model
- T-089.6: Persist as Artifact with sourceRecipeIds
- T-089.7: Test: "3-day vegetarian dinner plan", "weeknight dinners under 30 min", specific recipe selection

**Acceptance:** Meal plans generated from instructions or recipe selection. Days and meal slots populated correctly. Saved as Artifact.

---

### T-090 · Meal plan API + artifact handling
**Labels:** `backend`  
**Dependencies:** T-089, T-082

Wire meal plan generation into artifact API, with slot editing support.

**Subtasks:**
- T-090.1: Wire `meal_plan` artifactType into `POST /api/artifacts/generate` router
- T-090.2: Support `PATCH /api/artifacts/{id}` for meal plans — swap recipeId in a slot, add/remove days, edit slot notes
- T-090.3: Content validation on PATCH: meal plan slots must have valid recipeId or null
- T-090.4: Integration test: generate meal plan → edit a slot → verify revision created

**Acceptance:** Meal plan generation works via artifacts endpoint. Slot editing supported. Revisions created on edit.

---

### T-091 · Meal plan UI
**Labels:** `frontend`  
**Dependencies:** T-090

`/create/meal-plan/new` and meal plan view in artifact detail.

**Subtasks:**
- T-091.1: Generate meal plan generator page using v0 — constraint form: number of days slider (default 3), meals per day checkboxes (breakfast/lunch/dinner/snack), optional dietary tag filter, optional max cook time, optional specific recipe include picker, free-text instructions textarea, generate button
- T-091.2: Wire generation — `POST /api/artifacts/generate` (meal_plan) → navigate to `/artifacts/[newId]`
- T-091.3: Implement meal plan view in artifact detail — day cards, meal slot rows (recipe thumbnail + title + cook time), notes
- T-091.4: Wire slot editing — swap recipe opens search modal (`POST /api/search`) → pick recipe → `PATCH /api/artifacts/{id}`
- T-091.5: Wire slot remove and plan notes editing

**Acceptance:** Meal plan generation with all constraint inputs works. Slot editing works end to end.

---

### T-092 · Create hub UI
**Labels:** `frontend`  
**Dependencies:** T-083, T-091, T-087

`/create` landing page.

**Subtasks:**
- T-092.1: Generate Create hub page using v0 — three action cards: Shopping List (→ /create/shopping-list/new), Meal Plan (→ /create/meal-plan/new), What can I cook? (→ /pantry/feasibility)
- T-092.2: Show last 5 generated artifacts below action cards (type icon, title, date) — `GET /api/artifacts?limit=5`
- T-092.3: "View all" link → /artifacts
- T-092.4: Empty artifacts state — show creation options only with "Create your first..." prompt

**Acceptance:** Create hub renders three options. Recent artifacts shown. Navigation correct.

---

### T-093 · Artifacts library UI
**Labels:** `frontend`  
**Dependencies:** T-082

`/artifacts` — full library of saved artifacts.

**Subtasks:**
- T-093.1: Generate artifacts library page using v0 — list with type icon, title, source recipe count, created/updated date
- T-093.2: Wire list — `GET /api/artifacts` → render cards → click → `/artifacts/[id]`
- T-093.3: Filter bar: type filter (all / shopping list / meal plan / pantry feasibility) + status toggle (active / archived)
- T-093.4: Wire status toggle — active shows non-archived, archived shows archived artifacts
- T-093.5: Empty state: "No saved artifacts yet" with CTA → /create

**Acceptance:** Artifacts library shows all saved artifacts. Type and status (active/archived) filters work.

---

---

# SPRINT 12 — Phase 2 polish + deploy

**Goal:** Phase 2 is live on production. All features verified end to end.  
**Labels:** `phase-2` `p11-deploy2`

---

### T-094 · Phase 2 navigation updates
**Labels:** `frontend`  
**Dependencies:** T-070, T-077, T-092, T-087

Add Phase 2 surfaces to the primary nav.

**Subtasks:**
- T-094.1: Update primary nav: Recipes, Ingest, Search, Ask, Create, Pantry
- T-094.2: Update mobile nav (bottom bar or drawer) with Phase 2 items
- T-094.3: Add active state indicators per nav item
- T-094.4: Ensure root redirect (`/`) → `/recipes` remains correct
- T-094.5: Verify all Phase 2 route stubs registered in Next.js App Router

**Acceptance:** All Phase 2 routes accessible from nav. Active states correct.

---

### T-095 · Admin + debug endpoints
**Labels:** `backend`  
**Dependencies:** T-064, T-066, T-043

Admin endpoints for journal summary and embedding management.

**Subtasks:**
- T-095.1: Create `POST /api/recipes/{recipeId}/regenerate-journal-summary` — enqueues journal_summary_worker job, returns 202 Accepted
- T-095.2: Create `POST /api/admin/recipes/{recipeId}/regenerate-embedding` — enqueues index_recipe job for single recipe (admin-protected)
- T-095.3: Confirm `POST /api/admin/embeddings/backfill` from T-066 is properly documented and protected
- T-095.4: Admin protection: check Clerk userId against ADMIN_USER_IDS env var on all `/api/admin/*` routes
- T-095.5: Verify all three endpoints return correct responses and trigger correct workers

**Acceptance:** All three admin/debug endpoints work. Admin protection in place. Matches Phase 2 API contracts admin section.

---

### T-096 · Phase 2 error handling + observability
**Labels:** `backend` `frontend` `infrastructure`  
**Dependencies:** T-050

Extend error handling and logging to Phase 2 services.

**Subtasks:**
- T-096.1: Add structured logging to: search_service, ask_service, artifact_service, pantry_service, embedding_service, qdrant_client_service — log operation, result count/status, duration
- T-096.2: User-friendly error messages for Phase 2 conditions: Qdrant unavailable, embedding rate limited, Ask session closed, artifact generation failed
- T-096.3: Add Sentry error tracking to all Phase 2 services
- T-096.4: Add Phase 2 routes to frontend error boundary coverage
- T-096.5: Verify graceful Qdrant degradation (from T-068) works in staging environment

**Acceptance:** Phase 2 services emit structured logs. Sentry captures Phase 2 errors. Graceful Qdrant fallback verified.

---

### T-097 · Deployment — Phase 2
**Labels:** `infrastructure`  
**Dependencies:** T-059, T-066, T-094, T-095, T-096

Deploy Phase 2 to production.

**Subtasks:**
- T-097.1: Add Qdrant to Railway production (Qdrant Cloud recommended for managed hosting)
- T-097.2: Add Phase 2 env vars to Railway and Vercel: `QDRANT_URL`, `QDRANT_API_KEY`
- T-097.3: Run Alembic migrations: AskSession, AskMessage, Artifact, ArtifactRevision, PantryItem, RecipeSearchIndexStatus tables
- T-097.4: Create `kama_recipes` Qdrant collection on production instance (run T-059 setup script against production)
- T-097.5: Run embedding backfill — index all existing Phase 1 canonical recipes
- T-097.6: Smoke test Phase 2 features end to end: search a recipe → ask a question → generate shopping list → add pantry items → check feasibility → generate meal plan
- T-097.7: Monitor search latency and Qdrant response times for 24 hours post-deploy

**Acceptance:** Phase 2 live on production. All canonical recipes indexed. All Phase 2 features verified end to end. No Phase 1 regressions.

---

---

# Complete task index

## Phase 1 — Sprints 1–6

| ID | Task | Sprint | Labels |
|---|---|---|---|
| T-001 | Initialize monorepo | 1 | infrastructure |
| T-002 | Set up /packages/contracts | 1 | infrastructure |
| T-003 | Set up /packages/api-client | 1 | infrastructure |
| T-004 | Set up /packages/shared | 1 | infrastructure |
| T-005 | Set up /packages/ui | 1 | infrastructure, design |
| T-006 | Set up Next.js web app | 1 | frontend, infrastructure |
| T-007 | Set up FastAPI backend | 1 | backend, infrastructure |
| T-008 | Docker Compose + Dockerfile | 1 | infrastructure |
| T-009 | Database migrations — core tables | 1 | backend |
| T-010 | S3 presigned URL endpoint | 1 | backend |
| T-011 | Background worker execution (`background_runner` + Redis SSE) | 1 | backend, infrastructure |
| T-012 | PydanticAI integration | 1 | backend |
| T-013 | SSE endpoint | 1 | backend |
| T-014 | Core ingestion API endpoints | 1 | backend |
| T-055 | Testing infrastructure | 1 | infrastructure |
| T-015 | Ingestion agent — core loop | 2 | backend |
| T-016 | Normalized artifact persistence | 2 | backend |
| T-017 | Circuit breaker infrastructure | 2 | backend |
| T-018 | classify_source tool | 2 | backend |
| T-019 | httpx_fetch tool | 2 | backend |
| T-020 | check_schema_markup tool | 2 | backend |
| T-021 | schema_recipe_extract tool | 2 | backend |
| T-022 | extract_recipe_links tool | 2 | backend |
| T-023 | assess_parseability tool | 2 | backend |
| T-024 | llm_structured_extract tool | 2 | backend |
| T-025 | evaluate_candidate tool | 2 | backend |
| T-026 | RecipeCandidate persistence | 2 | backend |
| T-027 | End-to-end webpage ingestion test | 2 | backend |
| T-045 | Design pipeline — visual system | 2 | design, frontend |
| T-046 | v0 screen generation | 2 | design, frontend |
| T-056 | CI/CD — GitHub Actions | 2 | infrastructure |
| T-098 | extract_page_text tool | 2 | backend |
| T-028 | Review agent implementation | 3 | backend |
| T-029 | Ingredient DB setup and seeding | 3 | backend |
| T-030 | Candidate review decision API | 3 | backend |
| T-031 | Tag system | 3 | backend |
| T-047 | Frontend wiring — ingestion flow | 3 | frontend |
| T-052 | Recipe delete endpoint | 3 | backend, frontend |
| T-054 | Ingredient alias accumulation | 3 | backend |
| T-099 | Media materialization on ingestion save | 3 | backend |
| T-032 | Text ingestion tools | 4 | backend |
| T-033 | OCR tools — Google Cloud Vision | 4 | backend |
| T-048 | Frontend wiring — recipe management | 4 | frontend |
| T-053 | Draft delete endpoint | 4 | backend, frontend |
| T-057 | Rate limiting | 4 | backend, infrastructure |
| T-034 | YouTube ingestion tools | 5 | backend |
| T-035 | Social media ingestion tools | 5 | backend |
| T-036 | Video processing tools | 5 | backend |
| T-037 | Recipe list API | 5 | backend |
| T-038 | Recipe detail API | 5 | backend |
| T-039 | Recipe edit API | 5 | backend |
| T-040 | Revision history + restore API | 5 | backend |
| T-041 | Recipe media API | 5 | backend |
| T-042 | Cook journal API | 5 | backend |
| T-043 | Journal summary generation | 5 | backend |
| T-044 | Draft APIs | 5 | backend |
| T-049 | Frontend wiring — drafts | 5 | frontend |
| T-050 | Error handling + observability | 6 | backend, frontend, infrastructure |
| T-051 | Deployment — Phase 1 | 6 | infrastructure |
| T-058 | Image thumbnailing + optimization | 6 | backend, infrastructure |

## Phase 2 — Sprints 7–12

| ID | Task | Sprint | Labels |
|---|---|---|---|
| T-059 | Qdrant setup + collection configuration | 7 | infrastructure |
| T-060 | RecipeSearchIndexStatus model + migration | 7 | backend |
| T-061 | Embedding service — dense vectors | 7 | backend |
| T-062 | BM25 sparse vector generation | 7 | backend |
| T-063 | Qdrant client service | 7 | backend |
| T-064 | Search index worker | 7 | backend |
| T-065 | Staleness triggers | 7 | backend |
| T-066 | Backfill job for existing recipes | 7 | backend |
| T-067 | Query parser service | 8 | backend |
| T-068 | Hybrid search service | 8 | backend |
| T-069 | Search API endpoint | 8 | backend |
| T-070 | Search UI | 8 | frontend |
| T-071 | Search integration in recipe library | 8 | backend, frontend |
| T-072 | AskSession model + repository | 9 | backend |
| T-073 | Ask retrieval service | 9 | backend |
| T-074 | Ask generation service | 9 | backend |
| T-075 | Ask API endpoints | 9 | backend |
| T-076 | Session timeout + cleanup worker | 9 | backend |
| T-077 | Ask UI | 9 | frontend |
| T-078 | Recipe-scoped Ask — chef persona | 9 | backend, frontend |
| T-100 | Search/Ask intent routing | 9 | frontend |
| T-079 | Artifact model + repository | 10 | backend |
| T-080 | Artifact revision handling | 10 | backend |
| T-081 | Shopping list generation service | 10 | backend |
| T-082 | Shopping list + artifact API endpoints | 10 | backend |
| T-083 | Shopping list UI + Artifacts library | 10 | frontend |
| T-084 | PantryItem model + repository | 11 | backend |
| T-085 | Pantry service | 11 | backend |
| T-086 | Pantry API endpoints | 11 | backend |
| T-087 | Pantry UI | 11 | frontend |
| T-088 | Pantry feasibility badges on recipe library | 11 | backend, frontend |
| T-089 | Meal plan generation service | 11 | backend |
| T-090 | Meal plan API + artifact handling | 11 | backend |
| T-091 | Meal plan UI | 11 | frontend |
| T-092 | Create hub UI | 11 | frontend |
| T-093 | Artifacts library UI | 11 | frontend |
| T-094 | Phase 2 navigation updates | 12 | frontend |
| T-095 | Admin + debug endpoints | 12 | backend |
| T-096 | Phase 2 error handling + observability | 12 | backend, frontend, infrastructure |
| T-097 | Deployment — Phase 2 | 12 | infrastructure |

---

**Total: 100 tasks · 12 sprints · Phase 1: 61 tasks · Phase 2: 39 tasks**
