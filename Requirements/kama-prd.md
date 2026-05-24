# Kama — Product Requirements Document

**Version:** 1.0  
**Last updated:** March 2026  
**Owners:** Product Lead + Principal Engineer

---

## 1. Product thesis

Kama is an AI recipe workspace that converts messy cooking content from any source into structured, trustworthy recipe knowledge. Users can ingest recipes from URLs, images, handwritten notes, and text, then build a personal recipe library they can search, annotate, and plan from.

**Core promise:** Bring in recipes from anywhere. Kama turns them into reliable structured knowledge you can search, compare, and build plans from.

**What makes Kama different:** The product treats extraction quality, source provenance, and user trust as first-class concerns — not afterthoughts. Every recipe preserves where it came from and how confident the system is, so the user always knows what they can rely on.

---

## 2. Phase structure

### Phase 1 — Recipe ingestion, extraction, and management
Build the foundation: ingest recipes from multiple source types, extract structured data, let users review and save, and provide a recipe library with cook journal and tagging.

### Phase 2 — Intelligence on top of recipes
Build user-facing intelligence: search, retrieval-augmented generation (RAG), ask/create flows (meal planning, shopping lists, pantry-aware suggestions, recipe comparison).

This document focuses primarily on Phase 1 with enough Phase 2 context to ensure architectural decisions serve both.

---

## 3. Phase 1 product scope

### 3.1 Product surfaces

Phase 1 delivers four connected surfaces:

**Ingestion** — Submit a source (URL, image, or text), watch it process, review the extracted recipe, and save it as a trusted recipe or draft.

**Recipe library** — Browse, filter, and manage saved recipes. Drafts appear in the same library with clear labels and filter support.

**Recipe detail** — View a saved recipe with hero image, gallery, structured content, and the cook journal below. Version history is accessible from an overflow menu.

**Cook journal** — A timestamped feed of cooking notes, images, and tags below each recipe. Think of it as comments on a recipe post.

### 3.2 Ingestion

#### Supported source types
Users can submit three broad input types. The system classifies and routes them internally.

| Input type | User action | System classification |
|---|---|---|
| URL | Paste any link | Recipe webpage, YouTube video, Instagram reel/post, TikTok video, Facebook video/post, generic page |
| Image | Upload photo | Printed recipe, handwritten recipe, screenshot, cookbook page |
| Text | Paste content | Structured recipe text, freeform notes, mixed content |

#### Source confidence levels (Phase 1)

**Strongest support (high confidence):** Direct recipe webpages and clean pasted recipe text. These are the most reliable extraction paths.

**Strong support (medium-high confidence):** YouTube videos (via linked recipe pages, then transcript fallback) and Instagram/TikTok/Facebook posts where caption contains a recipe link or full recipe text.

**Supported (medium confidence):** Handwritten recipe images (assisted digitization with heavier review). Social media videos where recipe content is spoken or shown as text overlays (extracted via audio transcription and video frame analysis).

**Honest limitations:** Private/login-gated social media content is not accessible. Recipes that exist only in carousel image slides (without caption text or video) are not extractable in Phase 1. Video-extracted recipes will always require heavier review.

#### Social media ingestion strategy

Social media recipe extraction is a core Phase 1 capability, not a deferred feature. Kama uses platform-specific strategies:

**Acquisition:** yt-dlp extracts metadata, captions, and video content from Instagram, TikTok, and Facebook public posts. YouTube uses the YouTube Data API and youtube-transcript-api separately.

**Extraction priority:** For all social platforms, the system prefers written recipe sources over video processing. The agent tries progressively more expensive paths only when cheaper ones don't yield results.

The fallback ladder for social sources:

1. Scan caption for linked recipe page → follow link, use webpage extraction
2. Resolve creator profile bio links → find recipe blog or website
3. Search creator's website for matching recipe using video title/caption keywords
4. Extract recipe directly from caption text
5. Download video, transcribe audio via Whisper, extract frame text via multimodal LLM
6. Merge audio + visual text and run structured extraction

