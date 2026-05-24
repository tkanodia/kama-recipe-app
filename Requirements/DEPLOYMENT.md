# Kama deployment runbook

Deploy **frontend → Vercel**, **backend → Railway**. Phase 1 (T-051) and Phase 2 (T-097) share the same backend service; Phase 2 adds Qdrant and extra env vars.

## Architecture

```
Browser → Vercel (Next.js apps/web)
              ↓ HTTPS + Clerk JWT
         Railway (FastAPI + in-process background_runner)
              ↓
    Postgres · Redis · S3 · Qdrant Cloud · LLM APIs
```

- **Single Railway service** runs uvicorn + background jobs (no separate Dramatiq worker today).
- **Migrations** run automatically on each deploy via `backend/scripts/start.sh`.
- **SSE** (ingestion progress) crosses Vercel → Railway; CORS must include your Vercel URL.

---

## Prerequisites

| Service | Purpose |
|---------|---------|
| [Clerk](https://clerk.com) | Auth (same app for Vercel + Railway JWT validation) |
| [Railway](https://railway.app) | FastAPI, Postgres, Redis |
| [Vercel](https://vercel.com) | Next.js frontend |
| AWS S3 or [Cloudflare R2](https://developers.cloudflare.com/r2/) | Recipe media uploads |
| [Qdrant Cloud](https://qdrant.tech/cloud/) | Phase 2 hybrid search (recommended over self-hosting on Railway) |
| OpenAI and/or Anthropic | LLM for ingestion, Ask, Create |
| Google Cloud Vision (optional) | Image/OCR ingestion — use `GOOGLE_CREDENTIALS_JSON` on Railway |
| YouTube Data API (optional) | YouTube ingestion metadata |

---

## Part 1 — Railway (backend) · T-051

### 1. Create project

1. New Railway project → **Add PostgreSQL** and **Add Redis**.
2. **New service** → **Deploy from GitHub repo** → set **Root directory** to `backend`.
3. Railway detects `backend/Dockerfile` and `backend/railway.toml`.

### 2. Environment variables

Set on the **API service** (reference `backend/.env.example`):

| Variable | Required | Notes |
|----------|----------|-------|
| `APP_ENV` | Yes | `production` |
| `DATABASE_URL` | Yes | Reference from Postgres plugin (`postgresql://...` — auto-normalized) |
| `REDIS_URL` | Yes | Reference from Redis plugin |
| `CORS_ORIGINS` | Yes | `https://your-app.vercel.app` (comma-separate preview URLs if needed) |
| `CLERK_JWKS_URL` | Yes | From Clerk dashboard → JWT templates / API keys |
| `CLERK_ISSUER` | Yes | e.g. `https://xxx.clerk.accounts.dev` |
| `DISABLE_AUTH` | Yes | `false` in production |
| `S3_BUCKET`, `AWS_*` | Yes* | *Required for media uploads; use R2 + `S3_ENDPOINT_URL` if preferred |
| `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` | Yes | Match `LLM_PROVIDER` |
| `LLM_PROVIDER`, `LLM_MODEL` | Yes | e.g. `openai`, `gpt-4o` |
| `QDRANT_URL`, `QDRANT_API_KEY` | Phase 2 | Qdrant Cloud cluster URL + API key |
| `ADMIN_USER_IDS` | Optional | Clerk user IDs for embedding backfill admin routes |
| `SENTRY_DSN` | Optional | Backend error tracking |
| `GOOGLE_CREDENTIALS_JSON` | Optional | Full service account JSON string for Vision API |
| `YOUTUBE_API_KEY` | Optional | YouTube ingestion |

**Do not** set `PORT` manually — Railway injects it; `scripts/start.sh` reads it.

### 3. Deploy

Push to `main` (or trigger manual deploy). On start:

1. `alembic upgrade head`
2. `uvicorn` on `$PORT`

Verify:

```bash
curl https://your-api.up.railway.app/health
# → {"status":"ok"}

curl https://your-api.up.railway.app/health/ready
# → {"status":"ready"}  (503 if DB unreachable)
```

### 4. One-time: seed ingredients (T-051.4)

From Railway CLI or one-off shell on the API service:

```bash
uv run python -m app.seeds.seed_data
```

Safe to re-run — skips existing rows.

---

## Part 2 — Vercel (frontend) · T-051.5

### 1. Import project

1. Vercel → **Add New Project** → import GitHub repo.
2. **Root Directory:** `apps/web`
3. Framework: **Next.js** (auto-detected).
4. `apps/web/vercel.json` runs install/build from monorepo root via Turborepo.

### 2. Environment variables

| Variable | Required | Notes |
|----------|----------|-------|
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Yes | Clerk publishable key |
| `CLERK_SECRET_KEY` | Yes | Clerk secret (server-side) |
| `NEXT_PUBLIC_API_URL` | Yes | Railway API URL, no trailing slash |
| `NEXT_PUBLIC_SENTRY_DSN` | Optional | Frontend Sentry |

Redeploy after changing `NEXT_PUBLIC_*` vars.

### 3. Clerk allowed origins

In Clerk dashboard, add:

- Production: `https://your-app.vercel.app`
- Preview deployments if you use them

---

## Part 3 — Phase 2 production · T-097

After Phase 1 is live:

### T-097.1–T-097.2 Qdrant

1. Create cluster on [Qdrant Cloud](https://cloud.qdrant.io).
2. Set `QDRANT_URL` and `QDRANT_API_KEY` on Railway.
3. Redeploy API — `init_collection()` creates `kama_recipes` on startup if missing.

### T-097.3 Migrations

Already handled by deploy script. Confirm Ask/Artifact/Pantry tables exist:

```bash
uv run alembic current
uv run alembic history
```

### T-097.5 Embedding backfill

As an admin user (`ADMIN_USER_IDS`):

```bash
curl -X POST https://your-api.up.railway.app/api/admin/embeddings/backfill \
  -H "Authorization: Bearer <clerk-jwt>"
```

Or use Railway shell + internal HTTP client.

### T-097.6 Smoke test checklist

- [ ] Sign in on Vercel
- [ ] Ingest URL → SSE progress → review → save
- [ ] Recipe appears in library
- [ ] Search returns results (`/search`)
- [ ] Ask a question (`/ask`)
- [ ] Create shopping list from recipes
- [ ] Add pantry items → feasibility badges on library
- [ ] Generate meal plan

---

## CORS & SSE notes

- `CORS_ORIGINS` must include the exact Vercel origin (scheme + host, no path).
- Ingestion SSE uses `EventSource` with `?token=<clerk-jwt>` — works cross-origin when CORS allows the Vercel origin.
- If SSE fails in production, check browser Network tab for blocked CORS on `/api/ingestion/jobs/{id}/events`.

---

## Custom domains · T-051.7

| Platform | Steps |
|----------|-------|
| Vercel | Project → Settings → Domains |
| Railway | Service → Settings → Networking → Custom Domain |
| Clerk | Add production domain to allowed origins |
| CORS | Add `https://yourdomain.com` to Railway `CORS_ORIGINS` |

Update `NEXT_PUBLIC_API_URL` if API gets a custom domain too.

---

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| 401 on all API calls | `CLERK_JWKS_URL` / `CLERK_ISSUER` mismatch or `DISABLE_AUTH=false` without valid JWT |
| CORS errors | Missing Vercel URL in `CORS_ORIGINS` |
| Migrations fail on deploy | Wrong `DATABASE_URL` or Postgres not linked |
| Search always ILIKE fallback | Qdrant unreachable — check `QDRANT_URL` / API key; library shows “Search quality reduced” |
| Media upload fails | S3/R2 credentials or bucket policy |
| OCR fails | Missing `GOOGLE_CREDENTIALS_JSON` |
| Deploy health check fails | DB not ready — check `/health/ready` logs |

---

## Local parity

```bash
pnpm dev:infra          # Postgres, Redis, Qdrant, MinIO
cp backend/.env.example backend/.env
pnpm dev:apps           # web + API
```

See root `package.json` scripts.

---

## Related tasks

| Task | Scope |
|------|-------|
| T-051 | Phase 1 deploy (this doc, Part 1–2) |
| T-097 | Phase 2 deploy (Part 3) |
| T-050 / T-096 | Sentry + observability (optional env vars above) |
| T-056 | CI runs on GitHub — deploy is separate from CI |
