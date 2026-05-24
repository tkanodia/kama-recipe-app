# Kama — Frontend Routes, Screens & States

**Version:** 1.0  
**Stack:** Next.js App Router, Tailwind CSS, TanStack Query, React Hook Form, Clerk auth  
**Purpose:** Complete screen inventory for Phase 1 and Phase 2. Use as input for v0 screen generation and AI coding tools.

---

## 1. Complete route map

### Phase 1 routes

```
/                                → Redirect to /recipes or /sign-in
/sign-in                         → Clerk sign-in
/sign-up                         → Clerk sign-up

/recipes                         → Recipe library (list, filter, search)
/recipes/[id]                    → Recipe detail (content + journal)
/recipes/[id]/edit               → Recipe edit mode

/drafts/[id]                     → Draft detail / edit
/drafts/[id]/promote             → Draft promotion review

/ingest                          → Ingestion entry (submit source)
/ingest/[jobId]                  → Ingestion progress (SSE tracking)
/ingest/[jobId]/review           → Candidate review screen
```

### Phase 2 routes

```
/search                          → Search (hybrid semantic + structured)
/ask                             → Ask surface (grounded Q&A)
/ask/[sessionId]                 → Active ask session
/create                          → Create hub (shopping list, meal plan, pantry)
/create/shopping-list/new        → Generate shopping list
/create/meal-plan/new            → Generate meal plan
/artifacts                       → Artifact library (all generated outputs)
/artifacts/[id]                  → Artifact detail (view + edit)
/pantry                          → Pantry management
/pantry/feasibility              → Pantry feasibility results
```

### Navigation model

**Primary nav (sidebar or top bar):** Recipes, Ingest, Search (Phase 2), Ask (Phase 2), Create (Phase 2), Pantry (Phase 2).

**Secondary nav:** Settings, Tag management (low priority).

All major flows are page-level routes, not modals. Modals/drawers used only for: revision history, confirmation dialogs, image lightbox.

---

## 2. Phase 1 screens

### 2.1 Recipe library — `/recipes`

**Purpose:** Browse, filter, and manage all saved recipes and drafts.

**Layout:** Full-page list view. Filter bar at top, recipe cards below.

**Data:**
- `GET /api/recipes` — paginated list with filters
- `GET /api/tags?domain=recipe` — tag list for filter dropdown

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Initial fetch | Skeleton cards |
| Empty | No saved recipes | Empty state with CTA → `/ingest` |
| Populated | Recipes exist | Card grid or list |
| Filtered | Filters active | Filtered results with active filter chips |
| No results | Filters match nothing | "No recipes match" message with clear option |

**Components:**

**Filter bar** — Status toggle (all / canonical / drafts), tag multi-select, search input (debounced), sort selector (updated desc, created desc, title asc).

**Recipe card** — Hero image or placeholder, title, description snippet (1–2 lines), cook time badge, up to 3 tag chips, draft badge if applicable, journal entry count indicator. Entire card clickable → `/recipes/[id]` or `/drafts/[id]`.

**Pagination** — Infinite scroll or "Load more" with cursor pagination.

**Interactions:**
- Click card → recipe detail or draft detail
- Apply filter → refetch, update URL query params for shareable filter state
- FAB or header button → `/ingest`

---

### 2.2 Recipe detail — `/recipes/[id]`

**Purpose:** View a saved recipe. Recipe on top like a post, journal below like comments.

**Layout:** Single-column. Hero → metadata → ingredients → steps → gallery → journal.

**Data:**
- `GET /api/recipes/[id]` — full recipe with media, tags, provenance
- `GET /api/recipes/[id]/journal` — paginated journal entries, newest first

**Sections:**

**Hero** — Full-width hero image (or placeholder), title, description, metadata row (prep time, cook time, servings), tag chips.

**Action bar** — Edit button → `/recipes/[id]/edit`. Overflow menu (⋯): view revisions, delete recipe.