**Creator bio link resolution** (steps 2–3) is a key differentiator. Many social media recipe creators post short videos with minimal captions like "comment RECIPE" or "link in bio," while maintaining a full recipe blog linked from their profile. Kama's agent resolves the creator's profile, expands linktree or bio aggregator URLs, categorizes discovered links by recipe relevance, and follows the most promising path to the written recipe. This avoids expensive video processing for the majority of social recipe content.

**Design rule:** The agent does not blindly crawl everything in a creator's linktree. It categorizes links (recipe blog, shop, social profile, etc.) and only follows recipe-relevant ones. The agent uses LLM reasoning when link categorization is ambiguous.

**Video processing:** When caption-based methods are insufficient, the system downloads the video, extracts audio transcription (OpenAI Whisper) and key frame text (multimodal LLM) in parallel, then merges results for structured extraction. This path takes 30–60 seconds and always uses `reconstruction` review mode.

**Trust messaging:** The review screen should clearly communicate which extraction path was used. "Recipe extracted from video audio and visual text" sets different user expectations than "Recipe extracted from linked blog page."

#### Trust model — two-tier flow

Every ingestion follows the same trust path:

1. User submits a source
2. System extracts a recipe candidate
3. User reviews the candidate
4. User saves as **canonical recipe** (trusted) or **draft** (incomplete/uncertain)

**All ingestions start with review.** No recipe enters the trusted corpus without explicit user confirmation.

**Minimum required fields for a canonical recipe:** title, at least one ingredient, at least one step. These thresholds are configurable for future adjustment.

**Drafts** are incomplete or uncertain recipes. They appear in the library with a draft label, can be edited, and can later be promoted to canonical through a promotion review pipeline. Drafts are excluded from grounded retrieval, ask, and create workflows until promoted.

#### Ingestion processing model

The system uses an **AI-powered ingestion agent** that dynamically decides which tools to use and how to handle intermediate results. The agent replaces a static processing pipeline with intelligent, adaptive orchestration.

**Agent behavior:** The agent receives a source, classifies it, and begins gathering evidence using a catalog of tools (page fetchers, OCR, transcript APIs, video processors, LLM extractors). After each tool call, the agent evaluates what it found and decides the next step. For clear-cut cases (e.g., recipe webpage with schema markup), the agent's decisions are deterministic and fast. For ambiguous cases (e.g., partial OCR text, recipe index instead of recipe page, caption with ingredients but no steps), the agent uses LLM reasoning to choose the best path.

**Design principle: deterministic by default, LLM when ambiguous.** Most routing decisions cost nothing. The LLM is consulted only at genuine decision points where the next step depends on understanding content quality.

**Key principle for video sources:** Prefer the cleanest written recipe source available. For YouTube and similar: check linked recipe pages in description, then in the first comment, then use transcript extraction, and process the actual video content only as a last resort.

**Handwritten recipes** are supported as assisted digitization. The agent runs OCR and evaluates text quality, using LLM reasoning to decide whether to attempt extraction or flag for heavier review.

**Safety limits:** Maximum 15 tool calls per ingestion. Most clean sources complete in 3–5 calls. Complex social videos use 10–12. The limit prevents runaway processing and cost.

#### Review agent

Before a recipe candidate reaches human review, an automated review agent runs to improve the candidate quality. The review agent fills obvious gaps, fixes ingredient mappings, verifies structural coherence, and flags remaining issues for human attention.

**The review agent runs on every candidate.** Even high-confidence extractions benefit from ingredient mapping verification and metadata gap-filling.

**What the review agent does:**
- Maps unmapped ingredients to the ingredient DB (exact and alias matching)
- Fills missing metadata (cook time, prep time, servings) by re-reading source artifacts
- Checks that steps reference ingredients that actually exist in the ingredient list
- Normalizes ingredient formatting inconsistencies
- Resolves review findings it can fix, adds new findings for issues it can't

