# Kama — Phase 2 API Contracts

**Version:** 1.0  
**Base URL:** `/api`  
**Auth:** All endpoints require Clerk JWT in `Authorization: Bearer <token>`.  
**Standards:** Same as Phase 1 — JSON, ISO 8601 timestamps, cursor pagination, standard error shape.

---

## 1. Search

### 1.1 Search recipes

Hybrid search combining structured filters with semantic matching.

```
POST /api/search
```

**Why POST not GET:** The query payload can be complex (filters + semantic text + options). POST avoids URL length limits and is cleaner for structured bodies.

**Request body**

```json
{
  "query": "quick vegetarian pasta the kids will like",
  "filters": {
    "tagIds": ["tag_vegetarian"],
    "maxCookTimeMinutes": 30,
    "ingredientIds": ["ing_042"]
  },
  "limit": 20,
  "cursor": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `query` | `string` | No | Natural language search text. If empty, only filters apply. |
| `filters` | `object` | No | Structured filters (all optional within) |
| `filters.tagIds` | `string[]` | No | Match recipes with any of these tags |
| `filters.ingredientIds` | `string[]` | No | Match recipes containing these ingredients |
| `filters.maxCookTimeMinutes` | `number` | No | Upper bound on cook time |
| `filters.maxPrepTimeMinutes` | `number` | No | Upper bound on prep time |
| `filters.minServings` | `number` | No | |
| `filters.maxServings` | `number` | No | |
| `limit` | `number` | No | Default 20, max 50 |
| `cursor` | `string` | No | Pagination cursor |

**Backend behavior:**

If `query` is provided, the system uses LLM-assisted query parsing to extract any additional structured filters from the text (e.g. "under 30 min" → `maxCookTimeMinutes: 30`) and a cleaned semantic query string. These are merged with any explicitly provided filters.

The semantic query is then used to generate both a dense embedding (OpenAI text-embedding-3-small) and a BM25 sparse vector. A single hybrid query is sent to Qdrant combining: payload filters (from structured filters) + dense vector search (semantic) + sparse vector search (keyword) + RRF fusion. Qdrant returns fused ranked recipe IDs.

Full recipe objects are hydrated from Postgres using the returned IDs and returned to the client in ranked order.

If only `filters` are provided (no `query`), the search runs as a Qdrant payload-only filter query, returning results sorted by `updatedAt` descending.

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "rec_501",
      "title": "Easy One Pot Pasta",
      "description": "Quick weeknight pasta recipe.",
      "prepTimeMinutes": 10,
      "cookTimeMinutes": 20,
      "servings": 2,
      "heroImageUrl": "https://cdn.kama.app/media/hero_501.jpg",
      "recipeTags": [
        { "id": "tag_under30", "name": "under 30 mins" },
        { "id": "tag_vegetarian", "name": "vegetarian" }
      ],
      "journalSummary": "Family favorite, kids always finish it.",
      "relevanceScore": 0.87,
      "matchReasons": ["tag: vegetarian", "cook time ≤ 30 min", "semantic: kid-friendly pasta"]
    }
  ],
  "parsedQuery": {
    "structuredFilters": {
      "tagIds": ["tag_vegetarian"],
      "maxCookTimeMinutes": 30
    },
    "semanticQuery": "quick pasta the kids will like"
  },
  "nextCursor": null,
  "hasMore": false
}
```

The `parsedQuery` field shows the user how their query was interpreted. `matchReasons` explains why each result was returned — useful for trust and debugging.

---

## 2. Ask

### 2.1 Create ask session

Start a new Ask conversation.

```
POST /api/ask/sessions
```

**Request body**