**Ingredients** — Structured list. Each row: text, quantity/unit if present, ingredient DB mapping indicator (linked or unmapped icon). Each ingredient row carries a `category` field (from the linked Ingredient record). Optional: on recipes with long ingredient lists, ingredients may be visually grouped by category for readability.

**Steps** — Ordered list. Each step: number, text, inline step images if present.

**Gallery** — Additional recipe images below steps (source + user-added). Tap to enlarge.

**Provenance (collapsed)** — Expandable "How this recipe was created" panel. Source type, extraction method used, review agent enrichment summary. Light trust information.

**Journal section** — "Cook journal" header with entry count. Composer at top. Feed below, newest first.

**Journal composer** — Text input (required), date picker (optional cooked-on date), journal tag selector, image upload (max 2 images), submit button.

**Journal entry card** — Body text, cooked-on date if set, tag chips, attached images, timestamp, delete button with confirmation.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetch in progress | Skeleton layout |
| Loaded | Data available | Full recipe view |
| No journal entries | Zero entries | Composer only, empty state prompt |
| Journal loading | Entries loading separately | Recipe visible, journal skeleton |

**Interactions:**
- Edit → `/recipes/[id]/edit`
- View revisions → drawer/modal with revision list
- Restore revision → confirm dialog → `POST .../restore` → refresh
- Submit journal entry → `POST /api/recipes/[id]/journal` → optimistic append
- Delete journal entry → confirm → `DELETE /api/journal/[id]` → optimistic remove
- Upload journal images → presigned URL flow → attach refs on submit
- Expand provenance → toggle section

---

### 2.3 Recipe edit — `/recipes/[id]/edit`

**Purpose:** Edit canonical recipe content. Backend determines revision-worthiness.

**Layout:** Form view matching recipe structure, all fields editable.

**Data:**
- `GET /api/recipes/[id]` — current data (pre-populate form)
- `GET /api/tags?domain=recipe` — tag options
- `GET /api/ingredients?search=...` — ingredient search for mapping

**Form sections:**

**Title** — Text input, required.

**Description** — Textarea, optional.

**Metadata** — Prep time (minutes), cook time (minutes), servings (number). All optional.

**Ingredients** — Dynamic row list. Each row: text input (required), ingredient mapping (search ingredient DB, select or create), quantity, unit. Add/remove/reorder rows.

**Steps** — Dynamic ordered list. Each: textarea (required), optional image attachment. Add/remove/reorder.

**Tags** — Multi-select with create-new option. Recipe domain.

**Hero image** — Current hero shown. Option to change from gallery or upload new.

**Actions** — Save, Cancel. Unsaved changes guard on navigation.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching current data | Form skeleton |
| Ready | Form populated | Editable form, save disabled |
| Dirty | Unsaved changes exist | Save enabled, unsaved indicator |
| Saving | Save in progress | Button loading state |
| Saved | Success | Toast, navigate to detail |
| Validation error | Save rejected | Field-level errors |

**Interactions:**
- Edit any field → dirty state
- Save → `PATCH /api/recipes/[id]` → navigate to detail on success
- Cancel → confirm if dirty → navigate to detail
- Search ingredient → `GET /api/ingredients?search=...` → dropdown results
- Create new ingredient → inline create → `POST /api/ingredients`
- Reorder rows → drag-and-drop or up/down buttons
- Upload media → presigned URL → `POST /api/recipes/[id]/media`

---

### 2.4 Revision history — drawer on recipe detail

**Purpose:** View and restore previous versions. Accessed from overflow menu.

**Layout:** Slide-out drawer or modal. Revision list.

**Data:** `GET /api/recipes/[id]/revisions`

**Components:**

**Revision entry** — Timestamp, change summary text, "Restore" button.

**Restore flow** — Confirm dialog → `POST .../restore` → success → refresh recipe detail.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching revisions | Skeleton list |
| Empty | Never edited | "No previous versions" |
| Populated | Revisions exist | List with restore actions |

