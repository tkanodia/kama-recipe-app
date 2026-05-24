"""Qdrant client singleton and collection initialization."""

from __future__ import annotations

import structlog
from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings

log = structlog.get_logger()

COLLECTION_NAME = "kama_recipes"
DENSE_VECTOR_DIM = 1536

_client: AsyncQdrantClient | None = None


def get_qdrant_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
    return _client


async def init_collection() -> None:
    """Create the kama_recipes collection if it doesn't exist."""
    client = get_qdrant_client()
    collections = await client.get_collections()
    existing = {c.name for c in collections.collections}

    if COLLECTION_NAME in existing:
        log.info("qdrant_collection_exists", collection=COLLECTION_NAME)
        return

    await client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=DENSE_VECTOR_DIM,
                distance=models.Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "bm25": models.SparseVectorParams(),
        },
    )

    for field_name in [
        "userId",
        "tagIds",
        "ingredientIds",
    ]:
        await client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    for field_name in [
        "cookTimeMinutes",
        "prepTimeMinutes",
        "servings",
    ]:
        await client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field_name,
            field_schema=models.PayloadSchemaType.INTEGER,
        )

    log.info("qdrant_collection_created", collection=COLLECTION_NAME)


async def close_qdrant() -> None:
    global _client
    if _client is not None:
        await _client.close()
        _client = None