**What the review agent does not do:**
- Invent content not supported by source artifacts
- Make subjective recipe judgments
- Override source-extracted content with its own preferences
- Rewrite the recipe in its own voice

**Provenance:** When the review agent fills a gap, the provenance is marked as `review_agent_enriched` with a reference to which source artifact the information came from. The human reviewer can see exactly what was source-extracted vs agent-enriched.

**Safety limits:** Maximum 10 tool calls, 30-second wall-clock timeout. If the review agent can't finish in time, it passes whatever it has to human review.

#### Rerun policy

Reruns are allowed **only for internal/server failures** (e.g., OCR provider timeout, extraction service crash, worker heartbeat timeout). Source quality issues and unsupported content issues are not retriable — those are handled through review, draft save, or graceful failure messaging.

A rerun re-triggers the entire pipeline from scratch, but the agent preserves progress from previous attempts — artifacts already created are not re-fetched, and tools that already succeeded are skipped.

#### Failure handling

The system handles failures gracefully at multiple levels:

**Transient failures** (API timeouts, rate limits) are retried automatically at the tool level with exponential backoff. The user never sees these unless all retries are exhausted.

**Stuck jobs** (worker crash mid-processing) are detected via heartbeat monitoring and automatically marked as failed with a retry option.

**Service outages** (OCR or transcription provider down) are detected via circuit breakers. The agent receives a signal and intelligently routes to an alternative tool when possible.

**Consistently failing sources** (malformed content that crashes the worker) are stopped after 3 attempts to prevent blocking other work.

#### Error classes

| Error type | Meaning | User rerun? |
|---|---|---|
| Internal | System/infrastructure failure | Yes |
| Source access | URL blocked, login-gated, unreachable | No |
| Source quality | Image unreadable, transcript too sparse | No |
| Parseability | Not a recipe, insufficient structure | No |

#### Review modes

The system assigns a review mode based on source quality and extraction confidence:

**Quick** — Clean webpage or text extraction. Light review with mostly structured fields.

**Standard** — OCR, transcript, or medium-confidence extraction. Structured review with source context and issue highlights.

**Reconstruction** — Handwritten or very noisy sources. Heavier review with side-by-side source visibility.

All modes use the same review shell with mode-specific modules enabled.

#### Provenance

Provenance is a core product theme. Every extracted recipe preserves:

- Which extraction method produced it
- Which intermediate artifacts supported each field
- Per-field source type and optional notes
- Source preview for review context

This enables trust messaging in the UI, better debugging, and future reviewer-agent capabilities.

### 3.3 Recipe management

#### Canonical recipes
The primary trusted recipe object. Editable after save. Meaningful content changes (title, ingredients, steps, times, servings) automatically create revision snapshots.

**Nutrition information:** Stored as a JSONB object with optional macro/micro fields (calories, protein, fat, carbohydrates, etc.) as strings with units. Only populated when the source explicitly provides nutrition data — the system does not guess or calculate values. Extracted from schema.org `NutritionInformation`, LLM-parsed text, or multimodal extraction.

**Chef's notes:** Stored as a JSONB array of `{type, text}` objects. Types: `tip`, `substitution`, `storage`, `variation`, `general`. Extracted via HTML pattern matching on recipe plugin note containers (e.g., `.wprm-recipe-notes`), with LLM fallback when HTML patterns find nothing. For non-URL sources (text, image, video), notes are extracted by the LLM alongside the recipe.

**What does not create a revision:** Tag changes, note additions, media uploads, metadata-only changes.

**Revision retention:** The system retains recent meaningful revisions as an implementation-level retention policy. Revision history is a recovery utility, not a primary product surface — it lives in an overflow/3-dot menu. Detailed retention rules are deferred post-MVP.

#### Draft recipes
A distinct editable working object. Originates from a recipe candidate. Can be edited and later promoted to canonical through a re-review pipeline. Once promoted, the draft is deleted but lightweight promotion metadata (source asset ID, origin candidate ID, promotion timestamp) is preserved on the canonical recipe.