---

### 2.5 Draft detail — `/drafts/[id]`

**Purpose:** View and edit a draft. Similar to recipe edit but with draft status and promotion CTA.

**Layout:** Same form layout as recipe edit, with draft banner and promotion button.

**Data:**
- `GET /api/drafts/[id]`
- `GET /api/tags?domain=recipe`
- `GET /api/ingredients?search=...`

**Key differences from recipe edit:**
- Draft status banner: "This is a draft. Complete the required fields to save as a trusted recipe."
- Promotion CTA: "Review for trusted save" — enabled when `promotionEligible` is true, disabled with helper text showing what's missing
- Missing required fields have gentle indicators, not aggressive errors
- No revision history

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching | Form skeleton |
| Incomplete | Missing required fields | Banner with guidance |
| Promotion ready | All required fields present | Promotion button enabled |
| Saving | Edits saving | Loading state |

**Interactions:**
- Edit fields → `PATCH /api/drafts/[id]`
- Promotion button → `/drafts/[id]/promote`

---

### 2.6 Draft promotion review — `/drafts/[id]/promote`

**Purpose:** Two-step review before promoting draft to canonical.

**Data:**
- `POST /api/drafts/[id]/review-for-canonical` — assessment
- `POST /api/drafts/[id]/promote` — confirm

**Step 1 — Assessment:** System checks eligibility. Shows findings, field summary, eligibility result.

**Step 2 — Confirmation:** Optional final edits, confirm button. Success → redirect to `/recipes/[newId]`.

**States:**

| State | Condition | User sees |
|---|---|---|
| Assessing | API call in progress | Loading |
| Eligible | Passed assessment | Review summary + confirm button |
| Not eligible | Blocking issues found | Issues list + "Continue editing" back to draft |
| Promoting | Confirmation in progress | Loading |
| Success | Done | Success message, redirect to recipe |

---

### 2.7 Ingestion entry — `/ingest`

**Purpose:** Submit a new recipe source.

**Layout:** Centered card with source type tabs and input area.

**Data:** `POST /api/ingestion` on submit. `POST /api/media/presigned-url` for image upload.

**Tabs:**

**URL tab** — URL input with paste support. Optional context note.

**Image tab** — Drag-and-drop / click-to-upload area. Preview after selection. Optional context note.

**Text tab** — Large textarea. Optional context note.

**States:**

| State | Condition | User sees |
|---|---|---|
| Ready | Default | Tabs with empty input |
| Input provided | Content entered | Submit enabled |
| Uploading | Image presigned URL flow | Progress indicator |
| Submitting | POST in progress | Button loading |
| Error | Submission failed | Error with retry |

**Interactions:**
- Switch tab → clear input, show new type
- Paste URL → auto-populate
- Drop image → upload, show preview
- Submit → navigate to `/ingest/[jobId]`

---

### 2.8 Ingestion progress — `/ingest/[jobId]`

**Purpose:** Real-time tracking of ingestion job via SSE. Shows agent activity and transitions to review when ready.

**Layout:** Centered status card with source preview and progress visualization.

**Data:**
- `GET /api/ingestion/jobs/[jobId]` — snapshot for initial load / reconnect
- `GET /api/ingestion/jobs/[jobId]/events` — SSE stream

**Components:**

**Source preview** — What was submitted: URL card, image thumbnail, or text excerpt.

**Status indicator** — Animated step display:
- "Reading source..." (source acquisition)
- "Extracting recipe..." (extraction phase)
- "Reviewing and enriching..." (review agent phase)
- "Ready for review" (complete)

**Progress feed (optional)** — Collapsible timeline of agent tool calls and decisions. Shows tool names and outcomes. Not critical for v1 but useful for power users and debugging. Can be a secondary expandable section.

**Error state** — If job fails: error message, explanation (source quality / access / system), retry button if `rerunAllowed`.

**States:**

