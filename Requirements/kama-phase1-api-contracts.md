# Kama — Phase 1 API Contracts

**Version:** 1.0  
**Base URL:** `/api`  
**Auth:** All endpoints require a valid Clerk JWT in the `Authorization: Bearer <token>` header.  
**Content type:** `application/json` unless noted otherwise.  
**Date format:** ISO 8601 (`2026-03-22T18:00:00Z`). Date-only fields use `YYYY-MM-DD`.

---

## 1. Ingestion

### 1.1 Submit source

Starts a new ingestion. Creates a SourceAsset and queues an IngestionJob.

```
POST /api/ingestion
```

**Request body**

```json
{
  "sourceType": "url",
  "url": "https://youtube.com/watch?v=abc123",
  "contextNote": "Pasta recipe from Ana's channel"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `sourceType` | `"url" \| "image" \| "text"` | Yes | |
| `url` | `string` | If `sourceType = "url"` | The URL to ingest |
| `fileAssetRef` | `string` | If `sourceType = "image"` | S3 key from presigned upload |
| `rawTextInput` | `string` | If `sourceType = "text"` | Pasted recipe text |
| `contextNote` | `string` | No | Optional user context |

**Response `201 Created`**

```json
{
  "sourceAssetId": "src_4812",
  "ingestionJobId": "job_1024",
  "status": "queued",
  "sseUrl": "/api/ingestion/jobs/job_1024/events"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing required field for the given `sourceType` |
| `422` | Invalid URL format, empty text input, or missing file reference |

---

### 1.2 Get job status

Fetch the current snapshot of an ingestion job. Used for initial page load, reconnection after SSE drop, and direct link access.

```
GET /api/ingestion/jobs/{jobId}
```

**Response `200 OK`**

```json
{
  "id": "job_1024",
  "sourceAssetId": "src_4812",
  "status": "review_ready",
  "internalState": "completed",
  "internalErrorState": null,
  "processorFamily": "url",
  "processorVariant": "youtube_linked_recipe_fallback",
  "reviewMode": "standard",
  "candidateId": "cand_7781",
  "normalizedArtifactIds": ["norm_101", "norm_102", "norm_103"],
  "errorType": null,
  "errorCode": null,
  "rerunAllowed": false,
  "userRecoverable": true,
  "extractionPlan": [
    {
      "methodKey": "recipe_link_from_description",
      "priority": 1,
      "feasible": true,
      "feasibilityReason": "Linked recipe URL found in description",
      "requiredArtifacts": ["norm_102"],
      "status": "succeeded",
      "startedAt": "2026-03-22T18:00:06Z",
      "completedAt": "2026-03-22T18:00:08Z",
      "outputSummary": {
        "candidateCreated": true,
        "canonicalEligible": true,
        "draftEligible": true,
        "confidenceLevel": "high",
        "notes": ["Candidate produced from linked recipe page"]
      },
      "failure": null,
      "stopDecision": {
        "stopPipeline": true,
        "reason": "Canonical-eligible candidate created"
      }
    },
    {
      "methodKey": "transcript_extraction",
      "priority": 5,
      "feasible": true,
      "feasibilityReason": "Transcript available",
      "requiredArtifacts": ["norm_103"],
      "status": "skipped",
      "startedAt": null,
      "completedAt": null,
      "outputSummary": null,
      "failure": null,
      "stopDecision": null
    }
  ],
  "stateHistory": [
    { "eventType": "state_changed", "timestamp": "2026-03-22T18:00:01Z", "internalState": "source_received" },
    { "eventType": "state_changed", "timestamp": "2026-03-22T18:00:04Z", "internalState": "source_normalization" },
    { "eventType": "plan_built", "timestamp": "2026-03-22T18:00:05Z" },
    { "eventType": "method_started", "timestamp": "2026-03-22T18:00:06Z", "methodKey": "recipe_link_from_description" },
    { "eventType": "method_succeeded", "timestamp": "2026-03-22T18:00:08Z", "methodKey": "recipe_link_from_description" },
    { "eventType": "job_completed", "timestamp": "2026-03-22T18:00:09Z", "status": "review_ready" }
  ],
  "metadata": {
    "sourceSubtypeDetected": "youtube_video",
    "selectedExtractionMethod": "recipe_link_from_description"
  },
  "createdAt": "2026-03-22T18:00:01Z",
  "startedAt": "2026-03-22T18:00:02Z",
  "completedAt": "2026-03-22T18:00:09Z",
  "updatedAt": "2026-03-22T18:00:09Z",
  "lastHeartbeatAt": "2026-03-22T18:00:08Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Job not found or does not belong to authenticated user |

---

### 1.3 SSE — Job progress events

Subscribe to realtime ingestion progress. Server-Sent Events stream.

```
GET /api/ingestion/jobs/{jobId}/events
```

**Headers**

```
Accept: text/event-stream
```

**Event format**

Each SSE message is a JSON payload:

```
event: job.state_changed
data: {"eventType":"job.state_changed","jobId":"job_1024","sequence":2,"timestamp":"2026-03-22T18:00:04Z","status":"processing","internalState":"source_normalization"}

event: job.method_started
data: {"eventType":"job.method_started","jobId":"job_1024","sequence":4,"timestamp":"2026-03-22T18:00:06Z","status":"processing","methodKey":"recipe_link_from_description"}

event: job.review_ready
data: {"eventType":"job.review_ready","jobId":"job_1024","sequence":6,"timestamp":"2026-03-22T18:00:09Z","status":"review_ready","candidateId":"cand_7781"}
```

**Event types**

| Event | When emitted |
|---|---|
| `job.started` | Job begins processing |
| `job.state_changed` | Pipeline moves to a new internal stage |
| `job.plan_built` | Initial extraction plan assembled |
| `job.plan_modified` | Agent modified the plan based on intermediate results |
| `job.tool_called` | Agent is executing a tool |
| `job.tool_succeeded` | A tool completed successfully |
| `job.tool_failed` | A tool failed (agent may continue with different tool) |
| `job.agent_reasoning` | Agent made an LLM-assisted decision (includes reasoning text) |
| `job.candidate_created` | First recipe candidate assembled |
| `job.candidate_improved` | Agent improved candidate with additional data |
| `job.review_agent_started` | Review agent has begun verifying and enriching the candidate |
| `job.review_agent_tool_called` | Review agent is executing a tool (ingredient lookup, gap filling, etc.) |
| `job.review_agent_completed` | Review agent finished; includes summary of changes |
| `job.review_ready` | Canonical-eligible candidate ready for review |
| `job.draft_ready` | Draft-only candidate ready for review |
| `job.failed` | Job terminated due to error |
| `job.unsupported` | Source could not produce a usable recipe |

**SSE event payload**

| Field | Type | Always present | Notes |
|---|---|---|---|
| `eventType` | `string` | Yes | One of the event types above |
| `jobId` | `string` | Yes | |
| `sequence` | `number` | Yes | Monotonically increasing per job |
| `timestamp` | `string` | Yes | ISO 8601 |
| `status` | `string` | Yes | Current user-facing job status |
| `internalState` | `string` | No | Current pipeline stage |
| `methodKey` | `string` | No | For tool-level events |
| `candidateId` | `string` | No | Set on `review_ready` / `draft_ready` |
| `rerunAllowed` | `boolean` | No | Set on `failed` |
| `errorType` | `string` | No | Set on `failed` / `unsupported` |
| `errorCode` | `string` | No | Machine-readable error detail |
| `reasoning` | `string` | No | Agent's reasoning text (for `agent_reasoning` events) |

**Reconnection:** On disconnect, client calls `GET /api/ingestion/jobs/{jobId}` to get current snapshot and resumes.

---

### 1.4 Rerun job

Re-trigger the full ingestion pipeline. Only valid when `rerunAllowed = true` (internal/server failures only). Creates a new IngestionJob against the same SourceAsset.

```
POST /api/ingestion/jobs/{jobId}/rerun
```

**Request body:** None.

**Response `201 Created`**

```json
{
  "originalJobId": "job_1024",
  "newJobId": "job_1025",
  "sourceAssetId": "src_4812",
  "status": "queued",
  "sseUrl": "/api/ingestion/jobs/job_1025/events"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Job not found |
| `409` | Rerun not allowed (`rerunAllowed = false`) |

---

## 2. Recipe candidates

### 2.1 Get candidate for review

Fetch the full candidate payload for the review screen. Includes structured recipe fields, review findings, provenance, confidence, and supporting source context.

```
GET /api/recipe-candidates/{candidateId}
```

**Response `200 OK`**

```json
{
  "id": "cand_7781",
  "sourceAssetId": "src_4812",
  "ingestionJobId": "job_1024",
  "title": "Easy One Pot Pasta",
  "ingredients": [
    { "text": "8 oz pasta", "ingredientId": "ing_042", "quantity": "8", "unit": "oz" },
    { "text": "2 cloves garlic, minced", "ingredientId": "ing_011", "quantity": "2", "unit": "cloves" },
    { "text": "2 cups cherry tomatoes", "ingredientId": "ing_087", "quantity": "2", "unit": "cups" },
    { "text": "2 tbsp olive oil", "ingredientId": "ing_003", "quantity": "2", "unit": "tbsp" }
  ],
  "steps": [
    { "order": 1, "text": "Heat olive oil in a large pot.", "mediaRefs": [] },
    { "order": 2, "text": "Add garlic and tomatoes, cook 3 minutes.", "mediaRefs": ["media_201"] },
    { "order": 3, "text": "Add pasta and water, simmer until cooked.", "mediaRefs": [] }
  ],
  "description": "Quick one-pot pasta recipe from Cooking With Ana.",
  "prepTimeMinutes": 10,
  "cookTimeMinutes": 20,
  "servings": 2,
  "recipeTags": ["tag_under30", "tag_onepot"],
  "canonicalEligible": true,
  "draftEligible": true,
  "reviewMode": "standard",
  "reviewFindings": [
    {
      "code": "INFERRED_PREP_TIME",
      "severity": "info",
      "field": "prepTimeMinutes",
      "message": "Prep time estimated from source text, not explicitly stated.",
      "sourceArtifactId": "norm_101"
    },
    {
      "code": "POSSIBLE_MISSING_INGREDIENT",
      "severity": "warning",
      "field": "ingredients",
      "message": "Source may contain additional ingredients not captured.",
      "sourceArtifactId": null
    }
  ],
  "fieldConfidenceMap": {
    "title": "high",
    "ingredients": "high",
    "steps": "high",
    "prepTimeMinutes": "medium",
    "cookTimeMinutes": "medium"
  },
  "fieldProvenanceMap": {
    "title": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": "Extracted from page heading"
    },
    "ingredients": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": null
    },
    "steps": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": "Primary extraction source"
    },
    "prepTimeMinutes": {
      "sourceType": "review_agent_enriched",
      "artifactId": "norm_220",
      "note": "Found in source text by review agent: '10 minutes prep'"
    }
  },
  "selectedExtractionMethod": "recipe_link_from_description",
  "sourceArtifactIds": ["norm_101", "norm_102", "norm_220"],
  "sourceContext": {
    "sourceType": "url",
    "sourceSubtype": "youtube_video",
    "sourcePreview": {
      "previewKind": "link_card",
      "title": "Easy One Pot Pasta",
      "subtitle": "YouTube · Cooking With Ana",
      "imageUrl": "https://img.youtube.com/vi/abc123/maxresdefault.jpg",
      "sourceUrl": "https://youtube.com/watch?v=abc123",
      "summaryText": "Used linked recipe page from description"
    },
    "provenanceMessages": [
      "Recipe extracted from linked page in video description",
      "Prep time estimated from source text"
    ]
  },
  "allowedActions": {
    "canSaveCanonical": true,
    "canSaveDraft": true,
    "canDiscard": true
  },
  "reviewAgentSummary": {
    "ran": true,
    "fieldsEnriched": ["prepTimeMinutes"],
    "ingredientsMapped": 3,
    "findingsResolved": 1,
    "findingsAdded": 1,
    "totalToolCalls": 5,
    "durationMs": 4200
  },
  "createdAt": "2026-03-22T18:00:08Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Candidate not found |

---

### 2.2 Submit review decision

Save as canonical, save as draft, or discard. Includes any edits the user made during review.

```
POST /api/recipe-candidates/{candidateId}/decision
```

**Request body**

```json
{
  "action": "save_canonical",
  "editedFields": {
    "title": "Easy One Pot Pasta",
    "ingredients": [
      { "text": "8 oz penne pasta", "ingredientId": "ing_042", "quantity": "8", "unit": "oz" },
      { "text": "3 cloves garlic, minced", "ingredientId": "ing_011", "quantity": "3", "unit": "cloves" },
      { "text": "2 cups cherry tomatoes", "ingredientId": "ing_087", "quantity": "2", "unit": "cups" },
      { "text": "2 tbsp olive oil", "ingredientId": "ing_003", "quantity": "2", "unit": "tbsp" },
      { "text": "Salt to taste", "ingredientId": "ing_001", "quantity": null, "unit": null }
    ],
    "steps": [
      { "order": 1, "text": "Heat olive oil in a large pot.", "mediaRefs": [] },
      { "order": 2, "text": "Add garlic and tomatoes, cook 3 minutes.", "mediaRefs": ["media_201"] },
      { "order": 3, "text": "Add pasta and water, simmer until cooked.", "mediaRefs": [] }
    ],
    "description": "Quick one-pot pasta recipe.",
    "prepTimeMinutes": 10,
    "cookTimeMinutes": 20,
    "servings": 2
  },
  "recipeTags": ["tag_under30", "tag_onepot", "tag_vegetarian"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `action` | `"save_canonical" \| "save_draft" \| "discard"` | Yes | |
| `editedFields` | `object` | If action ≠ `discard` | Full structured content (not a diff) |
| `recipeTags` | `string[]` | No | Tag IDs to apply |

**Response `200 OK` — save_canonical**

```json
{
  "action": "save_canonical",
  "canonicalRecipeId": "rec_501",
  "draftRecipeId": null
}
```

**Response `200 OK` — save_draft**

```json
{
  "action": "save_draft",
  "canonicalRecipeId": null,
  "draftRecipeId": "draft_301"
}
```

**Response `200 OK` — discard**

```json
{
  "action": "discard",
  "canonicalRecipeId": null,
  "draftRecipeId": null
}
```

**Error responses**

| Status | Condition |
|---|---|
| `400` | Missing `editedFields` for non-discard action |
| `404` | Candidate not found |
| `409` | Candidate already has a decision |
| `422` | Edited fields fail canonical eligibility (missing title/ingredients/steps) when action is `save_canonical` |

---

## 3. Drafts

### 3.1 Get draft

```
GET /api/drafts/{draftId}
```

**Response `200 OK`**

```json
{
  "id": "draft_301",
  "userId": "user_17",
  "originSourceAssetId": "src_4812",
  "originRecipeCandidateId": "cand_7781",
  "title": "Chicken Curry",
  "ingredients": [
    { "text": "500g chicken thigh", "ingredientId": "ing_120", "quantity": "500", "unit": "g" },
    { "text": "Curry paste", "ingredientId": null, "quantity": null, "unit": null }
  ],
  "steps": [
    { "order": 1, "text": "Marinate chicken in curry paste.", "mediaRefs": [] }
  ],
  "description": null,
  "prepTimeMinutes": null,
  "cookTimeMinutes": null,
  "servings": null,
  "recipeTags": ["tag_indian"],
  "promotionEligible": false,
  "createdAt": "2026-03-22T19:00:00Z",
  "updatedAt": "2026-03-22T19:00:00Z"
}
```

---

### 3.2 Update draft

```
PATCH /api/drafts/{draftId}
```

**Request body** — partial update; include only the fields being changed.

```json
{
  "title": "Mom's Chicken Curry",
  "ingredients": [
    { "text": "500g chicken thigh, cubed", "ingredientId": "ing_120", "quantity": "500", "unit": "g" },
    { "text": "2 tbsp curry paste", "ingredientId": "ing_310", "quantity": "2", "unit": "tbsp" },
    { "text": "1 can coconut milk", "ingredientId": "ing_045", "quantity": "1", "unit": "can" }
  ],
  "steps": [
    { "order": 1, "text": "Marinate chicken in curry paste for 30 minutes.", "mediaRefs": [] },
    { "order": 2, "text": "Sauté marinated chicken until browned.", "mediaRefs": [] },
    { "order": 3, "text": "Add coconut milk and simmer 20 minutes.", "mediaRefs": [] }
  ],
  "cookTimeMinutes": 50,
  "recipeTags": ["tag_indian", "tag_comfort"]
}
```

**Response `200 OK`**

Returns the full updated DraftRecipe object (same shape as GET response), with `promotionEligible` recalculated.

**Error responses**

| Status | Condition |
|---|---|
| `404` | Draft not found |
| `422` | Invalid field values |

---

### 3.3 Request promotion review

Triggers the promotion assessment pipeline. System re-evaluates whether the draft meets canonical eligibility and returns a review payload.

```
POST /api/drafts/{draftId}/review-for-canonical
```

**Request body:** None.

**Response `200 OK`**

```json
{
  "draftId": "draft_301",
  "promotionEligible": true,
  "reviewFindings": [
    {
      "code": "INGREDIENT_UNMAPPED",
      "severity": "info",
      "field": "ingredients",
      "message": "1 ingredient has no canonical mapping.",
      "sourceArtifactId": null
    }
  ],
  "allowedActions": {
    "canPromote": true,
    "canContinueEditing": true
  }
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Draft not found |
| `409` | Draft does not meet minimum required fields (title, ≥1 ingredient, ≥1 step) |

---

### 3.4 Confirm promotion

Promotes draft to canonical recipe. Deletes the draft. Preserves lightweight promotion metadata on the new canonical recipe.

```
POST /api/drafts/{draftId}/promote
```

**Request body** — optional final edits before promotion.

```json
{
  "editedFields": {
    "title": "Mom's Chicken Curry",
    "servings": 4
  },
  "recipeTags": ["tag_indian", "tag_comfort", "tag_family"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `editedFields` | `object` | No | Partial updates applied before promotion |
| `recipeTags` | `string[]` | No | Final tag set |

**Response `201 Created`**

```json
{
  "canonicalRecipeId": "rec_502",
  "promotedFromDraftId": "draft_301",
  "promotedAt": "2026-03-22T20:15:00Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Draft not found |
| `409` | Promotion review not completed (must call `review-for-canonical` first) |
| `422` | Final state does not meet canonical eligibility |

---

## 4. Recipes

### 4.1 List recipes

```
GET /api/recipes
```

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `status` | `"all" \| "canonical" \| "draft"` | `"all"` | Filter by recipe status. `"all"` includes both canonical and drafts. |
| `tags` | `string` | — | Comma-separated tag IDs. Returns recipes matching any of these tags. |
| `search` | `string` | — | Free-text search against title and description. |
| `sort` | `"created_desc" \| "created_asc" \| "updated_desc" \| "title_asc"` | `"updated_desc"` | |
| `cursor` | `string` | — | Pagination cursor from previous response |
| `limit` | `number` | `20` | Max 50 |

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "rec_501",
      "type": "canonical",
      "title": "Easy One Pot Pasta",
      "description": "Quick one-pot pasta recipe.",
      "prepTimeMinutes": 10,
      "cookTimeMinutes": 20,
      "servings": 2,
      "heroImageUrl": "https://cdn.kama.app/media/hero_501.jpg",
      "recipeTags": [
        { "id": "tag_under30", "name": "under 30 mins" },
        { "id": "tag_onepot", "name": "one pot" }
      ],
      "journalEntryCount": 3,
      "createdAt": "2026-03-22T18:10:00Z",
      "updatedAt": "2026-03-22T19:30:00Z"
    },
    {
      "id": "draft_301",
      "type": "draft",
      "title": "Mom's Chicken Curry",
      "description": null,
      "prepTimeMinutes": null,
      "cookTimeMinutes": 50,
      "servings": null,
      "heroImageUrl": null,
      "recipeTags": [
        { "id": "tag_indian", "name": "indian" }
      ],
      "journalEntryCount": 0,
      "createdAt": "2026-03-22T19:00:00Z",
      "updatedAt": "2026-03-22T19:45:00Z"
    }
  ],
  "nextCursor": "eyJjIjoiMjAyNi0wMy0yMlQxOTowMDowMFoifQ",
  "hasMore": true
}
```

---

### 4.2 Get recipe detail

```
GET /api/recipes/{recipeId}
```

**Response `200 OK`**

```json
{
  "id": "rec_501",
  "userId": "user_17",
  "title": "Easy One Pot Pasta",
  "ingredients": [
    { "text": "8 oz penne pasta", "ingredientId": "ing_042", "quantity": "8", "unit": "oz" },
    { "text": "3 cloves garlic, minced", "ingredientId": "ing_011", "quantity": "3", "unit": "cloves" },
    { "text": "2 cups cherry tomatoes", "ingredientId": "ing_087", "quantity": "2", "unit": "cups" },
    { "text": "2 tbsp olive oil", "ingredientId": "ing_003", "quantity": "2", "unit": "tbsp" },
    { "text": "Salt to taste", "ingredientId": "ing_001", "quantity": null, "unit": null }
  ],
  "steps": [
    { "order": 1, "text": "Heat olive oil in a large pot.", "mediaRefs": [] },
    { "order": 2, "text": "Add garlic and tomatoes, cook 3 minutes.", "mediaRefs": ["media_201"] },
    { "order": 3, "text": "Add pasta and water, simmer until cooked.", "mediaRefs": [] }
  ],
  "description": "Quick one-pot pasta recipe.",
  "prepTimeMinutes": 10,
  "cookTimeMinutes": 20,
  "servings": 2,
  "recipeTags": [
    { "id": "tag_under30", "name": "under 30 mins" },
    { "id": "tag_onepot", "name": "one pot" },
    { "id": "tag_vegetarian", "name": "vegetarian" }
  ],
  "heroImage": {
    "id": "media_101",
    "role": "hero",
    "url": "https://cdn.kama.app/media/hero_501.jpg"
  },
  "gallery": [
    {
      "id": "media_201",
      "role": "step_reference",
      "url": "https://cdn.kama.app/media/step_201.jpg",
      "displayOrder": 1
    }
  ],
  "fieldProvenanceMap": {
    "title": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": "Extracted from page heading"
    },
    "ingredients": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": null
    },
    "steps": {
      "sourceType": "linked_recipe_page",
      "artifactId": "norm_220",
      "note": "Primary extraction source"
    }
  },
  "nutrition": {
    "calories": "450 kcal",
    "servingSize": "1 serving",
    "carbohydrates": "55 g",
    "protein": "12 g",
    "fat": "18 g",
    "saturatedFat": "3 g",
    "sodium": "200 mg",
    "fiber": "4 g",
    "sugar": "6 g"
  },
  "notes": [
    { "type": "tip", "text": "Use penne or fusilli for best results." },
    { "type": "storage", "text": "Store leftovers in an airtight container for up to 3 days." },
    { "type": "substitution", "text": "Swap cherry tomatoes for sun-dried tomatoes for a richer flavour." }
  ],
  "sourceAssetId": "src_4812",
  "promotedFromDraft": false,
  "journalSummary": "Family favorite weeknight dinner. Kids always finish it. Works well with penne or fusilli instead of default pasta. Added chili flakes once — too spicy for kids, stick with mild version. Less oil works fine.",
  "revisionCount": 1,
  "journalEntryCount": 3,
  "createdAt": "2026-03-22T18:10:00Z",
  "updatedAt": "2026-03-22T19:30:00Z"
}
```

---

### 4.3 Edit recipe

Partial update. Backend determines whether changes are revision-worthy.

```
PATCH /api/recipes/{recipeId}
```

**Request body** — include only the fields being changed.

```json
{
  "title": "Easy One Pot Penne Pasta",
  "servings": 3,
  "recipeTags": ["tag_under30", "tag_onepot", "tag_vegetarian", "tag_familyfav"],
  "nutrition": { "calories": "500 kcal", "protein": "14 g" },
  "notes": [{ "type": "tip", "text": "Add chili flakes for extra heat." }]
}
```

**Response `200 OK`**

```json
{
  "id": "rec_501",
  "revisionCreated": true,
  "revisionId": "rev_101",
  "updatedAt": "2026-03-23T10:00:00Z"
}
```

| Field | Notes |
|---|---|
| `revisionCreated` | `true` if meaningful content changed (title, ingredients, steps, times, servings). `false` for tag-only changes. |
| `revisionId` | Set only if `revisionCreated = true` |

**Error responses**

| Status | Condition |
|---|---|
| `404` | Recipe not found |
| `422` | Edit would remove required fields (empty title, zero ingredients, zero steps) |

---

### 4.4 List revision history

```
GET /api/recipes/{recipeId}/revisions
```

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "rev_101",
      "canonicalRecipeId": "rec_501",
      "changeSummary": "Title updated, servings changed from 2 to 3",
      "createdAt": "2026-03-23T10:00:00Z"
    }
  ]
}
```

---

### 4.5 Restore revision

Restores a previous version as the new current state. Creates a new revision (non-destructive).

```
POST /api/recipes/{recipeId}/revisions/{revisionId}/restore
```

**Request body:** None.

**Response `200 OK`**

```json
{
  "recipeId": "rec_501",
  "restoredFromRevisionId": "rev_101",
  "newRevisionId": "rev_102",
  "updatedAt": "2026-03-23T12:00:00Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Recipe or revision not found |

---

## 5. Media

### 5.1 Get presigned upload URL

Generates a presigned S3 URL for direct client upload.

```
POST /api/media/presigned-url
```

**Request body**

```json
{
  "fileName": "recipe_photo.jpg",
  "contentType": "image/jpeg",
  "context": "recipe_media"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `fileName` | `string` | Yes | Original filename |
| `contentType` | `string` | Yes | MIME type |
| `context` | `"recipe_media" \| "journal_media" \| "source_upload"` | Yes | Determines S3 path prefix |

**Response `200 OK`**

```json
{
  "uploadUrl": "https://s3.amazonaws.com/kama-uploads/...",
  "assetRef": "uploads/user_17/recipe_media/abc123_recipe_photo.jpg",
  "expiresAt": "2026-03-22T18:15:00Z"
}
```

---

### 5.2 Register media on recipe

After uploading to S3, register the media record.

```
POST /api/recipes/{recipeId}/media
```

**Request body**

```json
{
  "assetRef": "uploads/user_17/recipe_media/abc123_recipe_photo.jpg",
  "role": "user_added_gallery",
  "displayOrder": 3
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `assetRef` | `string` | Yes | S3 key from presigned upload |
| `role` | `"hero" \| "source_gallery" \| "step_reference" \| "user_added_gallery"` | Yes | |
| `displayOrder` | `number` | No | For gallery ordering |

**Response `201 Created`**

```json
{
  "id": "media_301",
  "canonicalRecipeId": "rec_501",
  "mediaType": "image",
  "role": "user_added_gallery",
  "source": "uploaded",
  "assetRef": "uploads/user_17/recipe_media/abc123_recipe_photo.jpg",
  "url": "https://cdn.kama.app/media/abc123_recipe_photo.jpg",
  "displayOrder": 3,
  "createdAt": "2026-03-22T19:00:00Z"
}
```

---

### 5.3 Update media

Change role or display order. Primary use: setting a gallery image as hero.

```
PATCH /api/recipes/{recipeId}/media/{mediaId}
```

**Request body**

```json
{
  "role": "hero"
}
```

**Response `200 OK`** — Updated media object.

**Side effect:** If setting a new hero, the previous hero image is demoted to `source_gallery` or `user_added_gallery` (based on its `source` field).

---

### 5.4 Delete media

```
DELETE /api/recipes/{recipeId}/media/{mediaId}
```

**Response `204 No Content`**

**Error responses**

| Status | Condition |
|---|---|
| `404` | Media not found |
| `409` | Cannot delete the only hero image (user must set another first, or this can be relaxed) |

---

## 6. Cook journal

### 6.1 List journal entries

```
GET /api/recipes/{recipeId}/journal
```

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `cursor` | `string` | — | Pagination cursor |
| `limit` | `number` | `20` | Max 50 |

**Response `200 OK`** — Newest first.

```json
{
  "items": [
    {
      "id": "journal_401",
      "canonicalRecipeId": "rec_501",
      "userId": "user_17",
      "body": "Used less oil this time, worked great. Kids loved it.",
      "cookedOn": "2026-03-20",
      "tags": [
        { "id": "jtag_success", "name": "success" },
        { "id": "jtag_tweak", "name": "tweak" }
      ],
      "media": [
        {
          "id": "jmedia_101",
          "url": "https://cdn.kama.app/journal/jmedia_101.jpg",
          "displayOrder": 1
        }
      ],
      "createdAt": "2026-03-21T08:00:00Z"
    }
  ],
  "nextCursor": null,
  "hasMore": false
}
```

---

### 6.2 Create journal entry

```
POST /api/recipes/{recipeId}/journal
```

**Request body**

```json
{
  "body": "Added chili flakes for extra heat. Took 5 mins longer than expected.",
  "cookedOn": "2026-03-22",
  "tags": ["jtag_tweak", "jtag_timing"],
  "mediaRefs": [
    "uploads/user_17/journal_media/dish_photo.jpg"
  ]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `body` | `string` | Yes | Freeform text |
| `cookedOn` | `string` | No | `YYYY-MM-DD` format |
| `tags` | `string[]` | No | Journal-domain tag IDs |
| `mediaRefs` | `string[]` | No | S3 keys from presigned upload. Max 2. |

**Response `201 Created`**

```json
{
  "id": "journal_402",
  "canonicalRecipeId": "rec_501",
  "body": "Added chili flakes for extra heat. Took 5 mins longer than expected.",
  "cookedOn": "2026-03-22",
  "tags": [
    { "id": "jtag_tweak", "name": "tweak" },
    { "id": "jtag_timing", "name": "timing note" }
  ],
  "media": [
    {
      "id": "jmedia_201",
      "url": "https://cdn.kama.app/journal/dish_photo.jpg",
      "displayOrder": 1
    }
  ],
  "createdAt": "2026-03-22T20:00:00Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Recipe not found |
| `422` | Empty body, or more than 2 media refs |

---

### 6.3 Delete journal entry

Hard delete. Removes entry and associated media records.

```
DELETE /api/journal/{entryId}
```

**Response `204 No Content`**

**Error responses**

| Status | Condition |
|---|---|
| `404` | Entry not found |

---

## 7. Tags

### 7.1 List tags by domain

```
GET /api/tags?domain=recipe
```

| Param | Type | Required | Notes |
|---|---|---|---|
| `domain` | `"recipe" \| "journal"` | Yes | |
| `search` | `string` | No | Filter by name substring |

**Response `200 OK`**

```json
{
  "items": [
    { "id": "tag_under30", "domain": "recipe", "name": "under 30 mins", "createdBySystem": true },
    { "id": "tag_onepot", "domain": "recipe", "name": "one pot", "createdBySystem": true },
    { "id": "tag_familyfav", "domain": "recipe", "name": "family favorite", "createdBySystem": false }
  ]
}
```

---

### 7.2 Create or reuse tag

If a tag with the same name exists in the given domain, returns the existing tag. Otherwise creates a new one.

```
POST /api/tags
```

**Request body**

```json
{
  "domain": "journal",
  "name": "too spicy"
}
```

**Response `200 OK`** (existing tag found)

```json
{
  "id": "jtag_toospicy",
  "domain": "journal",
  "name": "too spicy",
  "createdBySystem": false,
  "created": false
}
```

**Response `201 Created`** (new tag)

```json
{
  "id": "jtag_toospicy",
  "domain": "journal",
  "name": "too spicy",
  "createdBySystem": false,
  "createdByUserId": "user_17",
  "created": true,
  "createdAt": "2026-03-22T20:30:00Z"
}
```

The `created` field tells the client whether this was a new tag or existing match.

---

## 8. Ingredients

### 8.1 Search ingredients

```
GET /api/ingredients?search=garl
```

| Param | Type | Required | Notes |
|---|---|---|---|
| `search` | `string` | Yes | Searches canonical name and aliases |
| `category` | `IngredientCategory` | No | Filter results by category (e.g. `produce`, `dairy`) |
| `limit` | `number` | No | Default 10, max 50 |

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "ing_011",
      "name": "garlic",
      "aliases": ["garlic cloves", "fresh garlic"],
      "category": "produce",
      "matchConfidence": "exact",
      "notes": null
    },
    {
      "id": "ing_310",
      "name": "garlic powder",
      "aliases": ["powdered garlic"],
      "category": "spices_seasoning",
      "matchConfidence": "exact",
      "notes": null
    }
  ]
}
```

---

### 8.2 Create ingredient

Used during review when user maps a recipe line to a new ingredient not in the DB.

```
POST /api/ingredients
```

**Request body**

```json
{
  "name": "gochujang",
  "category": "canned_jarred",
  "aliases": ["korean chili paste", "red pepper paste"],
  "notes": "Fermented Korean condiment"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | `string` | Yes | Canonical display name |
| `category` | `IngredientCategory` | Yes | One of the 12 category values |
| `aliases` | `string[]` | No | Alternative names |
| `notes` | `string` | No | |

**Response `201 Created`**

```json
{
  "id": "ing_512",
  "name": "gochujang",
  "category": "canned_jarred",
  "aliases": ["korean chili paste", "red pepper paste"],
  "notes": "Fermented Korean condiment",
  "createdBySystem": false,
  "createdByUserId": "user_17",
  "createdAt": "2026-03-22T21:00:00Z"
}
```

**Error responses**

| Status | Condition |
|---|---|
| `409` | Ingredient with same canonical name already exists |
| `422` | Invalid `category` value |

---

### 8.3 Update ingredient aliases

```
PATCH /api/ingredients/{ingredientId}
```

**Request body** — partial update.

```json
{
  "aliases": ["korean chili paste", "red pepper paste", "gochujang paste"],
  "category": "spices_seasoning"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `aliases` | `string[]` | No | Replace alias list |
| `category` | `IngredientCategory` | No | Update category |

**Response `200 OK`** — Updated ingredient object.

**Error responses**

| Status | Condition |
|---|---|
| `404` | Ingredient not found |
| `422` | Invalid `category` value |

---

## 9. Common response patterns

### Error response shape

All error responses follow a consistent structure:

```json
{
  "error": {
    "code": "CANONICAL_ELIGIBILITY_FAILED",
    "message": "Recipe must have a title, at least one ingredient, and at least one step.",
    "details": {
      "missingFields": ["title"]
    }
  }
}
```

| Field | Type | Notes |
|---|---|---|
| `error.code` | `string` | Machine-readable error code |
| `error.message` | `string` | Human-readable message |
| `error.details` | `object` | Optional structured detail |

### Pagination

List endpoints use cursor-based pagination:

```json
{
  "items": [...],
  "nextCursor": "eyJjIjoiMjAyNi...",
  "hasMore": true
}
```

Pass `nextCursor` as the `cursor` query parameter to fetch the next page.

### Timestamps

All timestamps are ISO 8601 UTC. Date-only fields (e.g. `cookedOn`) use `YYYY-MM-DD`.