**Promotion review:** When a user completes a draft and requests promotion, the system re-assesses eligibility (required fields present, structural sanity) and opens a promotion review screen. No full extraction rerun — only validation of current draft state.

#### Recipe editing
Direct inline editing. Save creates a new revision automatically if meaningful content changed. No explicit "edit mode" required — the system detects and handles revision-worthiness.

Restoring an old version creates a new current revision rather than destructive rewind.

### 3.4 Ingredient knowledge layer

Kama maintains a **global ingredient source database** alongside per-recipe ingredient rows.

**Ingredient entity:** A canonical ingredient with an ID, display name, `category` (IngredientCategory enum), aliases/synonyms, and optional notes. This enables future pantry matching, shopping list aggregation, and substitution intelligence.

**IngredientCategory enum:**

| Value | Description |
|---|---|
| `produce` | Fruits, vegetables, fresh herbs |
| `meat_seafood` | Chicken, beef, shrimp, etc. |
| `dairy` | Milk, cheese, yogurt, butter, cream |
| `grains_bread` | Rice, pasta, flour, bread, oats |
| `spices_seasoning` | Cumin, salt, pepper, paprika, dried herbs |
| `oils_vinegars` | Olive oil, sesame oil, balsamic, soy sauce |
| `canned_jarred` | Canned tomatoes, beans, coconut milk, broth |
| `frozen` | Frozen peas, frozen berries |
| `baking` | Sugar, baking powder, vanilla extract, chocolate |
| `nuts_seeds` | Almonds, sesame seeds, peanut butter |
| `beverages` | Wine (cooking), stock, juice |
| `other` | Anything that doesn't fit |

**Recipe ingredient row:** Preserves the original recipe text alongside an optional mapping to a canonical ingredient ID, plus optional quantity (string — no normalization in Phase 1) and unit.

**Mapping happens during extraction** when possible. Users can fix mappings during review.

**Seeding strategy:** The ingredient DB starts with a curated base set of common cooking ingredients (pantry staples, proteins, produce, dairy, spices, grains — roughly 300–500 entries covering the most frequently used ingredients across major cuisines). This base set is system-created and ships with the app.

**Growth model:** The DB grows organically as recipes are ingested. When extraction encounters an ingredient that does not match any existing entry (including aliases), a new ingredient record is created. During review, the user can confirm, correct, or create ingredient mappings. Over time the DB becomes a personalized ingredient vocabulary shaped by the user's actual recipe collection.

**Alias resolution:** When mapping a recipe ingredient line to the DB, the system checks both canonical names and aliases. For example, "coriander leaves" should resolve to the same ingredient as "cilantro." Alias coverage improves over time as users and extraction encounter regional/cultural variations.

### 3.5 Media model

Recipe media and journal media are completely separate concerns.

#### Recipe media
Extracted and user-uploaded images attached to the recipe itself.

**Roles:**
- **Hero** — Primary display image. One per recipe. Can be extracted from source or set by user.
- **Source gallery** — Additional images extracted from the source page, including step reference images.
- **Step reference** — Images associated with specific recipe steps.
- **User-added gallery** — Images uploaded by the user after save.

User-added recipe media does not trigger re-extraction or recipe revisions. No hard numeric cap on extracted non-hero images, but source-page image extraction should apply relevance/quality filtering.

#### Journal entry media
Images attached to a specific cook journal entry. Maximum 2 images per entry. These do not appear in the recipe gallery.

**All media** preserves source origin and creation timestamp.

### 3.6 Journal summary (journalSummary)

Each canonical recipe maintains a system-generated `journalSummary` — a derived, context-rich paragraph summarizing the user's cooking experience with that recipe across all journal entries.

**Purpose:** Improves semantic search, Ask context quality, and Create planning quality in Phase 2. Built in Phase 1 so the data is ready when retrieval features arrive.

**What it should capture:**
- Repeated ingredient substitutions that worked
- Timing deviations (took longer, quicker than expected)
- Family/household preference patterns (kids liked it, too spicy)
- Whether the recipe was successful or worth remaking
- Meaningful usage context (good for weeknights, great for meal prep)