| State | Condition | User sees |
|---|---|---|
| Connecting | SSE not yet connected | Loading spinner |
| Processing | SSE streaming events | Animated status steps |
| Review ready | `job.review_ready` received | "Recipe ready for review" + CTA button |
| Draft ready | `job.draft_ready` received | "Partial recipe found, review as draft" + CTA |
| Failed (retriable) | `job.failed` + `rerunAllowed` | Error message + "Try again" button |
| Failed (final) | `job.failed` + not retriable | Error message + "Try different source" link |
| Unsupported | `job.unsupported` | "Couldn't extract recipe" message with explanation |

**Interactions:**
- "Review recipe" button → `/ingest/[jobId]/review`
- "Try again" → `POST /api/ingestion/jobs/[jobId]/rerun` → new jobId → same page with new SSE
- "Try different source" → `/ingest`
- Page refresh / SSE disconnect → fetch snapshot via GET, reconnect SSE

---

### 2.9 Candidate review — `/ingest/[jobId]/review`

**Purpose:** Review extracted recipe candidate before saving. The most complex Phase 1 screen. Shows what the system extracted, what the review agent enriched, and what needs human attention.

**Layout:** Two-column on desktop. Left: editable recipe form. Right: source context and review findings. Single column stacked on mobile.

**Data:**
- `GET /api/recipe-candidates/[candidateId]` — full candidate with provenance, findings, source context, agent summary
- `GET /api/tags?domain=recipe` — tag options
- `GET /api/ingredients?search=...` — ingredient search

**Left column — Recipe editor:**

**Title** — Text input, pre-populated. Required field indicator if empty.

**Ingredients** — Dynamic row list. Each row: text, ingredient mapping selector, quantity, unit. Rows with `review_agent_enriched` provenance show a subtle "AI enriched" indicator. Unmapped ingredients highlighted gently.

**Steps** — Ordered step list. Each: text, optional step images. Same provenance indicators for agent-enriched content.

**Metadata** — Prep time, cook time, servings, description. Fields filled by review agent show provenance indicator.

**Tags** — Tag selector with recipe-domain tags.

**Right column — Review context:**

**Review agent summary** — "AI verified 6 ingredients, filled in cook time, flagged 1 issue." Shows what the review agent accomplished before human review.

**Review findings** — Ordered by severity (errors → warnings → info). Each finding: severity icon, message, affected field reference. Resolved findings shown as crossed out or in a collapsed "resolved" section. Clickable findings scroll to the relevant field in the left column.

**Source context** — Source preview card (URL card, image thumbnail, or text excerpt). Provenance messages: "Recipe extracted from linked blog page found in video description" or "Ingredients from caption, cook time found by review agent in transcript." Expandable raw source view for power users.

**Bottom action bar (sticky):**
- "Save as trusted recipe" — primary action, enabled when canonical-eligible
- "Save as draft" — secondary action, always available if draft-eligible
- "Discard" — tertiary action with confirmation

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching candidate | Skeleton layout |
| Ready | Candidate loaded | Two-column editor + context |
| Canonical eligible | Required fields present + no blocking findings | "Save as trusted recipe" enabled |
| Draft only | Not canonical eligible | "Save as trusted recipe" disabled, tooltip explains why |
| Dirty | User has edited fields | Subtle unsaved indicator |
| Saving | Decision submission in progress | Action buttons loading |
| Saved | Success | Toast + redirect to `/recipes/[newId]` or `/drafts/[newId]` |

**Interactions:**
- Edit any field → form dirty state
- Click finding → scroll to affected field
- Save as canonical → `POST /api/recipe-candidates/[id]/decision` with `save_canonical` + edited fields → redirect to recipe detail
- Save as draft → same endpoint with `save_draft` → redirect to draft detail
- Discard → confirm → same endpoint with `discard` → redirect to `/recipes` or `/ingest`
- Search ingredient mapping → `GET /api/ingredients?search=...`
- Create new ingredient inline → `POST /api/ingredients`

