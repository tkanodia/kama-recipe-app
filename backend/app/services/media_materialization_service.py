"""T-099: Media materialization — download extracted images, upload to S3, register as RecipeMedia."""

from typing import Any

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.s3 import build_asset_ref, get_s3_client
from app.repositories import recipe_media_repo
from app.services.thumbnail_service import generate_thumbnail

log = structlog.get_logger()

_DOWNLOAD_TIMEOUT = 10.0
_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB


async def materialize_extracted_images(
    candidate_data: dict[str, Any],
    canonical_recipe_id: str,
    user_id: str,
    session: AsyncSession,
) -> list[str]:
    """Download images from candidate signals and register them as RecipeMedia.

    Returns a list of created media IDs.  Failures are logged but never
    propagated — the canonical save must not fail because of image issues.
    """
    _MAX_GALLERY = 4  # 1 hero + 3 source_gallery
    image_urls: list[str] = (candidate_data.get("imageUrls") or [])[:_MAX_GALLERY]
    step_images: dict[str, list[str]] = candidate_data.get("stepImages") or {}

    if not image_urls and not step_images:
        return []

    settings = get_settings()
    bucket = settings.s3_bucket
    created_ids: list[str] = []

    if not bucket:
        for idx, url in enumerate(image_urls):
            try:
                role = "hero" if idx == 0 else "source_gallery"
                media = await recipe_media_repo.create(
                    session,
                    canonical_recipe_id=canonical_recipe_id,
                    role=role,
                    source="extracted_url",
                    asset_ref=url,
                    thumbnail_ref=None,
                    display_order=idx,
                )
                created_ids.append(media.id)
                log.info("image_registered_url", recipe_id=canonical_recipe_id, url=url, role=role)
            except Exception as exc:
                log.warning("image_registration_error", url=url, error=str(exc))

        await _register_step_images(step_images, canonical_recipe_id, None, session, created_ids)
        return created_ids

    s3 = get_s3_client()

    async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT, follow_redirects=True) as client:
        for idx, url in enumerate(image_urls):
            try:
                # S3 key (already in bucket) — read directly instead of HTTP download
                if url.startswith("uploads/") or url.startswith("s3://"):
                    s3_key = url.removeprefix("s3://")
                    try:
                        obj = s3.get_object(Bucket=bucket, Key=s3_key)
                        image_content = obj["Body"].read()
                        content_type = obj.get("ContentType", "image/jpeg")
                    except Exception as s3_exc:
                        log.warning("s3_image_read_failed", key=s3_key, error=str(s3_exc))
                        continue
                    asset_key = s3_key
                else:
                    resp = await client.get(url)
                    resp.raise_for_status()

                    if len(resp.content) > _MAX_IMAGE_BYTES:
                        log.warning("image_too_large", url=url, size=len(resp.content))
                        continue

                    image_content = resp.content
                    content_type = resp.headers.get("content-type", "image/jpeg")
                    ext = _extension_from_content_type(content_type)
                    asset_key = build_asset_ref("recipe-media", user_id, f"img_{idx}{ext}")

                    s3.put_object(
                        Bucket=bucket,
                        Key=asset_key,
                        Body=image_content,
                        ContentType=content_type,
                    )

                thumb_key: str | None = None
                try:
                    thumb_bytes = await generate_thumbnail(image_content)
                    thumb_key = f"{asset_key}_thumb"
                    s3.put_object(
                        Bucket=bucket,
                        Key=thumb_key,
                        Body=thumb_bytes,
                        ContentType="image/webp",
                    )
                except Exception as thumb_exc:
                    log.warning("thumbnail_generation_failed", url=url, error=str(thumb_exc))
                    thumb_key = None

                role = "hero" if idx == 0 else "source_gallery"
                media = await recipe_media_repo.create(
                    session,
                    canonical_recipe_id=canonical_recipe_id,
                    role=role,
                    source="extracted",
                    asset_ref=asset_key,
                    thumbnail_ref=thumb_key,
                    display_order=idx,
                )
                created_ids.append(media.id)
                log.info(
                    "image_materialized",
                    recipe_id=canonical_recipe_id,
                    url=url,
                    role=role,
                    asset_ref=asset_key,
                    thumbnail_ref=thumb_key,
                )

            except httpx.HTTPError as exc:
                log.warning("image_download_failed", url=url, error=str(exc))
            except Exception as exc:
                log.warning("image_materialization_error", url=url, error=str(exc))

    await _register_step_images(step_images, canonical_recipe_id, bucket, session, created_ids)
    return created_ids


async def _register_step_images(
    step_images: dict[str, list[str]],
    canonical_recipe_id: str,
    bucket: str | None,
    session: AsyncSession,
    created_ids: list[str],
) -> None:
    """Register per-step images as RecipeMedia with role='step_{order}'.

    Only the first image per step is used to keep the gallery manageable.
    """
    if not step_images:
        return

    seen_urls: set[str] = set()
    for step_order, urls in step_images.items():
        url = urls[0] if urls else None
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)

        try:
            role = f"step_{step_order}"
            media = await recipe_media_repo.create(
                session,
                canonical_recipe_id=canonical_recipe_id,
                role=role,
                source="extracted_url",
                asset_ref=url,
                thumbnail_ref=None,
                display_order=1000 + int(step_order),
            )
            created_ids.append(media.id)
            log.info("step_image_registered", recipe_id=canonical_recipe_id, step=step_order, url=url)
        except Exception as exc:
            log.warning("step_image_registration_error", step=step_order, url=url, error=str(exc))


def _extension_from_content_type(content_type: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    ct = content_type.split(";")[0].strip().lower()
    return mapping.get(ct, ".jpg")