**What it should exclude:**
- Irrelevant conversational noise
- One-off details with no future retrieval value
- Raw journal verbosity

**Product behavior:**
- System-generated, not directly user-editable
- Updated asynchronously whenever journal entries are created or deleted
- Full regeneration from all journal entries (optimization to incremental updates deferred)
- Stored on the CanonicalRecipe model
- No summary generated until at least 1 journal entry exists
- Null/empty when no journal entries exist

### 3.7 Cook journal

A first-class product feature, not a side note. The journal is the active memory layer for a recipe — what happened when the user actually cooked it.

**Recipe detail page structure:** Recipe content at top (like a post), cook journal below (like comments/activity), version history hidden in overflow menu.

#### Journal entry

Each entry contains:

- **Body text** — Freeform cooking notes
- **Timestamp** — System-created
- **Cooked-on date** — Optional, date-only, user-set. Allows logging after the fact.
- **Tags** — From the journal tag vocabulary
- **Images** — Up to 2 per entry

**Feed order:** Newest first.

**MVP behavior:** Entries can be created and deleted. No editing in Phase 1 (deferred).

### 3.8 Tag system

Shared infrastructure, separate vocabularies.

**One tag model** with a domain discriminator:
- **Recipe tags** — Classification metadata. Examples: "under 30 mins," "vegetarian," "kids favorite," "one pot." Can be extracted during ingestion, edited by user. Do not trigger recipe revisions.
- **Journal tags** — Usage memory metadata. Examples: "tweak," "success," "issue," "would make again," "took longer."

**Tag behavior:**
- Each domain has a predefined starter set plus user-extendable vocabulary
- When a user types a new tag, if it exists in that domain it is reused; otherwise it is created and persisted in that domain's library
- Tags are stored as IDs, not raw strings

### 3.9 Library behavior

Canonical recipes and drafts appear in the same library. Drafts are clearly labeled. Users can filter by status (all, canonical, drafts), by recipe tags, and by basic search.

---

## 4. Phase 2 product scope — Search, Ask, Create

### 4.1 Phase 2 vision

Phase 1 makes Kama a trustworthy recipe capture and management system. Phase 2 makes Kama a recipe intelligence and planning system.

Users should be able to search their saved recipe corpus effectively, ask grounded questions over their recipes, and generate useful outputs such as shopping lists, meal plans, and pantry-feasible recipe suggestions.

**Phase 2 promise:** Use your saved recipe knowledge to find what matters, ask better questions, and generate useful plans.

### 4.2 Phase 2 product surfaces

Phase 2 introduces three independent capability groups that share common retrieval foundations.

#### Search

Allow users to find recipes quickly using both structured filters and semantic matching. Search should feel like retrieval over the user's own recipe knowledge base, not generic internet search.

**Search capabilities:**
- Recipe title and description search
- Ingredient-aware search (by ingredient ID and semantic ingredient queries)
- Tag-based filtering
- Time-based filtering (prep time, cook time)
- Journal-aware relevance through journalSummary
- Search over canonical recipes only (drafts excluded)

**Search relevance signals:** title, description, structured ingredients, recipe tags, time metadata, journalSummary.

**Retrieval strategy:** Hybrid retrieval using dense semantic embeddings (OpenAI text-embedding-3-small) and sparse BM25 keyword vectors, fused via Reciprocal Rank Fusion (RRF) in a single Qdrant query. Structured metadata filters (tags, ingredient IDs, time constraints) apply alongside vector search. Dense vectors capture meaning ("comfort food"), sparse vectors capture exact terms ("paneer"), and structured filters handle factual constraints ("under 30 minutes"). No reranker is used in production.

**Example queries:**
- "under 30 min vegetarian dinners"
- "recipes with paneer and spinach"
- "kid-friendly pasta recipes"
- "recipes I should remake"
- "recipes where substitutions worked well"

#### Ask