---

## 3. Phase 2 screens

### 3.1 Search — `/search`

**Purpose:** Hybrid semantic + structured search over canonical recipes.

**Layout:** Full-page. Search input prominently at top. Results below. Filter sidebar or collapsible filter panel.

**Data:**
- `POST /api/search` — hybrid search with query + filters
- `GET /api/tags?domain=recipe` — tag options for filter panel

**Components:**

**Search bar** — Large text input. Placeholder: "Search your recipes..." Submit on enter or search button. Shows parsed query interpretation below input after search ("Searching for: quick pasta | Filters: vegetarian, under 30 min").

**Filter panel** — Tag multi-select, max cook time slider/input, max prep time slider/input, servings range. Collapsible on mobile. Filters combine with search query.

**Results list** — Recipe cards (same component as library but with relevance additions). Each card shows: hero image, title, description snippet, cook time, tag chips, relevance score or match reason chips ("tag: vegetarian", "semantic: kid-friendly", "ingredient: paneer").

**Empty/no results** — "No recipes match your search" with suggestions to broaden query or clear filters.

**States:**

| State | Condition | User sees |
|---|---|---|
| Initial | No search yet | Search bar + "Search your recipe collection" prompt |
| Searching | Query submitted | Skeleton results |
| Results | Results returned | Recipe cards with match reasons |
| No results | Search returned empty | "No matches" with suggestions |
| Filter only | No text query, just filters | Filtered results sorted by recency |

**Interactions:**
- Type + submit → `POST /api/search` with query + filters
- Apply filter → re-search with updated filters
- Click result → `/recipes/[id]`
- Clear search → return to initial state

---

### 3.2 Ask — `/ask`

**Purpose:** Entry point for grounded Q&A over recipe corpus.

**Layout:** Chat-like interface. Question input at bottom, responses above.

**Data:** `POST /api/ask/sessions` — create session with first question.

**Components:**

**Question input** — Text input at bottom of page. Placeholder: "Ask about your recipes..." Submit on enter.

**Welcome state** — Suggested questions: "What can I make for a quick weeknight dinner?", "Which recipes are kid-friendly?", "What should I cook with chickpeas?"

**States:**

| State | Condition | User sees |
|---|---|---|
| Initial | No active session | Welcome message + suggested questions |
| Submitting | First question sent | Loading indicator |
| Session created | Response received | Redirect to `/ask/[sessionId]` |

---

### 3.3 Ask session — `/ask/[sessionId]`

**Purpose:** Active conversation with grounded recipe answers and follow-up support.

**Layout:** Chat-style. Messages stack vertically, newest at bottom. Input fixed at bottom.

**Data:**
- `GET /api/ask/sessions/[sessionId]` — session with message history (for refresh/recovery)
- `POST /api/ask/sessions/[sessionId]/messages` — send follow-up

**Components:**

**Message thread** — Alternating user/assistant messages. User messages are plain text bubbles. Assistant messages include: answer text, cited recipe cards (inline or below answer), "Based on N recipes" indicator.

**Cited recipe cards** — Compact recipe card: hero thumbnail, title, cook time. Clickable → `/recipes/[id]` (opens in new tab or navigates with back support).

**Question input** — Fixed at bottom. "Ask a follow-up..." placeholder. Submit on enter.

**Session status** — Subtle indicator: "Active session" or "Session ended — start a new question."

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching session | Skeleton |
| Active | Messages loaded, session active | Chat thread + input |
| Generating | Follow-up submitted, waiting | Typing indicator on assistant side |
| Closed | Session timed out or closed | Thread visible, input disabled, "Start new question" link |

**Interactions:**
- Type + submit → `POST .../messages` → append user message → show generating → append assistant response
- Click cited recipe → navigate to recipe detail
- Start new question → `/ask`
- Session timeout → input disabled, prompt to start new session

---

### 3.4 Create hub — `/create`

