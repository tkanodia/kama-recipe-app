"""Qdrant client service — abstraction layer for all Qdrant vector operations."""

from __future__ import annotations

from typing import Any

import structlog
from qdrant_client import models

from app.core.qdrant import COLLECTION_NAME, get_qdrant_client

log = structlog.get_logger()


class QdrantUnavailableError(Exception):
    """Raised when Qdrant is unreachable or returns a connection error."""


async def upsert_recipe_point(
    recipe_id: str,
    dense_vector: list[float],
    sparse_vector: dict,
    payload: dict[str, Any],
) -> None:
    """Upsert a recipe point with named dense + sparse vectors."""
    try:
        client = get_qdrant_client()
        await client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                models.PointStruct(
                    id=_recipe_id_to_point_id(recipe_id),
                    vector={
                        "dense": dense_vector,
                        "bm25": models.SparseVector(
                            indices=sparse_vector["indices"],
                            values=sparse_vector["values"],
                        ),
                    },
                    payload={**payload, "recipeId": recipe_id},
                )
            ],
        )
        log.debug("qdrant_upsert_ok", recipe_id=recipe_id)
    except Exception as exc:
        log.error("qdrant_upsert_failed", recipe_id=recipe_id, error=str(exc))
        raise QdrantUnavailableError(f"Qdrant upsert failed: {exc}") from exc


async def hybrid_search(
    dense_vector: list[float],
    sparse_vector: dict,
    payload_filter: models.Filter | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[str, float]]:
    """Hybrid search with RRF fusion on dense + sparse, returns (recipe_id, score) tuples."""
    try:
        client = get_qdrant_client()
        results = await client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=dense_vector,
                    using="dense",
                    limit=limit + offset + 20,
                    filter=payload_filter,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_vector["indices"],
                        values=sparse_vector["values"],
                    ),
                    using="bm25",
                    limit=limit + offset + 20,
                    filter=payload_filter,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            offset=offset,
            with_payload=True,
        )

        hits: list[tuple[str, float]] = []
        for point in results.points:
            recipe_id = point.payload.get("recipeId", "") if point.payload else ""
            hits.append((recipe_id, point.score or 0.0))

        return hits
    except Exception as exc:
        log.error("qdrant_search_failed", error=str(exc))
        raise QdrantUnavailableError(f"Qdrant search failed: {exc}") from exc


async def filter_only_search(
    payload_filter: models.Filter,
    limit: int = 20,
    offset: int = 0,
) -> list[tuple[str, float]]:
    """Search using only payload filters (no query text)."""
    try:
        client = get_qdrant_client()
        results = await client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=payload_filter,
            limit=limit,
            offset=_int_to_point_id(offset) if offset else None,
            with_payload=True,
        )

        hits: list[tuple[str, float]] = []
        for point in results[0]:
            recipe_id = point.payload.get("recipeId", "") if point.payload else ""
            hits.append((recipe_id, 1.0))

        return hits
    except Exception as exc:
        log.error("qdrant_filter_search_failed", error=str(exc))
        raise QdrantUnavailableError(f"Qdrant filter search failed: {exc}") from exc


async def delete_recipe_point(recipe_id: str) -> None:
    """Delete a recipe's point from Qdrant."""
    try:
        client = get_qdrant_client()
        await client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=models.PointIdsList(
                points=[_recipe_id_to_point_id(recipe_id)],
            ),
        )
        log.debug("qdrant_delete_ok", recipe_id=recipe_id)
    except Exception as exc:
        log.error("qdrant_delete_failed", recipe_id=recipe_id, error=str(exc))
        raise QdrantUnavailableError(f"Qdrant delete failed: {exc}") from exc


async def get_recipe_point(recipe_id: str) -> dict | None:
    """Retrieve a recipe's point for debugging/verification."""
    try:
        client = get_qdrant_client()
        points = await client.retrieve(
            collection_name=COLLECTION_NAME,
            ids=[_recipe_id_to_point_id(recipe_id)],
            with_payload=True,
            with_vectors=False,
        )
        if points:
            return {
                "id": points[0].id,
                "payload": points[0].payload,
            }
        return None
    except Exception as exc:
        log.error("qdrant_get_failed", recipe_id=recipe_id, error=str(exc))
        raise QdrantUnavailableError(f"Qdrant get failed: {exc}") from exc


def _recipe_id_to_point_id(recipe_id: str) -> str:
    """Convert recipe ID to a Qdrant-compatible point ID (UUID-like hex string)."""
    import hashlib
    h = hashlib.md5(recipe_id.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _int_to_point_id(offset: int) -> str:
    """Create a dummy point ID from an integer offset — used for scroll pagination."""
    import hashlib
    h = hashlib.md5(str(offset).encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