Allow users to ask grounded, natural-language questions over their saved recipe corpus with short session memory for follow-up questions.

**Ask model:** Short session memory. Users can ask a question and follow up within the same session (e.g. "what can I make with chickpeas?" → "which of those are under 30 minutes?"). Session context is maintained during the conversation but is not persisted long-term. A new question outside the session starts fresh.

**Ask grounding rules:**
- Ask must be grounded in canonical recipes, recipe metadata, recipe tags, ingredient mappings, and journalSummary
- Ask must not rely on drafts, ungrounded open-web cooking knowledge, or generic assistant-style responses unrelated to the saved corpus
- Ask answers must cite which recipes they're based on

**Ask UX principle:** Ask helps the user interrogate their own recipe library, not replace it with a chatbot.

**Recipe-scoped Ask (chef persona):** When viewing a specific recipe, the user can ask contextual questions about that recipe with an expert chef persona. Examples: "What can I substitute for cream in this pasta?" or "Can I make this without coconut milk?" The system loads the recipe's full context (ingredients, steps, journalSummary) and responds with chef-level cooking knowledge applied to that specific recipe. This is not a separate agent — it's a mode of the Ask surface using a chef expert system prompt with fixed recipe context.

**Example queries:**
- "Which of my recipes are good for weekday dinners?"
- "What can I make with chickpeas and spinach from my saved recipes?"
- "Which recipes seem most kid-friendly based on how I used them before?"
- "Which saved recipes are easiest when I'm short on time?"
- Follow-up: "What about ones that are also vegetarian?"

#### Create

Generate practical, persistent outputs from saved recipes that help users plan and act. Generated artifacts are first-class objects: saved, editable, and linked back to source recipes.

**Phase 2 Create outputs:**

**Shopping list** — Generate an aggregated shopping list from one or more selected or system-recommended recipes. Ingredients are grouped and deduplicated using the ingredient knowledge layer. **Grouping uses `ingredient.category` deterministically** — mapped ingredients are placed into their DB-assigned category section (Produce, Dairy, Meat & Seafood, etc.) with no LLM call required. LLM-based category inference is used only as a fallback for unmapped ingredients (those without an `ingredientId`). Users can edit the list after generation. The list preserves linkage to the source recipes that produced each item.

**Meal plan** — Generate a meal plan from saved recipes using tags, time constraints, ingredients, recipe fitness, and journal-derived context. Plans are editable and saveable. Each meal slot links to its source recipe.

**Pantry feasibility / what can I cook** — Identify recipes that are fully feasible, partially feasible, or missing ingredients based on the user's pantry. Relies on canonical ingredient IDs matched against pantry contents.

**Create artifact behavior:**
- Artifacts are saved automatically on generation
- Artifacts are editable after generation
- Artifacts preserve linkage to source recipes
- Artifacts support revision history
- Artifacts are first-class domain objects, not throwaway outputs

### 4.3 Pantry

Phase 2 introduces a persistent pantry that the user maintains over time.

**Pantry behavior:**
- Users add ingredients to their pantry from the ingredient DB
- Users can add ingredients via free text (mapped to ingredient IDs)
- Users can remove ingredients as they're used
- Pantry persists across sessions
- Pantry is used by the Create surface for feasibility matching

**Pantry feasibility matching:**
- Fully feasible: all recipe ingredients are in pantry
- Partially feasible: most ingredients present, some missing
- Not feasible: too many missing ingredients
- Missing ingredients are shown explicitly

**Pantry is a constrained feature, not a full inventory management system.** Phase 2 pantry tracks what ingredients the user has available. It does not track quantities, expiry dates, or purchase history.

### 4.4 Phase 2 data foundations

Phase 2 depends on these Phase 1 assets:
- Canonical recipe corpus with structured content
- Ingredient knowledge layer and recipe-to-ingredient mappings
- Recipe tags (recipe domain)
- Cook journal + journalSummary
- Recipe media and metadata
- Provenance-rich saved recipes