**Purpose:** Entry point for generating artifacts. Shows what can be created and links to existing artifacts.

**Layout:** Card grid showing creation options and recent artifacts.

**Components:**

**Creation option cards:**
- "Shopping list" — description: "Generate a grouped shopping list from selected recipes" → `/create/shopping-list/new`
- "Meal plan" — description: "Plan meals for the week from your recipe collection" → `/create/meal-plan/new`
- "What can I cook?" — description: "Find recipes you can make with what's in your pantry" → `/pantry/feasibility`

**Recent artifacts** — Last 5 generated artifacts with type icon, title, date. "View all" → `/artifacts`.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching recent artifacts | Skeleton cards |
| Ready | Options + artifacts loaded | Creation options + recent list |
| No artifacts | No generated artifacts yet | Creation options only, "Create your first..." prompt |

---

### 3.5 Generate shopping list — `/create/shopping-list/new`

**Purpose:** Select recipes and generate an aggregated shopping list.

**Layout:** Two steps: recipe selection → generated list.

**Data:**
- `GET /api/recipes` or `POST /api/search` — for recipe selection
- `POST /api/artifacts/generate` with `artifactType: "shopping_list"`

**Step 1 — Recipe selection:**
- Search/browse recipe library inline (compact recipe cards)
- Selected recipes shown as pills/chips above the list
- "Generate shopping list" button when at least 1 recipe selected
- Optional: text input for additional instructions ("exclude pantry staples")

**Step 2 — Generated list:**
- Shopping list grouped by **ingredient category** (Produce, Dairy & Eggs, Meat & Seafood, etc.) — sections are determined by `ingredient.category` from the DB, not LLM-assigned categories. LLM fallback only for unmapped ingredients.
- Each item: text, quantity, source recipe indicator (which recipe needs it)
- Checkboxes for marking items
- Editable: can add/remove items, change quantities
- Title editable
- "Save" to persist → redirect to `/artifacts/[newId]`

**States:**

| State | Condition | User sees |
|---|---|---|
| Selecting | Choosing recipes | Recipe browser + selected chips |
| Generating | API call in progress | Loading with "Building your list..." message |
| Generated | List ready | Editable shopping list |
| Saving | Persisting artifact | Save button loading |
| Saved | Success | Redirect to artifact detail |

---

### 3.6 Generate meal plan — `/create/meal-plan/new`

**Purpose:** Generate a meal plan from saved recipes.

**Layout:** Constraint input → generated plan.

**Data:**
- `POST /api/artifacts/generate` with `artifactType: "meal_plan"`

**Step 1 — Constraints:**
- Number of days (default 3)
- Meals per day (checkboxes: breakfast, lunch, dinner, snack)
- Optional: dietary preference tags
- Optional: max cook time
- Optional: specific recipes to include
- Optional: free-text instructions ("vegetarian dinners, quick lunches")
- "Generate plan" button

**Step 2 — Generated plan:**
- Day-by-day view. Each day shows meal slots with assigned recipes.
- Each recipe slot: recipe title, hero thumbnail, cook time. Clickable → recipe detail.
- Editable: swap recipes (opens recipe picker), remove meal, add notes.
- Title editable.
- "Save" to persist → redirect to `/artifacts/[newId]`

**States:**

| State | Condition | User sees |
|---|---|---|
| Input | Entering constraints | Constraint form |
| Generating | API call in progress | Loading with "Planning your meals..." |
| Generated | Plan ready | Day-by-day editable plan |
| Saving | Persisting | Save button loading |
| Saved | Success | Redirect to artifact detail |

---

### 3.7 Artifact library — `/artifacts`

**Purpose:** Browse all generated artifacts (shopping lists, meal plans, feasibility results).

**Layout:** List view with type filter.

**Data:** `GET /api/artifacts` — paginated, filterable by type and status.

**Components:**

**Filter bar** — Type filter (all / shopping lists / meal plans / pantry feasibility), status toggle (active / archived).

