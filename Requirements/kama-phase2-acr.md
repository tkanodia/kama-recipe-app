# Kama — Phase 2 Technical ACR

**Version:** 1.0  
**Last updated:** May 2026  
**Owner:** Principal Engineer

---

## 1.0 Alignment with Phase 1 — background execution (May 2026)

Phase 2 async work (**embedding regeneration**, **Qdrant upserts**) follows the same pattern as Phase 1: **`background_runner.enqueue`** from the Phase 1 stack (see **Phase 1 ACR §1.0**). **Redis** remains used where Phase 1 uses it (e.g. **SSE**). **Dramatiq + Redis as a broker** is **not** in the current codebase but remains a documented **revisit** for dedicated worker fleets.

---

## 1. Phase 2 technical overview

Phase 2 adds retrieval, querying, and generation capabilities on top of the Phase 1 recipe corpus. The technical foundation is a hybrid retrieval layer combining structured Postgres queries with vector semantic search via pgvector.

Phase 2 introduces four new domain concerns:

- **Retrieval and embedding** — Vector search + metadata filters
- **Ask sessions** — Grounded Q&A with short session memory
- **Artifacts** — Persistent, editable generated outputs (shopping lists, meal plans)
- **Pantry** — Persistent ingredient inventory for feasibility matching

---

## 2. Phase 2 technology additions

| Layer | Choice | Rationale |
|---|---|---|
| Vector search | pgvector (already in Postgres) | No separate vector DB needed, co-located with recipe data |
| Embedding model | OpenAI `text-embedding-3-small` (1536 dimensions) | Good quality/cost ratio, upgrade to `-large` if quality insufficient |
| RAG orchestration | Custom service layer with PydanticAI tool-augmented pattern | Fixed flow with optional search refinement tool; not a full autonomous agent |
| LLM for Ask/Create | Claude Sonnet (same PydanticAI abstraction as Phase 1) | Grounded answer generation and artifact creation |
| LLM for journalSummary | Claude Sonnet (or Haiku for cost) | Summarization task, can use cheaper model |

No new infrastructure services are required beyond Phase 1. Phase 2 uses the existing **Postgres, Redis, S3, FastAPI** stack; async indexing uses the same **in-process `background_runner`** pattern as Phase 1 (see Phase 1 ACR **§1.0**). **Revisit:** add **Dramatiq** (or similar) + Redis broker if worker processes are split out for scale.

---

## 3. Phase 2 domain model

### 3.1 RecipeSearchIndex (Qdrant)

Each canonical recipe is represented as a point in Qdrant with both dense and sparse vectors plus filterable payload metadata.

**Qdrant point structure per recipe:**

```typescript
type RecipeSearchPoint = {
  // Qdrant point ID = canonical recipe ID
  id: string;

  // Dense vector — semantic meaning
  denseVector: number[];             // 1536 dimensions (text-embedding-3-small)

  // Sparse vector — BM25 keyword matching
  sparseVector: {
    indices: number[];               // Token indices
    values: number[];                // BM25 weights
  };

  // Payload — structured metadata for filtering (not full recipe data)
  payload: {
    recipeId: string;
    userId: string;
    tagIds: string[];
    ingredientIds: string[];
    prepTimeMinutes: number | null;
    cookTimeMinutes: number | null;
    servings: number | null;
    createdAt: string;
    updatedAt: string;
  };
};
```

**Application-side tracking model (Postgres):**

```typescript
type RecipeSearchIndexStatus = {
  id: string;
  canonicalRecipeId: string;
  sourceText: string;                // The text that was embedded (for debugging/regeneration)
  embeddingModel: string;            // e.g. "text-embedding-3-small"
  indexedAt: string;                 // When last successfully indexed to Qdrant
  stale: boolean;                    // True when recipe/journal changes since last index
  staleReason?: string | null;       // What triggered staleness
  staleSince?: string | null;
};
```

This Postgres record tracks indexing status. The actual vectors live in Qdrant, not in Postgres.

**Source text composition (used for both dense and sparse vectors):**

```
{title}. {description}. Ingredients: {ingredient names joined}. Tags: {tag names joined}. {journalSummary}
```

Both the dense embedding (OpenAI) and the sparse BM25 vector are generated from the same source text. This ensures the dense vector captures semantic meaning ("comfort food," "kid-friendly") while the sparse vector captures exact terms ("paneer," "chickpeas," "fusilli").

**Indexing triggers:**
- Recipe created (title, ingredients, steps saved)
- Recipe content edited (title, description, ingredients)
- journalSummary updated
- Recipe tags changed