```json
{
  "question": "Which of my recipes are good for weekday dinners?"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | `string` | Yes | The initial question |

**Response `201 Created`**

```json
{
  "sessionId": "ask_101",
  "answer": {
    "id": "msg_201",
    "role": "assistant",
    "content": "Based on your saved recipes, here are the best options for weekday dinners:\n\n1. **Easy One Pot Pasta** — 20 minutes total, your journal notes say the kids always finish it.\n2. **Quick Stir Fry** — 15 minutes, versatile with whatever vegetables you have.\n3. **Sheet Pan Chicken** — 10 min prep, 25 min cook, your journal mentions it works well for meal prep.\n\nAll three are under 30 minutes active time. Would you like more details on any of these, or should I narrow by dietary preference?",
    "citedRecipeIds": ["rec_501", "rec_512", "rec_523"],
    "retrievedRecipeIds": ["rec_501", "rec_512", "rec_523", "rec_530", "rec_541"]
  },
  "citedRecipes": [
    {
      "id": "rec_501",
      "title": "Easy One Pot Pasta",
      "heroImageUrl": "https://cdn.kama.app/media/hero_501.jpg",
      "cookTimeMinutes": 20
    },
    {
      "id": "rec_512",
      "title": "Quick Stir Fry",
      "heroImageUrl": "https://cdn.kama.app/media/hero_512.jpg",
      "cookTimeMinutes": 15
    },
    {
      "id": "rec_523",
      "title": "Sheet Pan Chicken",
      "heroImageUrl": "https://cdn.kama.app/media/hero_523.jpg",
      "cookTimeMinutes": 35
    }
  ],
  "createdAt": "2026-03-22T20:00:00Z"
}
```

---

### 2.2 Send follow-up message

Continue a conversation within an active session.

```
POST /api/ask/sessions/{sessionId}/messages
```

**Request body**

```json
{
  "question": "Which of those are also vegetarian?"
}
```

**Response `200 OK`**

```json
{
  "answer": {
    "id": "msg_202",
    "role": "assistant",
    "content": "Of the three I suggested, **Easy One Pot Pasta** is vegetarian. Your **Quick Stir Fry** can also be made vegetarian — your journal mentions you've done it with tofu before and it worked well.",
    "citedRecipeIds": ["rec_501", "rec_512"],
    "retrievedRecipeIds": ["rec_501", "rec_512"]
  },
  "citedRecipes": [
    {
      "id": "rec_501",
      "title": "Easy One Pot Pasta",
      "heroImageUrl": "https://cdn.kama.app/media/hero_501.jpg"
    },
    {
      "id": "rec_512",
      "title": "Quick Stir Fry",
      "heroImageUrl": "https://cdn.kama.app/media/hero_512.jpg"
    }
  ]
}
```

**Error responses**

| Status | Condition |
|---|---|
| `404` | Session not found |
| `409` | Session is closed (timed out or explicitly closed) |

---

### 2.3 Close ask session

Explicitly end a session.

```
POST /api/ask/sessions/{sessionId}/close
```

**Response `200 OK`**

```json
{
  "sessionId": "ask_101",
  "status": "closed",
  "closedAt": "2026-03-22T20:15:00Z"
}
```

---

### 2.4 Get ask session

Retrieve an existing session (for page refresh / recovery).

```
GET /api/ask/sessions/{sessionId}
```

**Response `200 OK`**

```json
{
  "id": "ask_101",
  "status": "active",
  "messages": [
    {
      "id": "msg_200",
      "role": "user",
      "content": "Which of my recipes are good for weekday dinners?",
      "createdAt": "2026-03-22T20:00:00Z"
    },
    {
      "id": "msg_201",
      "role": "assistant",
      "content": "Based on your saved recipes...",
      "citedRecipeIds": ["rec_501", "rec_512", "rec_523"],
      "createdAt": "2026-03-22T20:00:03Z"
    },
    {
      "id": "msg_202_user",
      "role": "user",
      "content": "Which of those are also vegetarian?",
      "createdAt": "2026-03-22T20:01:00Z"
    },
    {
      "id": "msg_202",
      "role": "assistant",
      "content": "Of the three I suggested...",
      "citedRecipeIds": ["rec_501", "rec_512"],
      "createdAt": "2026-03-22T20:01:03Z"
    }
  ],
  "createdAt": "2026-03-22T20:00:00Z",
  "lastActiveAt": "2026-03-22T20:01:03Z"
}
```

---

## 3. Artifacts (Create)

### 3.1 Generate artifact

Create a new artifact (shopping list, meal plan, or pantry feasibility check).

```
POST /api/artifacts/generate
```

**Request body — shopping list**

Ingredients with a mapped `ingredientId` are grouped by their `ingredient.category` from the DB (deterministic — no LLM call needed). Unmapped ingredients (no `ingredientId`) fall back to LLM-based category inference.

```json
{
  "artifactType": "shopping_list",
  "title": "Weekend cooking list",
  "recipeIds": ["rec_501", "rec_512", "rec_523"],
  "instructions": null
}
```

**Request body — meal plan**

```json
{
  "artifactType": "meal_plan",
  "title": "Weeknight dinners this week",
  "recipeIds": null,
  "instructions": "3-day vegetarian dinner plan using my saved recipes, prefer under 30 minutes"
}
```

**Request body — pantry feasibility**

```json
{
  "artifactType": "pantry_feasibility",
  "title": "What can I cook tonight?",
  "recipeIds": null,
  "instructions": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `artifactType` | `"shopping_list" \| "meal_plan" \| "pantry_feasibility"` | Yes | |
| `title` | `string` | No | Auto-generated if not provided |
| `recipeIds` | `string[]` | No | Specific recipes to use. If null, system selects from corpus. |
| `instructions` | `string` | No | Natural language instructions for generation (meal plans, custom constraints) |

**Response `201 Created`**

```json
{
  "id": "art_301",
  "artifactType": "shopping_list",
  "title": "Weekend cooking list",
  "content": {
    "type": "shopping_list",
    "sections": [
      {
        "category": "Produce",
        "items": [
          {
            "text": "2 cups cherry tomatoes",
            "ingredientId": "ing_087",
            "quantity": "2",
            "unit": "cups",
            "sourceRecipeIds": ["rec_501"],
            "checked": false
          },
          {
            "text": "3 cloves garlic",
            "ingredientId": "ing_011",
            "quantity": "3",
            "unit": "cloves",
            "sourceRecipeIds": ["rec_501", "rec_512"],
            "checked": false
          }
        ]
      },
      {
        "category": "Pantry",
        "items": [
          {
            "text": "8 oz pasta",
            "ingredientId": "ing_042",
            "quantity": "8",
            "unit": "oz",
            "sourceRecipeIds": ["rec_501"],
            "checked": false
          }
        ]
      }
    ]
  },
  "sourceRecipeIds": ["rec_501", "rec_512", "rec_523"],
  "status": "active",
  "createdAt": "2026-03-22T21:00:00Z",
  "updatedAt": "2026-03-22T21:00:00Z"
}
```

---

### 3.2 Get artifact

```
GET /api/artifacts/{artifactId}
```

**Response `200 OK`** — Full artifact object (same shape as generate response).

---

### 3.3 List artifacts

```
GET /api/artifacts
```

**Query parameters**

| Param | Type | Default | Notes |
|---|---|---|---|
| `artifactType` | `string` | — | Filter by type |
| `status` | `"active" \| "archived" \| "all"` | `"active"` | |
| `sort` | `"created_desc" \| "updated_desc"` | `"updated_desc"` | |
| `cursor` | `string` | — | Pagination |
| `limit` | `number` | `20` | Max 50 |

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "art_301",
      "artifactType": "shopping_list",
      "title": "Weekend cooking list",
      "sourceRecipeCount": 3,
      "status": "active",
      "createdAt": "2026-03-22T21:00:00Z",
      "updatedAt": "2026-03-22T21:00:00Z"
    }
  ],
  "nextCursor": null,
  "hasMore": false
}
```

---

### 3.4 Edit artifact

Partial update. Backend determines revision-worthiness.

```
PATCH /api/artifacts/{artifactId}
```

**Request body** — include only changed fields.

```json
{
  "title": "Updated weekend list",
  "content": {
    "type": "shopping_list",
    "sections": [...]
  }
}
```

**Response `200 OK`**

```json
{
  "id": "art_301",
  "revisionCreated": true,
  "revisionId": "artrev_101",
  "updatedAt": "2026-03-22T22:00:00Z"
}
```

---

### 3.5 Archive artifact

Soft-delete. Archived artifacts are hidden by default but retrievable.

```
POST /api/artifacts/{artifactId}/archive
```

**Response `200 OK`**

```json
{
  "id": "art_301",
  "status": "archived",
  "updatedAt": "2026-03-22T23:00:00Z"
}
```

---

### 3.6 Get artifact revisions

```
GET /api/artifacts/{artifactId}/revisions
```

**Response `200 OK`** — Same shape as recipe revision list.

---

### 3.7 Restore artifact revision

```
POST /api/artifacts/{artifactId}/revisions/{revisionId}/restore
```

**Response `200 OK`** — Same pattern as recipe revision restore (creates new current, non-destructive).

---

## 4. Pantry

### 4.1 Get pantry

```
GET /api/pantry
```

**Response `200 OK`**

```json
{
  "items": [
    {
      "id": "pantry_001",
      "ingredientId": "ing_003",
      "ingredientName": "olive oil",
      "category": "oils_vinegars",
      "addedAt": "2026-03-20T10:00:00Z"
    },
    {
      "id": "pantry_002",
      "ingredientId": "ing_042",
      "ingredientName": "pasta",
      "category": "grains_bread",
      "addedAt": "2026-03-20T10:00:00Z"
    },
    {
      "id": "pantry_003",
      "ingredientId": "ing_011",
      "ingredientName": "garlic",
      "category": "produce",
      "addedAt": "2026-03-21T08:00:00Z"
    }
  ],
  "totalCount": 3
}
```

---

### 4.2 Add pantry items

Add one or more ingredients to the pantry.

```
POST /api/pantry
```

**Request body**

```json
{
  "ingredientIds": ["ing_087", "ing_001"]
}
```

**Response `201 Created`**

```json
{
  "added": [
    { "id": "pantry_004", "ingredientId": "ing_087", "ingredientName": "cherry tomatoes", "addedAt": "2026-03-22T12:00:00Z" },
    { "id": "pantry_005", "ingredientId": "ing_001", "ingredientName": "salt", "addedAt": "2026-03-22T12:00:00Z" }
  ],
  "alreadyInPantry": []
}
```

**Duplicate handling:** If an ingredient is already in the pantry, it's returned in `alreadyInPantry` rather than creating a duplicate.

---

### 4.3 Add pantry item by text

Add an ingredient by free text, mapped to the ingredient DB.

```
POST /api/pantry/from-text
```

**Request body**

```json
{
  "text": "chickpeas"
}
```

**Response `201 Created`**

```json
{
  "added": {
    "id": "pantry_006",
    "ingredientId": "ing_150",
    "ingredientName": "chickpeas",
    "addedAt": "2026-03-22T12:05:00Z"
  },
  "matched": true,
  "matchedIngredient": {
    "id": "ing_150",
    "name": "chickpeas",
    "matchedVia": "alias"
  }
}
```

**If no match found:**

```json
{
  "added": null,
  "matched": false,
  "suggestions": [
    { "id": "ing_150", "name": "chickpeas" },
    { "id": "ing_151", "name": "chicken" }
  ]
}
```

---

### 4.4 Remove pantry items

```
DELETE /api/pantry
```

**Request body**

```json
{
  "pantryItemIds": ["pantry_004", "pantry_005"]
}
```

**Response `204 No Content`**

---

### 4.5 Check pantry feasibility

Run feasibility matching against all canonical recipes using current pantry contents.

```
POST /api/pantry/feasibility
```

**Request body** — optional filters to narrow which recipes are checked.

```json
{
  "filters": {
    "tagIds": ["tag_vegetarian"],
    "maxCookTimeMinutes": 45
  },
  "limit": 30
}
```

**Response `200 OK`**

```json
{
  "pantryItemCount": 12,
  "recipesChecked": 45,
  "fullyFeasible": [
    {
      "recipeId": "rec_501",
      "recipeTitle": "Easy One Pot Pasta",
      "heroImageUrl": "https://cdn.kama.app/media/hero_501.jpg",
      "matchedIngredientCount": 5,
      "totalIngredientCount": 5
    }
  ],
  "partiallyFeasible": [
    {
      "recipeId": "rec_512",
      "recipeTitle": "Quick Stir Fry",
      "heroImageUrl": "https://cdn.kama.app/media/hero_512.jpg",
      "matchedIngredientCount": 4,
      "totalIngredientCount": 6,
      "feasibilityScore": 0.67,
      "missingIngredients": [
        { "ingredientId": "ing_200", "ingredientName": "soy sauce", "category": "oils_vinegars" },
        { "ingredientId": "ing_201", "ingredientName": "sesame oil", "category": "oils_vinegars" }
      ]
    }
  ],
  "notFeasible": [
    {
      "recipeId": "rec_523",
      "recipeTitle": "Sheet Pan Chicken",
      "missingCount": 5
    }
  ],
  "generatedAt": "2026-03-22T22:00:00Z"
}
```

This endpoint can also be used to generate a `pantry_feasibility` artifact if the user wants to save the results (via `POST /api/artifacts/generate` with `artifactType: "pantry_feasibility"`).

---

## 5. Journal summary

The `journalSummary` field is managed automatically by the system. No direct user-facing API for editing it. It is returned as part of the recipe detail response (already in Phase 1 API contracts).

### 5.1 Trigger summary regeneration (admin/debug)

For development and debugging purposes only.

```
POST /api/recipes/{recipeId}/regenerate-journal-summary
```

**Response `202 Accepted`**

```json
{
  "recipeId": "rec_501",
  "status": "queued",
  "message": "Journal summary regeneration queued."
}
```

This triggers a **background task** (`regenerate_journal_summary_send` → `background_runner.enqueue`). The summary updates on the recipe asynchronously. **Revisit:** a **Dramatiq**-backed worker if moving job dispatch off the API process.

---

## 6. Embeddings (internal)

Embedding generation and management is not user-facing. These endpoints are for admin/debug use.

### 6.1 Trigger embedding regeneration

```
POST /api/admin/recipes/{recipeId}/regenerate-embedding
```

**Response `202 Accepted`**

```json
{
  "recipeId": "rec_501",
  "status": "queued"
}
```

### 6.2 Backfill all embeddings

```
POST /api/admin/embeddings/backfill
```

**Response `202 Accepted`**

```json
{
  "status": "queued",
  "recipesToProcess": 487
}
```

---

## 7. Phase 2 endpoint summary

| Method | Endpoint | Surface | Purpose |
|---|---|---|---|
| POST | `/api/search` | Search | Hybrid recipe search |
| POST | `/api/ask/sessions` | Ask | Start new ask session |
| POST | `/api/ask/sessions/{id}/messages` | Ask | Send follow-up question |
| POST | `/api/ask/sessions/{id}/close` | Ask | Close session |
| GET | `/api/ask/sessions/{id}` | Ask | Retrieve session (recovery) |
| POST | `/api/artifacts/generate` | Create | Generate artifact |
| GET | `/api/artifacts/{id}` | Create | Get artifact |
| GET | `/api/artifacts` | Create | List artifacts |
| PATCH | `/api/artifacts/{id}` | Create | Edit artifact |
| POST | `/api/artifacts/{id}/archive` | Create | Archive artifact |
| GET | `/api/artifacts/{id}/revisions` | Create | Artifact revision history |
| POST | `/api/artifacts/{id}/revisions/{revId}/restore` | Create | Restore artifact revision |
| GET | `/api/pantry` | Pantry | Get pantry contents |
| POST | `/api/pantry` | Pantry | Add pantry items by ingredient ID |
| POST | `/api/pantry/from-text` | Pantry | Add pantry item by free text |
| DELETE | `/api/pantry` | Pantry | Remove pantry items |
| POST | `/api/pantry/feasibility` | Pantry | Check recipe feasibility |
| POST | `/api/recipes/{id}/regenerate-journal-summary` | Admin | Trigger summary regen |
| POST | `/api/admin/recipes/{id}/regenerate-embedding` | Admin | Trigger embedding regen |
| POST | `/api/admin/embeddings/backfill` | Admin | Backfill all embeddings |

**Total Phase 2 endpoints: 20**  
**Combined Phase 1 + Phase 2: 47 endpoints**