**Artifact card** — Type icon, title, source recipe count, created/updated date. Clickable → `/artifacts/[id]`.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching | Skeleton list |
| Empty | No artifacts | Empty state with CTA → `/create` |
| Populated | Artifacts exist | Artifact cards |

---

### 3.8 Artifact detail — `/artifacts/[id]`

**Purpose:** View and edit a saved artifact.

**Layout:** Depends on artifact type. Shopping lists show grouped checklist. Meal plans show day view. Pantry feasibility shows recipe feasibility list.

**Data:**
- `GET /api/artifacts/[id]` — full artifact content
- `PATCH /api/artifacts/[id]` — save edits

**Common elements:**
- Title (editable)
- Source recipes list (links to recipe detail)
- Last updated timestamp
- Action bar: Save edits, Archive, overflow menu (revision history)

**Shopping list view:** Category sections with checkbox items. Add/remove/edit items. Source recipe indicator per item.

**Meal plan view:** Day cards with meal slot rows. Each slot shows recipe + cook time. Swap recipe action per slot.

**Pantry feasibility view:** Three sections: fully feasible, partially feasible (with missing ingredients), not feasible. Each entry links to recipe detail.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching | Skeleton |
| Viewing | Data loaded, no edits | Content display |
| Editing | User changed content | Save enabled, dirty indicator |
| Saving | Persist in progress | Loading |
| Saved | Success | Toast |

---

### 3.9 Pantry — `/pantry`

**Purpose:** Manage persistent pantry ingredient list.

**Layout:** Two sections: add ingredients + current pantry list.

**Data:**
- `GET /api/pantry` — current items
- `POST /api/pantry` or `POST /api/pantry/from-text` — add items
- `DELETE /api/pantry` — remove items

**Components:**

**Add section** — Search input that searches ingredient DB. Autocomplete dropdown. Select → add. Also supports free text entry with fuzzy matching ("chickpeas" → matches existing ingredient or suggests close matches).

**Pantry list** — All current pantry items grouped by **ingredient category** (Produce, Dairy & Eggs, Spices & Seasoning, etc.) with section headers and per-category item counts. Each item: ingredient name, added date, remove button (x).

**Quick actions** — "What can I cook?" button → `/pantry/feasibility`. Item count badge.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Fetching pantry | Skeleton |
| Empty | No items in pantry | Empty state: "Add ingredients to your pantry" |
| Populated | Items exist | Ingredient list + add section |
| Adding | Adding new item | Inline loading on that item |
| Removing | Removing item | Optimistic remove with undo toast |

**Interactions:**
- Search ingredient → `GET /api/ingredients?search=...` → autocomplete
- Select from autocomplete → `POST /api/pantry` → optimistic add
- Type free text → `POST /api/pantry/from-text` → handle match/no-match/suggestions
- Remove → `DELETE /api/pantry` → optimistic remove
- "What can I cook?" → `/pantry/feasibility`

---

### 3.10 Pantry feasibility — `/pantry/feasibility`

**Purpose:** Show which recipes the user can cook based on current pantry contents.

**Layout:** Filtered results page. Three sections ranked by feasibility.

**Data:**
- `POST /api/pantry/feasibility` — feasibility check against all canonical recipes

**Components:**

**Filter bar** — Optional filters: tags, max cook time. These narrow which recipes are checked.

**Feasibility sections:**

**Fully feasible** — Recipes where all ingredients are in pantry. Recipe cards with green "Ready to cook" badge.

**Partially feasible** — Recipes with most ingredients available. Recipe cards with amber badge showing "Missing 2 ingredients." Expandable missing ingredients list per recipe.

**Not feasible** — Collapsed by default. Recipe cards with red badge showing missing count. Less prominent display.

**Actions:** "Save this check" → generates a `pantry_feasibility` artifact. "Make shopping list for missing" → pre-selects partially feasible recipes and navigates to shopping list generator with missing ingredients pre-populated.