**Staleness model:** When a trigger fires, the Postgres tracking record is marked `stale: true`. A **background task** (`search_index_worker` via `enqueue`) regenerates both vectors and upserts the point to Qdrant. During regeneration, the existing Qdrant point is still searchable — slightly outdated results are better than missing results.

**Deletion:** When a canonical recipe is deleted, its Qdrant point is deleted and the Postgres tracking record is removed.

### 3.2 AskSession

Short-lived conversational context for the Ask surface.

```typescript
type AskSession = {
  id: string;
  userId: string;
  status: "active" | "closed";
  messages: AskMessage[];
  retrievedRecipeIds: string[];      // Accumulated across the session
  createdAt: string;
  lastActiveAt: string;
  closedAt?: string | null;
};

type AskMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  retrievedRecipeIds?: string[];     // Recipes used for this specific answer
  citedRecipeIds?: string[];         // Recipes explicitly cited in the answer
  createdAt: string;
};
```

**Session lifecycle:**
- Created when user asks the first question
- Subsequent messages in the same session include prior messages as context
- Session closes after inactivity timeout (e.g. 15 minutes) or when user explicitly starts a new question
- Closed sessions are not reactivatable
- Sessions are not persisted long-term — retained for a short period (e.g. 7 days) then cleaned up

**Context window management:** The full message history is sent to the LLM for each follow-up. For long sessions, older messages may be summarized or truncated to stay within context limits. Phase 2 keeps this simple — short sessions with 5–10 exchanges are the expected pattern.

### 3.3 Artifact

First-class persistent output from Create flows. Editable, versioned, source-linked.

```typescript
type Artifact = {
  id: string;
  userId: string;
  artifactType: "shopping_list" | "meal_plan" | "pantry_feasibility";
  title: string;
  content: ArtifactContent;          // Type-specific payload
  sourceRecipeIds: string[];         // Recipes that produced this artifact
  status: "active" | "archived";
  createdAt: string;
  updatedAt: string;
};
```

#### Shopping list content

Sections are grouped by `ingredient.category` deterministically for mapped ingredients. LLM-based category inference is a fallback for unmapped ingredients only.

```typescript
type ShoppingListContent = {
  type: "shopping_list";
  sections: Array<{
    category: string;               // Display name derived from IngredientCategory (e.g. "Produce", "Dairy & Eggs", "Meat & Seafood")
    items: Array<{
      text: string;                 // Display text: "2 cups cherry tomatoes"
      ingredientId?: string | null;
      quantity?: string | null;
      unit?: string | null;
      sourceRecipeIds: string[];    // Which recipes need this item
      checked: boolean;
    }>;
  }>;
};
```

#### Meal plan content

```typescript
type MealPlanContent = {
  type: "meal_plan";
  days: Array<{
    date?: string | null;           // Optional specific date
    dayLabel: string;               // "Day 1", "Monday", etc.
    meals: Array<{
      mealSlot: "breakfast" | "lunch" | "dinner" | "snack";
      recipeId?: string | null;     // Linked canonical recipe
      recipeTitle: string;
      notes?: string | null;
    }>;
  }>;
  planNotes?: string | null;
};
```

#### Pantry feasibility content

```typescript
type PantryFeasibilityContent = {
  type: "pantry_feasibility";
  fullyFeasible: Array<{
    recipeId: string;
    recipeTitle: string;
    matchedIngredients: string[];   // Ingredient IDs
  }>;
  partiallyFeasible: Array<{
    recipeId: string;
    recipeTitle: string;
    matchedIngredients: string[];
    missingIngredients: Array<{
      ingredientId: string;
      ingredientName: string;
      category: IngredientCategory;  // Inherited from Ingredient record
    }>;
    feasibilityScore: number;       // 0-1, proportion of ingredients available
  }>;
  notFeasible: Array<{
    recipeId: string;
    recipeTitle: string;
    missingCount: number;
  }>;
  generatedAt: string;
};
```

**Artifact revision model:** Artifacts support revision history using the same pattern as recipes — meaningful content edits create a revision snapshot. The `ArtifactRevision` object mirrors `RecipeRevision`:

```typescript
type ArtifactRevision = {
  id: string;
  artifactId: string;
  snapshotPayload: object;
  changeSummary?: string | null;
  createdAt: string;
};
```

### 3.4 PantryItem

Persistent ingredient inventory maintained by the user.

```typescript
type PantryItem = {
  id: string;
  userId: string;
  ingredientId: string;             // Links to Ingredient source DB
  addedAt: string;
  // category is inherited from the linked Ingredient record at read time (not stored on PantryItem)
};
```