Phase 2 adds:
- Recipe search index in Qdrant (dense + sparse vectors per recipe, payload metadata for filtering)
- AskSession for conversational context
- Artifact model for Create outputs
- PantryItem model for persistent pantry

### 4.5 Phase 2 user workflows

**Search recipe corpus:** User searches using text, filters, or ingredients. System returns relevant canonical recipes ranked by structured match + semantic similarity. journalSummary influences ranking where relevant.

**Ask a grounded question:** User submits a natural-language question. System retrieves relevant canonical recipes. System returns a grounded answer citing specific recipes. User can follow up within the session.

**Create a shopping list:** User selects recipes or asks Kama to suggest relevant ones. System aggregates ingredient rows across recipes, deduplicates via ingredient IDs. System generates a shopping list artifact. User can edit and save.

**Generate a meal plan:** User specifies planning context or constraints (e.g. "3-day vegetarian plan for this week"). System selects relevant recipes from the corpus. System generates a meal plan artifact with recipe assignments per meal slot. User can edit, swap recipes, and save.

**Check pantry feasibility:** User maintains their pantry ingredient list. System maps pantry items to canonical ingredient IDs. User opens pantry view and sees which saved recipes are fully/partially/not feasible. Missing ingredients are shown per recipe.

### 4.6 Phase 2 success metrics

**Search:** search usage rate, search-to-recipe clickthrough, search refinement rate, retrieval relevance benchmarks.

**Ask:** ask usage rate, grounded answer usefulness, question-to-recipe engagement, answer relevance benchmarks.

**Create:** shopping list generation rate, meal plan generation rate, pantry feasibility usage rate, artifact save/edit/reuse rate.

**journalSummary:** summary update success rate, search/ask relevance improvement from journalSummary inclusion.

### 4.7 Phase 2 deferred items

- Broad open-ended internet cooking assistant behavior
- Social collaboration on artifacts
- Duplicate-aware retrieval enhancements
- Multi-user shared workspaces
- Full pantry management (quantities, expiry, purchase tracking)
- Complex nutrition intelligence
- Artifact types beyond shopping list, meal plan, and pantry feasibility

---

## 5. Success metrics

### Phase 1

**Ingestion quality:**
- Extraction acceptance rate (% of ingestions that produce a usable candidate)
- % of canonical recipes requiring fewer than 3 field edits during review
- Source-type-specific extraction success rates

**Product engagement:**
- Recipes saved per user
- Journal entries per recipe
- Drafts promoted to canonical

**Trust signals:**
- % of recipes with complete provenance
- Review completion rate (not abandoned)

### Phase 2

- Grounded answer citation rate
- Artifact save/export rate
- Retrieval relevance on known-answer queries

---

## 6. Feature scope template

Use this template when adding new features to the Kama product spec.

```
### Feature: [Name]

**Surface:** [Ingest / Library / Recipe detail / Journal / Ask / Create]

**User story:** As a [user type], I want to [action] so that [outcome].

**Behavior:**
- [Key behavior 1]
- [Key behavior 2]

**Constraints:**
- [Trust/quality constraint]
- [Scope boundary]

**Domain objects affected:**
- [Object 1] — [how it changes]
- [Object 2] — [how it changes]

**Phase:** [1 / 2 / Later]

**Open questions:**
- [Question 1]
```

---

## 7. Deferred decisions (parking lot)

These are decisions explicitly deferred from Phase 1 to avoid scope creep. They remain on the roadmap.

- Duplicate/near-duplicate recipe detection and merge flows
- Share-for-review via external form URL
- Journal entry editing
- Multi-recipe extraction from a single source
- Recipe change suggestions derived from journal entries
- Journal-activity-driven library ranking/sorting
- Revision retention rules beyond "keep recent meaningful versions"
- Advanced collaboration features
- Analytics dashboard
- Social media private/login-gated content extraction
- Social media carousel image slide extraction (no video, no caption text)
- Ingredient quantity normalization
- Ingredient nutrition linkage
- Recipe reviewer agent for automated quality assessment