**States:**

| State | Condition | User sees |
|---|---|---|
| Loading | Running feasibility check | "Checking your pantry against N recipes..." |
| Results | Check complete | Three-section feasibility results |
| Empty pantry | No items in pantry | "Add ingredients to your pantry first" → `/pantry` |
| All feasible | Every recipe is fully feasible | Celebration state + recipe cards |
| None feasible | Nothing fully feasible | Show partially feasible prominently |

---

## 4. Shared components (cross-screen)

These components appear on multiple screens and should live in `/packages/ui` or at least be built as reusable components.

**Recipe card** — Used in: library, search results, ask citations, create recipe selection, feasibility results. Variants: full (with description, journal count), compact (thumbnail + title + cook time), selectable (with checkbox for create flows).

**Ingredient row editor** — Used in: recipe edit, candidate review, draft edit. Row with text input, ingredient DB search/select, quantity, unit, add/remove/reorder. Provenance indicator variant for review screen.

**Step editor** — Used in: recipe edit, candidate review, draft edit. Ordered textarea rows with image attachment, add/remove/reorder.

**Tag selector** — Used in: recipe edit, candidate review, draft edit, journal composer, search filters. Multi-select with domain-scoped tag list and create-new inline.

**Journal entry card** — Used in: recipe detail. Body, cooked-on date, tags, images, timestamp, delete action.

**Journal composer** — Used in: recipe detail. Text input, date picker, tag selector, image upload (max 2), submit.

**Source preview card** — Used in: ingestion progress, candidate review. Shows URL card, image thumbnail, or text excerpt depending on source type.

**Review finding card** — Used in: candidate review. Severity icon, message, field reference, clickable.

**Filter bar** — Used in: library, search, artifact library. Status toggle, tag filter, sort, search input. Composable with different filter configurations per screen.

**Image upload area** — Used in: ingestion entry (image tab), recipe edit, journal composer. Drag-and-drop, presigned URL flow, preview.

**Confirmation dialog** — Used across screens for destructive actions (delete, discard, restore).

**Toast notifications** — Used across screens for success/error feedback.

---

## 5. State management patterns

**Server state (TanStack Query):** All API data. Recipe lists, recipe detail, candidates, jobs, journal entries, tags, ingredients, artifacts, pantry. Shared query keys enable cross-screen cache consistency (editing a recipe invalidates the library cache).

**Form state (React Hook Form):** Recipe edit, candidate review, draft edit, create flows. Complex forms with dynamic rows (ingredients, steps) and validation.

**SSE state (custom hook):** Ingestion progress. A `useIngestionSSE(jobId)` hook subscribes to the SSE endpoint, updates a local state machine, and can also update the TanStack Query cache for the job snapshot.

**URL state:** Active filters on library and search screens persist in URL query params for shareability and back-button support.

**No global store needed in Phase 1.** TanStack Query + React Hook Form + URL params + occasional `useState` covers everything. Zustand or similar only if a genuine cross-screen UI state need emerges (unlikely).

---

## 6. Key navigation flows

### Ingestion → save flow
```
/ingest → submit → /ingest/[jobId] → SSE progress → "Review" → /ingest/[jobId]/review → "Save as trusted" → /recipes/[newId]
```

### Ingestion → draft → promote flow
```
/ingest → ... → /ingest/[jobId]/review → "Save as draft" → /drafts/[newId] → edit → "Review for trusted save" → /drafts/[id]/promote → /recipes/[newId]
```

### Search → ask flow (Phase 2)
```
/search → type question → recognize ask intent → redirect to /ask → response → /ask/[sessionId]
```

### Pantry → cook flow (Phase 2)
```
/pantry → "What can I cook?" → /pantry/feasibility → click feasible recipe → /recipes/[id]
```

### Create → artifact flow (Phase 2)
```
/create → "Shopping list" → /create/shopping-list/new → select recipes → generate → save → /artifacts/[newId]
```