**Design choice:** PantryItem stores only ingredient identity, not quantity. This is a "what do I have" list, not a full inventory system. Quantity tracking is deferred. The `category` field is inherited from the linked `Ingredient` record and included in API responses for UI grouping — it is not duplicated on the PantryItem row itself.

---

## 4. Retrieval architecture

### 4.1 Hybrid search strategy

Phase 2 uses **dense + sparse hybrid search with RRF fusion in Qdrant**, complemented by Qdrant's native payload filtering for structured constraints.

Every search and Ask query is executed as a single Qdrant hybrid query that combines three mechanisms:

**Dense vector search (semantic).** The user's query is embedded via OpenAI text-embedding-3-small. Qdrant compares this against stored dense recipe vectors. This catches meaning-based matches — "comfort food for a cold day" finds hearty stews even if those words don't appear in the recipe.

**Sparse vector search (BM25 lexical).** The user's query is converted to a BM25 sparse vector. Qdrant compares this against stored sparse recipe vectors. This catches exact keyword matches — "paneer" finds recipes containing the word "paneer" even if the dense embedding doesn't strongly associate it.

**Payload filtering (structured constraints).** Tag IDs, ingredient IDs, cook time, prep time, and servings are stored as Qdrant payload metadata. Filters are applied before or during vector search to narrow the candidate set. This handles precise factual constraints without relying on embeddings.

**Reciprocal Rank Fusion (RRF)** merges the dense and sparse ranked lists into a single result set server-side within Qdrant. No custom reranker or post-processing is needed. The fused ranking naturally promotes recipes that score well on both semantic meaning and keyword relevance.

### 4.2 Search flow (single Qdrant call)

```
User query: "quick vegetarian pasta with paneer"
                    │
                    ▼
        ┌─ LLM-assisted query parsing ─┐
        │                               │
        │  Structured filters:          │
        │    tagIds: [tag_vegetarian]    │
        │    maxCookTimeMinutes: 30     │
        │                               │
        │  Semantic query text:          │
        │    "quick pasta with paneer"   │
        └───────────────────────────────┘
                    │
          ┌────────┴────────┐
          ▼                 ▼
   OpenAI embed       BM25 sparse
   (1536d dense)      vector gen
          │                 │
          └────────┬────────┘
                   ▼
        ┌─ Single Qdrant query ─────────┐
        │                               │
        │  1. Payload filter:           │
        │     tagIds contains            │
        │       "tag_vegetarian"         │
        │     cookTimeMinutes <= 30     │
        │                               │
        │  2. Dense vector search       │
        │  3. Sparse vector search      │
        │  4. RRF fusion                │
        │                               │
        │  → Fused ranked recipe IDs    │
        └───────────────────────────────┘
                   │
                   ▼
        Hydrate full recipes from Postgres
```

The key property: one outbound call to Qdrant returns the final ranked result set. No multi-stage orchestration, no separate dense-then-sparse pipelines, no post-search reranking service.

### 4.3 Why dense + sparse together

Dense embeddings alone have a known weakness: they can miss exact keyword matches. If a user searches for "paneer" and only one recipe contains paneer, a purely dense search might rank a recipe about "Indian cottage cheese curry" higher because the embeddings are semantically close — even though the user typed the exact word.

Sparse BM25 vectors solve this directly. "Paneer" in the query matches "paneer" in the recipe's source text with high BM25 weight. RRF fusion ensures this exact-match recipe rises to the top while still ranking semantically similar results nearby.

The reverse is also true: BM25 alone would miss "recipes where I had good results" because that query has no keyword overlap with recipe content. The dense embedding handles this by matching against journalSummary content about success and remaking.

Together they cover both query types cleanly.

### 4.4 Query parsing

User queries are decomposed into structured filters + semantic query text via LLM-assisted parsing. This is the same approach as previously defined:

```typescript
type ParsedQuery = {
  structuredFilters: {
    tagIds?: string[];
    ingredientIds?: string[];
    maxCookTimeMinutes?: number;
    maxPrepTimeMinutes?: number;
    minServings?: number;
    maxServings?: number;
  };
  semanticQuery: string;
  queryIntent: "search" | "ask" | "ambiguous";
};
```

**Structured filters** become Qdrant payload filters. **Semantic query** becomes the input for both dense embedding and BM25 sparse vector generation. Both are sent in one Qdrant query.

### 4.5 Indexing pipeline

When a canonical recipe is created or updated:

1. Compose source text from recipe fields + journalSummary
2. Call OpenAI text-embedding-3-small → dense vector (1536d)
3. Generate BM25 sparse vector from the same source text (via Qdrant's built-in sparse encoding or a Python BM25 library)
4. Upsert to Qdrant: point ID = recipe ID, dense vector, sparse vector, payload metadata (tag IDs, ingredient IDs, times, servings)
5. Update Postgres tracking record: `stale: false`, `indexedAt: now`

This runs as an **async background task** (`enqueue`) triggered by recipe/journal changes.

### 4.6 Ask retrieval + generation

The Ask flow uses the same hybrid retrieval, then feeds results to the LLM:

1. Parse query (LLM-assisted decomposition)
2. Hybrid search in Qdrant → top-N recipe IDs
3. Hydrate full recipe data from Postgres (content + journalSummary)
4. Construct LLM prompt: user question + session history (if follow-up) + retrieved recipe content
5. LLM generates grounded answer citing specific recipes
6. Return answer + cited recipe IDs

For follow-up questions, the session history provides conversational context. Retrieval may use the follow-up question combined with prior context to improve result quality.

### 4.7 Create generation

Create flows use retrieval or user selection, then generate structured artifacts:

1. Determine relevant recipes (user-selected, or retrieved via hybrid search)
2. Hydrate full recipe data from Postgres
3. Construct LLM prompt with recipe data + generation instructions
4. LLM generates structured output (shopping list JSON, meal plan JSON)
5. Parse and validate the generated structure
6. Persist as Artifact

Pantry feasibility is deterministic (no vectors, no LLM):

1. Fetch user's pantry ingredient IDs from Postgres
2. For each canonical recipe, compare recipe ingredient IDs against pantry set
3. Classify as fully / partially / not feasible
4. Rank partially feasible by feasibility score

---

## 5. Backend ownership — Phase 2 additions

### `/backend/app/services` (new)

`search_service` — Hybrid retrieval orchestration: query parsing → dense + sparse vector generation → single Qdrant hybrid query → Postgres hydration.

`query_parser_service` — LLM-assisted query decomposition into structured filters + semantic query.

`embedding_service` — Dense embedding generation via OpenAI API + BM25 sparse vector generation. Handles indexing and re-indexing to Qdrant.

`qdrant_client_service` — Qdrant connection management, point upsert, hybrid search queries, point deletion.

`ask_service` — Ask session management, retrieval + LLM answer generation.

`artifact_service` — Artifact creation, editing, revision management.

`pantry_service` — Pantry CRUD, feasibility matching against recipe ingredients.

### `/backend/app/repositories` (new)

`recipe_search_index_repo` — Postgres tracking records for indexing status (staleness, last indexed, source text).

`ask_session_repo` — Session persistence and cleanup.

`artifact_repo` — Artifact CRUD and revision storage.

`pantry_repo` — Pantry item CRUD.

### `/backend/app/workers` (new)

`search_index_worker` — Async dense + sparse vector generation and Qdrant upsert on recipe/journal changes.

### `/backend/app/domain` (additions)

Artifact type definitions, pantry feasibility logic, query parsing types, Qdrant collection configuration, BM25 sparse encoding config.

### `/backend/app/schemas` (additions)

Pydantic models for: RecipeSearchIndexStatus, RecipeSearchPoint, AskSession, AskMessage, Artifact, ArtifactContent (shopping list, meal plan, pantry feasibility), ArtifactRevision, PantryItem, ParsedQuery.

---

## 6. Phase 2 key architectural decisions

| Decision | Choice | Rationale |
|---|---|---|
| Embedding strategy | One embedding per recipe + structured metadata filters | Balanced precision and simplicity; structured filters handle precise constraints |
| Embedding model | OpenAI text-embedding-3-small (1536d) | Good quality/cost ratio; upgrade to -large if insufficient |
| Vector storage | pgvector in Postgres | Co-located with recipe data, no separate vector DB |
| Query parsing | LLM-assisted decomposition | Handles natural language variations; minimal cost per query |
| Ask model | Short session memory, not persistent chat | Follow-ups within session; no long-term chat history |
| Ask grounding | Canonical recipes + metadata + journalSummary only | No drafts, no open-web knowledge |
| Create artifacts | Saved, editable, versioned, source-linked | First-class domain objects, not throwaway outputs |
| Pantry | Persistent user-maintained ingredient list | Ingredient identity only, no quantities |
| Pantry feasibility | Deterministic ingredient ID matching | No LLM needed; direct set comparison |
| Embedding staleness | Mark stale + async regenerate | Stale embedding still searchable; no downtime during regeneration |
| journalSummary generation | Full regeneration from all entries, async | Simple correctness; optimize to incremental later |
| Session cleanup | Time-based retention (e.g. 7 days) | Sessions are short-lived, not permanent records |

---

## 7. Phase 2 implementation priorities

### Priority 1 — Qdrant setup + indexing pipeline
- Qdrant container deployment on Railway
- Qdrant collection creation with dense (1536d) and sparse vector configuration
- Payload schema definition (recipe ID, user ID, tag IDs, ingredient IDs, times, servings)
- OpenAI embedding integration (text-embedding-3-small)
- BM25 sparse vector generation for source text
- RecipeSearchIndexStatus model in Postgres (staleness tracking)
- Qdrant client service for upsert, search, and delete operations
- `search_index_worker` — Async dense + sparse vector generation and Qdrant upsert on recipe/journal changes (`enqueue`; **revisit** Dramatiq actor if using a broker)
- Staleness marking on recipe edit, journalSummary update, and tag change
- Backfill job: generate dense + sparse vectors and index all existing canonical recipes

### Priority 2 — Search
- Query parser service (LLM-assisted decomposition into structured filters + semantic query)
- Dense query embedding generation (OpenAI text-embedding-3-small)
- Sparse BM25 query vector generation
- Single Qdrant hybrid query: payload filters + dense search + sparse search + RRF fusion
- Result hydration from Postgres (recipe IDs → full recipe objects)
- Search API endpoint with parsed query transparency and match reasons
- Search UI in recipe library

### Priority 3 — Ask
- AskSession model and persistence
- Ask retrieval flow (query → retrieve recipes → construct prompt)
- LLM grounded answer generation with recipe citations
- Session follow-up handling (message history as context)
- Session timeout and cleanup
- Ask API endpoints (create session, send message, close session)
- Ask UI surface

### Priority 4 — Create: Shopping list
- Artifact model and persistence
- Shopping list generation (recipe selection → ingredient aggregation → **deterministic grouping by `ingredient.category`**)
- Mapped ingredients are placed into their DB-assigned category section (Produce, Meat & Seafood, Dairy, etc.) with no LLM call
- **LLM-based category inference used only as fallback** for unmapped ingredients (those without an `ingredientId`)
- Ingredient deduplication via ingredient IDs
- Source recipe linkage per shopping list item
- Shopping list editing (check items, add/remove items, edit quantities)
- Artifact revision on edit
- Shopping list API endpoints
- Shopping list UI

### Priority 5 — Pantry + feasibility
- PantryItem model and persistence
- Pantry items inherit `category` from the linked Ingredient record
- Pantry CRUD API — `GET /api/pantry` response includes `category` per item
- Pantry UI (add/remove ingredients, search ingredient DB) — **list grouped by ingredient category** with section headers and per-category counts
- Feasibility matching service (deterministic ingredient ID comparison)
- Feasibility classification (fully/partially/not feasible)
- Missing ingredients display per recipe — includes `category` field
- Pantry feasibility API endpoint — `POST /api/pantry/feasibility` missing ingredients include `category`
- Integration with recipe library (feasibility badges/filter)

### Priority 6 — Create: Meal plan
- Meal plan generation (constraints → recipe selection → LLM plan construction)
- Meal plan artifact with day/meal slot structure
- Recipe-to-slot linkage
- Meal plan editing (swap recipes, adjust days, add notes)
- Artifact revision on edit
- Meal plan API endpoints
- Meal plan UI

---

## 8. Phase 2 deferred technical decisions

| Topic | Status |
|---|---|
| Embedding model upgrade (text-embedding-3-large) | Upgrade if search quality proves insufficient |
| Cohere reranker in production | Explore in notebooks; add only if RRF fusion quality is insufficient |
| Incremental journalSummary updates | Optimize from full regeneration when cost/latency warrants |
| Multi-vector per recipe (field-level dense embeddings) | Add only if single dense + sparse + filters proves too weak |
| Ask session persistence beyond 7 days | Defer unless user research shows demand |
| Streaming LLM responses for Ask | Add if UX feels slow; initial implementation returns complete answers |
| Pantry quantity tracking | Defer — ingredient identity only in Phase 2 |
| Pantry expiry dates | Defer |
| Artifact sharing / collaboration | Defer |
| Artifact templates (reusable meal plan structures) | Defer |
| Complex nutrition-aware planning | Defer |
| pgvector as fallback search | Qdrant is primary; pgvector available in Postgres but not used for search in Phase 2 |
| Qdrant replicas / sharding | Not needed at personal-use scale; revisit if multi-user |
