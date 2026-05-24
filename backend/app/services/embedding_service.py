"""Embedding service — dense (OpenAI) and sparse (BM25) vector generation."""

from __future__ import annotations

import string

import structlog
import tiktoken
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import llm_breaker
from app.core.config import get_settings
from app.models.tables import CanonicalRecipe

log = structlog.get_logger()

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_TOKENS = 8191


def compose_source_text(recipe: CanonicalRecipe) -> str:
    """Build a single text block from recipe fields for embedding."""
    parts: list[str] = []

    parts.append(recipe.title or "")

    if recipe.description:
        parts.append(recipe.description)

    if recipe.ingredients:
        names = [
            ing.get("name", "") for ing in recipe.ingredients if isinstance(ing, dict)
        ]
        if names:
            parts.append(f"Ingredients: {', '.join(n for n in names if n)}")

    if recipe.recipe_tags:
        tag_names = [
            t.get("name", "") for t in recipe.recipe_tags if isinstance(t, dict)
        ]
        if tag_names:
            parts.append(f"Tags: {', '.join(n for n in tag_names if n)}")

    if recipe.journal_summary:
        parts.append(recipe.journal_summary)

    return ". ".join(p for p in parts if p)


def _truncate_to_token_limit(text: str, max_tokens: int = MAX_TOKENS) -> str:
    """Truncate text to fit within the token limit for the embedding model."""
    enc = tiktoken.encoding_for_model(EMBEDDING_MODEL)
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    log.warning("embedding_text_truncated", original_tokens=len(tokens), max_tokens=max_tokens)
    return enc.decode(tokens[:max_tokens])


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def generate_dense_embedding(text: str) -> list[float]:
    """Generate a 1536-dimensional dense embedding via OpenAI."""
    from openai import AsyncOpenAI

    if llm_breaker.is_open():
        raise RuntimeError("LLM circuit breaker is open — refusing embedding call")

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for embeddings")

    truncated = _truncate_to_token_limit(text)
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    try:
        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )
        llm_breaker.record_success()
        return response.data[0].embedding
    except Exception:
        llm_breaker.record_failure()
        raise


# ---------------------------------------------------------------------------
# BM25 sparse vector generation
# ---------------------------------------------------------------------------

_PUNCT_TABLE = str.maketrans("", "", string.punctuation)


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return text.lower().translate(_PUNCT_TABLE).split()


def generate_sparse_vector(text: str) -> dict:
    """Build a BM25-style sparse vector from text.

    Returns a dict with 'indices' (list[int]) and 'values' (list[float])
    suitable for Qdrant sparse vector format.

    Uses term-frequency with BM25 saturation (k1=1.2) applied
    per-document. Since we don't have a corpus-wide IDF at indexing
    time, TF saturation alone provides a solid lexical signal that
    pairs well with RRF fusion at query time.
    """
    tokens = _tokenize(text)
    if not tokens:
        return {"indices": [], "values": []}

    tf: dict[str, int] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1

    doc_len = len(tokens)
    avg_dl = doc_len  # single-doc assumption
    k1 = 1.2
    b = 0.75

    indices: list[int] = []
    values: list[float] = []

    for term, count in tf.items():
        idx = abs(hash(term)) % (2**31)
        norm_tf = (count * (k1 + 1)) / (count + k1 * (1 - b + b * doc_len / avg_dl))
        indices.append(idx)
        values.append(float(norm_tf))

    return {"indices": indices, "values": values}
