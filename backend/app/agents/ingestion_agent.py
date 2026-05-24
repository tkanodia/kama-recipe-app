"""T-015: Ingestion agent — core loop.

Orchestrates source classification, content fetching, extraction, and
candidate creation. Replaces the stub worker with real tool-calling logic.
"""

import os
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.ids import new_id
from app.repositories import ingestion_job_repo, normalized_artifact_repo, tag_repo
from app.agents.review_agent import run_review_agent
from app.services.ingestion_service import create_candidate_from_extraction
from app.services.sse_service import next_sequence, publish_job_event
from app.tools.evaluation_tools import assess_parseability, evaluate_candidate
from app.tools.extraction_tools import (
    check_schema_markup,
    classify_recipe_images,
    extract_images_from_html,
    extract_images_with_context,
    llm_structured_extract,
    schema_recipe_extract,
)
from app.tools.notes_extractor import (
    extract_chef_notes_from_html,
    extract_chef_notes_llm,
    extract_how_to_serve_from_html,
)
from app.tools.fetch_tools import extract_page_text, httpx_fetch
from app.tools.ocr_tools import (
    create_image_preview,
    enrich_extracted_recipe,
    extract_dish_photo_from_image,
    multimodal_llm_extract,
    ocr_extract,
    _resolve_image_bytes,
)
from app.tools.social_tools import (
    discover_recipe_on_site,
    expand_bio_links,
    fetch_creator_profile,
    fetch_social_post_page,
    yt_dlp_fetch_metadata,
)
from app.tools.source_tools import classify_source, extract_recipe_links
from app.tools.text_tools import analyze_text_structure, clean_text, create_text_preview
from app.tools.video_tools import (
    cleanup_temp_files,
    extract_key_frames,
    llm_frame_extract,
    merge_partial_candidates,
    whisper_transcribe,
    yt_dlp_download_video,
)
from app.tools.youtube_tools import (
    extract_video_id,
    youtube_api_fetch,
    youtube_transcript_fetch,
)

log = structlog.get_logger()

MAX_ITERATIONS = 15
WALL_CLOCK_TIMEOUT = 300  # 5 minutes


async def run_ingestion_agent(
    session: AsyncSession,
    job_id: str,
    user_id: str,
    source_asset_id: str,
    source_type: str,
    url: str | None = None,
    raw_text: str | None = None,
    file_asset_ref: str | None = None,
    model_override: str | None = None,
) -> None:
    start_time = time.monotonic()
    iteration = 0
    artifacts: list[dict[str, Any]] = []
    artifact_ids: list[str] = []
    extraction_plan: list[dict] = []
    candidate_update: dict[str, Any] | None = None
    provenance: dict[str, Any] = {}
    extraction_method = ""
    review_mode = "standard"
    canonical_eligible = False
    draft_eligible = False
    review_findings: list[dict] = []

    def _elapsed() -> float:
        return time.monotonic() - start_time

    def _timed_out() -> bool:
        return _elapsed() >= WALL_CLOCK_TIMEOUT

    async def _heartbeat() -> None:
        now = datetime.now(tz=UTC)
        await ingestion_job_repo.update_job_status(session, job_id, last_heartbeat_at=now)

    async def _emit(event_type: str, extra: dict | None = None) -> None:
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {
            "eventType": event_type,
            "jobId": job_id,
            "sequence": next_sequence(job_id),
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }
        if extra:
            payload.update(extra)
        publish_job_event(job_id, payload)

    async def _add_plan_entry(method_key: str, status: str = "planned") -> dict:
        entry = {
            "methodKey": method_key,
            "status": status,
            "addedBy": "agent",
            "agentDecision": None,
            "startedAt": None,
            "completedAt": None,
        }
        extraction_plan.append(entry)
        return entry

    async def _update_plan_entry(method_key: str, status: str, **kwargs: Any) -> None:
        for entry in extraction_plan:
            if entry["methodKey"] == method_key:
                entry["status"] = status
                entry.update(kwargs)
                break

    async def _persist_artifact(artifact_type: str, payload: dict) -> str:
        art = await normalized_artifact_repo.create_artifact(
            session,
            ingestion_job_id=job_id,
            artifact_type=artifact_type,
            payload=payload,
        )
        artifact_ids.append(art.id)
        artifacts.append({"artifactType": artifact_type, "payload": payload, "id": art.id})
        return art.id

    async def _run_tool(tool_name: str, tool_fn, *args, **kwargs):
        nonlocal iteration
        iteration += 1

        await _heartbeat()
        await _emit("tool_called", {"toolName": tool_name, "iteration": iteration})
        await _add_plan_entry(tool_name, status="running")

        now_str = datetime.now(tz=UTC).isoformat()
        await _update_plan_entry(tool_name, "running", startedAt=now_str)

        try:
            result = await tool_fn(*args, **kwargs) if _is_async(tool_fn) else tool_fn(*args, **kwargs)

            done_str = datetime.now(tz=UTC).isoformat()
            if result.success:
                await _update_plan_entry(tool_name, "completed", completedAt=done_str)
                await _emit("tool_succeeded", {"toolName": tool_name, "message": result.message})
            else:
                await _update_plan_entry(tool_name, "failed", completedAt=done_str)
                await _emit("tool_failed", {"toolName": tool_name, "message": result.message})

            for art_data in result.artifacts:
                await _persist_artifact(art_data["artifactType"], art_data.get("payload", {}))

            return result

        except Exception as e:
            done_str = datetime.now(tz=UTC).isoformat()
            await _update_plan_entry(tool_name, "failed", completedAt=done_str)
            await _emit("tool_failed", {"toolName": tool_name, "message": str(e)})
            log.error("tool_exception", tool=tool_name, job_id=job_id, error=str(e))
            from app.tools.base import ToolResult
            return ToolResult(success=False, message=str(e))

    async def _resolve_recipe_tags(tag_names: list[str]) -> list[dict[str, str]]:
        """Resolve LLM-suggested tag names to DB tag objects, creating new ones as needed."""
        resolved = []
        for name in tag_names[:8]:
            tag, _ = await tag_repo.create_or_reuse(
                session, name=name, domain="recipe", created_by_user_id=user_id,
            )
            resolved.append({"id": tag.id, "name": tag.name})
        return resolved

    try:
        # Load existing recipe tags to guide the LLM
        existing_tags = await tag_repo.list_by_domain(session, "recipe")
        available_tag_names = [t.name for t in existing_tags]

        await _emit("job.state_changed", {"status": "processing", "internalState": "source_classification"})

        # Step 1: Classify source
        classify_result = await _run_tool(
            "classify_source",
            classify_source,
            source_type, url, file_asset_ref, raw_text,
        )
        if not classify_result.success:
            await _finalize_job(session, job_id, "failed", "unsupported_source", extraction_plan, artifact_ids)
            await _emit("job.unsupported", {"status": "unsupported", "message": classify_result.message})
            return

        source_subtype = classify_result.signals.get("sourceSubtype", "unknown")
        await _emit("job.state_changed", {"status": "processing", "internalState": "recipe_extraction", "sourceSubtype": source_subtype})

        # Step 2: Source-specific extraction
        if source_type == "url" and url and source_subtype == "youtube":
            candidate_update, provenance, extraction_method, review_mode_override, _image_urls, _step_images = await _extract_from_youtube(
                session, job_id, url,
                _run_tool, _emit, artifacts, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
            if review_mode_override:
                review_mode = review_mode_override
            if _image_urls or _step_images:
                payload: dict[str, Any] = {}
                if _image_urls:
                    payload["imageUrls"] = _image_urls
                if _step_images:
                    payload["stepImages"] = _step_images
                await _persist_artifact("extracted_images", payload)
        elif source_type == "url" and url and source_subtype in ("instagram_photo", "facebook_photo"):
            candidate_update, provenance, extraction_method, review_mode_override, _image_urls = await _extract_from_social_photo(
                session, job_id, url, source_subtype,
                _run_tool, _emit, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
            if review_mode_override:
                review_mode = review_mode_override
            if _image_urls:
                await _persist_artifact("extracted_images", {"imageUrls": _image_urls})
        elif source_type == "url" and url and source_subtype in ("instagram", "tiktok", "facebook"):
            candidate_update, provenance, extraction_method, review_mode_override, _image_urls, _step_images = await _extract_from_social(
                session, job_id, url, source_subtype,
                _run_tool, _emit, artifacts, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
            if review_mode_override:
                review_mode = review_mode_override
            if _image_urls or _step_images:
                payload: dict[str, Any] = {}
                if _image_urls:
                    payload["imageUrls"] = _image_urls
                if _step_images:
                    payload["stepImages"] = _step_images
                await _persist_artifact("extracted_images", payload)
        elif source_type == "url" and url:
            candidate_update, provenance, extraction_method, _image_urls, _step_images = await _extract_from_url(
                session, job_id, url, source_subtype,
                _run_tool, _emit, artifacts, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
            if _image_urls or _step_images:
                payload: dict[str, Any] = {}
                if _image_urls:
                    payload["imageUrls"] = _image_urls
                if _step_images:
                    payload["stepImages"] = _step_images
                await _persist_artifact("extracted_images", payload)
        elif source_type == "text" and raw_text:
            candidate_update, provenance, extraction_method = await _extract_from_text(
                session, job_id, raw_text, _run_tool, _emit, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
        elif source_type == "image" and file_asset_ref:
            candidate_update, provenance, extraction_method, review_mode_override, _img_urls = await _extract_from_image(
                session, job_id, file_asset_ref, _run_tool, _emit, _timed_out,
                model_override=model_override, available_tag_names=available_tag_names,
            )
            if review_mode_override:
                review_mode = review_mode_override
            if _img_urls:
                await _persist_artifact("extracted_images", {"imageUrls": _img_urls})

        if _timed_out():
            log.warning("agent_timeout", job_id=job_id, elapsed=_elapsed())

        # Step 2b: LLM refinement — only for non-LLM extractions (schema markup,
        # video reconstruction) where the data wasn't already shaped by our prompt
        _LLM_METHODS = {"llm_structured_extract", "caption_llm", "description_llm", "transcript_llm"}
        needs_refine = (
            candidate_update
            and candidate_update.get("title")
            and not _timed_out()
            and not any(tag in extraction_method for tag in _LLM_METHODS)
        )
        if needs_refine:
            try:
                from app.tools.extraction_tools import llm_refine_candidate
                candidate_update = await llm_refine_candidate(
                    candidate_update,
                    model_override=model_override,
                )
            except Exception as e:
                log.warning("llm_refine_error", job_id=job_id, error=str(e))

        # Step 3: Evaluate candidate
        if candidate_update and candidate_update.get("title"):
            eval_result = await _run_tool(
                "evaluate_candidate",
                evaluate_candidate,
                candidate_update.get("title"),
                candidate_update.get("ingredients", []),
                candidate_update.get("steps", []),
                candidate_update.get("description"),
                candidate_update.get("prepTimeMinutes"),
                candidate_update.get("cookTimeMinutes"),
                candidate_update.get("servings"),
            )
            canonical_eligible = eval_result.signals.get("canonicalEligible", False)
            draft_eligible = eval_result.signals.get("draftEligible", True)
            review_findings = eval_result.signals.get("reviewFindings", [])
            review_mode = "quick" if canonical_eligible else "standard"

            # Step 3b: Map ingredients to DB (quantity/unit + ingredientId + category)
            try:
                from app.tools.ingredient_parser import map_ingredients_to_db
                raw_ings = candidate_update.get("ingredients", [])
                if raw_ings:
                    candidate_update["ingredients"] = await map_ingredients_to_db(session, raw_ings)
                    mapped_count = sum(1 for i in candidate_update["ingredients"] if i.get("ingredientId"))
                    log.info("ingredients_mapped", job_id=job_id, total=len(raw_ings), mapped=mapped_count)
            except Exception as e:
                log.warning("ingredient_mapping_failed", job_id=job_id, error=str(e))

            # Step 3c: Resolve LLM-suggested tag names to DB tag objects
            raw_tag_names = candidate_update.get("recipeTags", [])
            if raw_tag_names and isinstance(raw_tag_names, list):
                try:
                    candidate_update["recipeTags"] = await _resolve_recipe_tags(raw_tag_names)
                    log.info("tags_resolved", job_id=job_id, count=len(candidate_update["recipeTags"]))
                except Exception as e:
                    log.warning("tag_resolution_failed", job_id=job_id, error=str(e))
                    candidate_update["recipeTags"] = []

            # Step 4: Create candidate
            cand_id = await create_candidate_from_extraction(
                session,
                user_id=user_id,
                source_asset_id=source_asset_id,
                ingestion_job_id=job_id,
                candidate_update=candidate_update,
                provenance=provenance,
                extraction_method=extraction_method,
                review_mode=review_mode,
                review_findings=review_findings,
                canonical_eligible=canonical_eligible,
                draft_eligible=draft_eligible,
                source_artifact_ids=artifact_ids,
            )

            # Step 5: Run review agent on the candidate
            await _emit("review_agent_started", {"candidateId": cand_id})
            try:
                review_result = await run_review_agent(
                    title=candidate_update.get("title", ""),
                    ingredients=candidate_update.get("ingredients", []),
                    steps=candidate_update.get("steps", []),
                    description=candidate_update.get("description"),
                    prep_time_minutes=candidate_update.get("prepTimeMinutes"),
                    cook_time_minutes=candidate_update.get("cookTimeMinutes"),
                    servings=candidate_update.get("servings"),
                    extraction_method=extraction_method,
                )
                review_findings = review_result["reviewFindings"]
                review_mode = review_result["reviewMode"]
                canonical_eligible = review_result["canonicalEligible"]
                draft_eligible = review_result["draftEligible"]
                field_confidence_map = review_result.get("fieldConfidenceMap", {})

                from sqlalchemy import update as sa_update
                from app.models.tables import RecipeCandidate
                await session.execute(
                    sa_update(RecipeCandidate)
                    .where(RecipeCandidate.id == cand_id)
                    .values(
                        review_findings=review_findings,
                        review_mode=review_mode,
                        canonical_eligible=canonical_eligible,
                        draft_eligible=draft_eligible,
                        field_confidence_map=field_confidence_map,
                    )
                )
                await session.flush()

                await _emit("review_agent_completed", {
                    "candidateId": cand_id,
                    "reviewMode": review_mode,
                    "canonicalEligible": canonical_eligible,
                    "findingSummary": review_result.get("findingSummary", {}),
                })
                log.info("review_agent_done", job_id=job_id, candidate_id=cand_id, review_mode=review_mode)
            except Exception as e:
                log.error("review_agent_error", job_id=job_id, candidate_id=cand_id, error=str(e))
                await _emit("review_agent_completed", {
                    "candidateId": cand_id,
                    "error": str(e),
                })

            terminal = "review_ready"
            await _finalize_job(
                session, job_id, terminal, "completed",
                extraction_plan, artifact_ids,
                candidate_id=cand_id, review_mode=review_mode,
            )
            await _emit(f"job.{terminal}", {
                "status": terminal,
                "candidateId": cand_id,
                "canonicalEligible": canonical_eligible,
                "draftEligible": draft_eligible,
            })
            log.info("ingestion_complete", job_id=job_id, candidate_id=cand_id, terminal=terminal)

        else:
            await _finalize_job(session, job_id, "unsupported", "no_recipe_found", extraction_plan, artifact_ids)
            await _emit("job.unsupported", {"status": "unsupported", "message": "Could not extract a recipe from this source"})

    except Exception as e:
        log.error("ingestion_agent_error", job_id=job_id, error=str(e), exc_info=True)
        await _finalize_job(
            session, job_id, "failed", "agent_error", extraction_plan, artifact_ids,
            error_type="internal", error_code="agent_exception",
        )
        await _emit("job.failed", {
            "status": "failed",
            "errorType": "internal",
            "errorCode": "agent_exception",
            "rerunAllowed": True,
            "message": str(e),
        })


def _enrich_provenance_with_source(
    provenance: dict[str, Any],
    social_url: str,
    discovered_url: str,
    extraction_method: str,
) -> dict[str, Any]:
    """Add discovered website URL to provenance so the UI can show both sources."""
    enriched = dict(provenance)
    enriched["_source"] = {
        "socialUrl": social_url,
        "discoveredUrl": discovered_url,
        "extractionMethod": extraction_method,
    }
    return enriched


async def _extract_website_images(
    html: str,
    page_url: str,
    candidate_update: dict[str, Any],
    extract_result_signals: dict[str, Any],
    job_id: str,
    _timed_out,
    *,
    model_override=None,
) -> tuple[list[str], dict[str, list[str]]]:
    """Extract and classify images from a discovered recipe page.

    Returns (image_urls, step_images) just like _extract_from_url does.
    Reusable across social, YouTube, and direct URL flows.
    """
    image_urls: list[str] = list(extract_result_signals.get("imageUrls", []))
    step_images: dict[str, list[str]] = dict(extract_result_signals.get("stepImages", {}))

    if not html or _timed_out():
        return image_urls, step_images

    try:
        image_candidates = extract_images_with_context(html, page_url, limit=20)
        if image_candidates:
            steps = candidate_update.get("steps", [])
            title = candidate_update.get("title", "")
            classified = await classify_recipe_images(
                image_candidates, steps, title,
                model_override=model_override,
            )
            classified_gallery = classified.get("galleryImages", [])
            classified_steps = classified.get("stepImages", {})

            _MAX_GALLERY = 4
            existing_bases = {u.split("?")[0] for u in image_urls}
            for img_url in classified_gallery:
                if len(image_urls) >= _MAX_GALLERY:
                    break
                if img_url.split("?")[0] not in existing_bases:
                    image_urls.append(img_url)
                    existing_bases.add(img_url.split("?")[0])

            for step_num, urls in classified_steps.items():
                if step_num not in step_images:
                    step_images[step_num] = urls
                else:
                    existing_step_bases = {u.split("?")[0] for u in step_images[step_num]}
                    for u in urls:
                        if u.split("?")[0] not in existing_step_bases:
                            step_images[step_num].append(u)

            log.info(
                "images_classified",
                job_id=job_id,
                gallery=len(classified_gallery),
                step_images=len(classified_steps),
                skipped=len(image_candidates) - len(classified_gallery) - sum(len(v) for v in classified_steps.values()),
            )
    except Exception as exc:
        log.warning("image_classification_failed", job_id=job_id, error=str(exc))

    return image_urls, step_images


async def _extract_from_url(session, job_id, url, source_subtype, _run_tool, _emit, artifacts, _timed_out, *, model_override=None, available_tag_names=None):
    candidate_update = None
    provenance: dict[str, Any] = {}
    extraction_method = ""
    extracted_image_urls: list[str] = []
    extracted_step_images: dict[str, list[str]] = {}

    # Fetch the page
    fetch_result = await _run_tool("httpx_fetch", httpx_fetch, url)
    if not fetch_result.success:
        return None, {}, "", [], {}

    html = fetch_result.signals.get("html", "")
    has_schema = fetch_result.signals.get("has_recipe_schema", False)

    # Try schema extraction first (fastest, most reliable)
    if has_schema:
        schema_result = await _run_tool("check_schema_markup", check_schema_markup, html)
        if schema_result.success and schema_result.signals.get("recipeSchema"):
            extract_result = await _run_tool(
                "schema_recipe_extract",
                schema_recipe_extract,
                schema_result.signals["recipeSchema"],
            )
            if extract_result.success and extract_result.candidate_update:
                candidate_update = extract_result.candidate_update
                provenance = extract_result.signals.get("provenance", {})
                extraction_method = "schema_recipe_markup"
                extracted_image_urls = extract_result.signals.get("imageUrls", [])
                extracted_step_images = extract_result.signals.get("stepImages", {})

    # If no schema or schema extraction failed, try page text + LLM
    if candidate_update is None and not _timed_out():
        await _emit("job.state_changed", {"status": "processing", "internalState": "text_extraction"})

        text_result = await _run_tool("extract_page_text", extract_page_text, html, url)
        if text_result.success:
            cleaned_text = text_result.signals.get("cleanedText", "")
            if cleaned_text and len(cleaned_text) >= 100:
                llm_result = await _run_tool(
                    "llm_structured_extract",
                    llm_structured_extract,
                    cleaned_text,
                    "webpage text",
                    model_override=model_override,
                    available_tags=available_tag_names,
                )
                if llm_result.success and llm_result.candidate_update:
                    candidate_update = llm_result.candidate_update
                    provenance = llm_result.signals.get("provenance", {})
                    extraction_method = "llm_structured_extract_webpage"
                    extracted_image_urls = extract_images_from_html(html, url, limit=4)

    # If still nothing, try extracting recipe links from page and following them
    if candidate_update is None and not _timed_out():
        link_result = await _run_tool("extract_recipe_links", extract_recipe_links, html)
        recipe_urls = link_result.signals.get("urls", [])
        for link_info in recipe_urls[:2]:
            if _timed_out():
                break
            linked_url = link_info.get("url", "")
            if linked_url and linked_url != url:
                linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, linked_url)
                if linked_fetch.success:
                    linked_html = linked_fetch.signals.get("html", "")
                    if linked_fetch.signals.get("has_recipe_schema"):
                        linked_schema = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                        if linked_schema.success and linked_schema.signals.get("recipeSchema"):
                            linked_extract = await _run_tool(
                                "schema_recipe_extract",
                                schema_recipe_extract,
                                linked_schema.signals["recipeSchema"],
                            )
                            if linked_extract.success and linked_extract.candidate_update:
                                candidate_update = linked_extract.candidate_update
                                provenance = linked_extract.signals.get("provenance", {})
                                extraction_method = "schema_from_linked_page"
                                extracted_image_urls = linked_extract.signals.get("imageUrls", [])
                                extracted_step_images = linked_extract.signals.get("stepImages", {})
                                break

    # Smart image extraction: extract with context, then LLM-classify & map to steps
    if candidate_update and html and not _timed_out():
        extracted_image_urls, extracted_step_images = await _extract_website_images(
            html, url, candidate_update,
            {"imageUrls": extracted_image_urls, "stepImages": extracted_step_images},
            job_id, _timed_out,
            model_override=model_override,
        )

    # Extract how-to-serve from HTML
    if candidate_update and html and not candidate_update.get("howToServe"):
        serve_text = extract_how_to_serve_from_html(html)
        if serve_text:
            candidate_update["howToServe"] = serve_text
            log.info("how_to_serve_extracted", job_id=job_id)

    # Extract chef's notes from HTML (Tier 1) + LLM fallback (Tier 2)
    if candidate_update and html:
        existing_notes = candidate_update.get("notes") or []
        if not existing_notes:
            html_notes = extract_chef_notes_from_html(html)
            if html_notes:
                candidate_update["notes"] = html_notes
                log.info("notes_extracted_html", job_id=job_id, count=len(html_notes))
            elif not _timed_out():
                page_text = ""
                if fetch_result.success:
                    text_result_for_notes = await _run_tool("extract_page_text", extract_page_text, html, url)
                    if text_result_for_notes.success:
                        page_text = text_result_for_notes.signals.get("cleanedText", "")
                if page_text and len(page_text) >= 100:
                    llm_notes = await extract_chef_notes_llm(page_text, model_override=model_override)
                    if llm_notes:
                        candidate_update["notes"] = llm_notes
                        log.info("notes_extracted_llm", job_id=job_id, count=len(llm_notes))

    return candidate_update, provenance, extraction_method, extracted_image_urls, extracted_step_images


async def _extract_from_text(session, job_id, raw_text, _run_tool, _emit, _timed_out, *, model_override=None, available_tag_names=None):
    await _emit("job.state_changed", {"status": "processing", "internalState": "text_extraction"})

    # Generate source preview
    await _run_tool("create_text_preview", create_text_preview, raw_text)

    # Clean text
    clean_result = await _run_tool("clean_text", clean_text, raw_text)
    cleaned = clean_result.signals.get("cleanedText", raw_text) if clean_result.success else raw_text

    if _timed_out():
        return None, {}, ""

    # Analyze structure
    analysis_result = await _run_tool("analyze_text_structure", analyze_text_structure, cleaned)
    source_desc = "pasted text"
    if analysis_result.success:
        likelihood = analysis_result.signals.get("recipeLikelihood", "low")
        if likelihood == "high":
            source_desc = "structured recipe text"
        elif likelihood == "medium":
            source_desc = "recipe-like text"

    if _timed_out():
        return None, {}, ""

    # LLM extraction
    llm_result = await _run_tool(
        "llm_structured_extract",
        llm_structured_extract,
        cleaned,
        source_desc,
        model_override=model_override,
        available_tags=available_tag_names,
    )

    if llm_result.success and llm_result.candidate_update:
        return (
            llm_result.candidate_update,
            llm_result.signals.get("provenance", {}),
            f"llm_structured_extract_{source_desc.replace(' ', '_')}",
        )

    return None, {}, ""


async def _extract_from_image(session, job_id, file_asset_ref, _run_tool, _emit, _timed_out, *, model_override=None, available_tag_names=None):
    """Process an image source: OCR → assess → LLM extract → enrich → crop dish photo."""
    await _emit("job.state_changed", {"status": "processing", "internalState": "image_processing"})

    review_mode_override: str | None = None
    candidate_update = None
    provenance: dict[str, Any] = {}
    extraction_method = ""

    # Source preview
    await _run_tool("create_image_preview", create_image_preview, file_asset_ref)

    # OCR extraction
    ocr_result = await _run_tool("ocr_extract", ocr_extract, file_asset_ref)

    if not ocr_result.success:
        log.warning("ocr_failed_trying_multimodal", job_id=job_id)
        fallback = await _run_tool(
            "multimodal_llm_extract",
            multimodal_llm_extract,
            file_asset_ref,
            None,
            model_override=model_override,
            available_tags=available_tag_names,
        )
        if fallback.success and fallback.candidate_update:
            candidate_update = fallback.candidate_update
            provenance = fallback.signals.get("provenance", {})
            extraction_method = "multimodal_llm_fallback"
            review_mode_override = "reconstruction"

    if candidate_update is None and ocr_result.success:
        extracted_text = ocr_result.signals.get("extractedText", "")
        confidence = ocr_result.signals.get("overallConfidence", 0.0)
        handwriting = ocr_result.signals.get("handwritingDetected", False)
        quality = ocr_result.signals.get("qualityAssessment", "acceptable")

        if handwriting:
            review_mode_override = "reconstruction"

        if _timed_out():
            return None, {}, "", None, []

        if quality in ("unusable", "very_low"):
            log.info("ocr_quality_low_using_fallback", job_id=job_id, quality=quality, confidence=confidence)
            await _emit("job.state_changed", {"status": "processing", "internalState": "multimodal_fallback"})

            fallback = await _run_tool(
                "multimodal_llm_extract",
                multimodal_llm_extract,
                file_asset_ref,
                extracted_text if quality != "unusable" else None,
                model_override=model_override,
                available_tags=available_tag_names,
            )
            if fallback.success and fallback.candidate_update:
                candidate_update = fallback.candidate_update
                provenance = fallback.signals.get("provenance", {})
                extraction_method = "multimodal_llm_fallback"
                if not review_mode_override:
                    review_mode_override = "reconstruction"
        else:
            if not _timed_out():
                ocr_artifacts = [
                    {"artifactType": "ocr_text", "payload": {"text": extracted_text}},
                ]
                await _run_tool("assess_parseability", assess_parseability, ocr_artifacts, "image")

                source_desc = "handwritten recipe image (OCR)" if handwriting else "recipe image (OCR)"
                llm_result = await _run_tool(
                    "llm_structured_extract",
                    llm_structured_extract,
                    extracted_text,
                    source_desc,
                    model_override=model_override,
                    available_tags=available_tag_names,
                )

                if llm_result.success and llm_result.candidate_update:
                    candidate_update = llm_result.candidate_update
                    provenance = llm_result.signals.get("provenance", {})
                    extraction_method = "ocr_then_llm_extract"

            if candidate_update is None and not _timed_out():
                log.info("llm_ocr_parse_failed_trying_multimodal", job_id=job_id)
                fallback = await _run_tool(
                    "multimodal_llm_extract",
                    multimodal_llm_extract,
                    file_asset_ref,
                    extracted_text,
                    model_override=model_override,
                    available_tags=available_tag_names,
                )
                if fallback.success and fallback.candidate_update:
                    candidate_update = fallback.candidate_update
                    provenance = fallback.signals.get("provenance", {})
                    extraction_method = "multimodal_llm_fallback"
                    if not review_mode_override:
                        review_mode_override = "reconstruction"

    if candidate_update is None:
        return None, {}, "", None, []

    # --- Post-extraction enrichment ---
    if not _timed_out():
        await _emit("job.state_changed", {"status": "processing", "internalState": "enriching_recipe"})
        try:
            candidate_update = await enrich_extracted_recipe(
                candidate_update, model_override=model_override,
            )
            extraction_method += "+enriched"
            log.info("image_recipe_enriched", job_id=job_id)
        except Exception as exc:
            log.warning("enrichment_failed", job_id=job_id, error=str(exc))

    # --- Dish photo cropping ---
    extracted_image_urls: list[str] = []
    if not _timed_out():
        try:
            image_bytes = _resolve_image_bytes(file_asset_ref)
            if image_bytes:
                await _emit("job.state_changed", {"status": "processing", "internalState": "extracting_dish_photo"})
                crop_result = await extract_dish_photo_from_image(
                    image_bytes, model_override=model_override,
                )
                if crop_result is not None:
                    cropped_bytes, region = crop_result
                    from app.core.config import get_settings
                    from app.core.s3 import build_asset_ref, get_s3_client
                    settings = get_settings()
                    if settings.s3_bucket:
                        crop_key = build_asset_ref("dish_photo", "system", "cropped_dish.jpg")
                        s3 = get_s3_client()
                        s3.put_object(
                            Bucket=settings.s3_bucket,
                            Key=crop_key,
                            Body=cropped_bytes,
                            ContentType="image/jpeg",
                        )
                        extracted_image_urls.append(crop_key)
                        log.info("dish_photo_saved", job_id=job_id, key=crop_key, region=region)
        except Exception as exc:
            log.warning("dish_photo_crop_failed", job_id=job_id, error=str(exc))

    return candidate_update, provenance, extraction_method, review_mode_override, extracted_image_urls


async def _extract_from_youtube(session, job_id, url, _run_tool, _emit, artifacts, _timed_out, *, model_override=None, available_tag_names=None):
    """YouTube extraction fallback ladder: API metadata → description links → comments →
    description text → transcript → video processing."""
    await _emit("job.state_changed", {"status": "processing", "internalState": "youtube_extraction"})

    candidate_update = None
    provenance: dict[str, Any] = {}
    extraction_method = ""
    review_mode_override: str | None = None

    video_id = extract_video_id(url)
    if not video_id:
        log.warning("youtube_invalid_url", url=url, job_id=job_id)
        return None, {}, "", None

    # Step 1: Fetch YouTube API metadata (title, description, first comment, thumbnail)
    api_result = await _run_tool("youtube_api_fetch", youtube_api_fetch, video_id)
    description = ""
    first_comment = ""
    thumbnail_url = ""
    if api_result.success:
        description = api_result.signals.get("description", "")
        first_comment = api_result.signals.get("firstComment", "")
        thumbnail_url = api_result.signals.get("thumbnailUrl", "")

    # Step 1a: Extract recipe links from description → fetch linked page → schema/llm extract
    if description and not _timed_out():
        link_result = await _run_tool("extract_recipe_links", extract_recipe_links, description)
        recipe_urls = link_result.signals.get("urls", [])
        for link_info in recipe_urls[:3]:
            if _timed_out():
                break
            linked_url = link_info.get("url", "")
            if not linked_url:
                continue
            linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, linked_url)
            if not linked_fetch.success:
                continue
            linked_html = linked_fetch.signals.get("html", "")
            if linked_fetch.signals.get("has_recipe_schema"):
                schema_result = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                if schema_result.success and schema_result.signals.get("recipeSchema"):
                    extract_result = await _run_tool(
                        "schema_recipe_extract", schema_recipe_extract,
                        schema_result.signals["recipeSchema"],
                    )
                    if extract_result.success and extract_result.candidate_update:
                        img_urls, step_imgs = await _extract_website_images(
                            linked_html, linked_url, extract_result.candidate_update,
                            extract_result.signals, job_id, _timed_out, model_override=model_override,
                        )
                        prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, linked_url, "youtube_description_link_schema")
                        return extract_result.candidate_update, prov, "youtube_description_link_schema", None, img_urls, step_imgs
            text_result = await _run_tool("extract_page_text", extract_page_text, linked_html, linked_url)
            if text_result.success:
                cleaned = text_result.signals.get("cleanedText", "")
                if cleaned and len(cleaned) >= 100:
                    llm_result = await _run_tool(
                        "llm_structured_extract", llm_structured_extract,
                        cleaned, "linked page from YouTube description",
                        model_override=model_override, available_tags=available_tag_names,
                    )
                    if llm_result.success and llm_result.candidate_update:
                        img_urls = extract_images_from_html(linked_html, linked_url, limit=4)
                        prov = _enrich_provenance_with_source(llm_result.signals.get("provenance", {}), url, linked_url, "youtube_description_link_llm")
                        return llm_result.candidate_update, prov, "youtube_description_link_llm", None, img_urls, {}

    # Step 2: Extract recipe links from first comment
    if first_comment and candidate_update is None and not _timed_out():
        comment_link_result = await _run_tool("extract_recipe_links", extract_recipe_links, first_comment)
        comment_urls = comment_link_result.signals.get("urls", [])
        for link_info in comment_urls[:2]:
            if _timed_out():
                break
            linked_url = link_info.get("url", "")
            if not linked_url:
                continue
            linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, linked_url)
            if not linked_fetch.success:
                continue
            linked_html = linked_fetch.signals.get("html", "")
            if linked_fetch.signals.get("has_recipe_schema"):
                schema_result = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                if schema_result.success and schema_result.signals.get("recipeSchema"):
                    extract_result = await _run_tool(
                        "schema_recipe_extract", schema_recipe_extract,
                        schema_result.signals["recipeSchema"],
                    )
                    if extract_result.success and extract_result.candidate_update:
                        img_urls, step_imgs = await _extract_website_images(
                            linked_html, linked_url, extract_result.candidate_update,
                            extract_result.signals, job_id, _timed_out, model_override=model_override,
                        )
                        prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, linked_url, "youtube_comment_link_schema")
                        return extract_result.candidate_update, prov, "youtube_comment_link_schema", None, img_urls, step_imgs

    # Step 3: Discover recipe on websites mentioned in description (e.g. "get the recipe at mysite DOT COM")
    if description and candidate_update is None and not _timed_out():
        mentioned_sites = _extract_mentioned_sites(description)
        for site_url in mentioned_sites:
            if _timed_out():
                break
            keywords = _extract_keywords_from_caption(description)
            discover_result = await _run_tool(
                "discover_recipe_on_site", discover_recipe_on_site,
                site_url, keywords or ["recipe"],
            )
            if discover_result.success:
                found_html = discover_result.signals.get("html", "")
                found_url = discover_result.signals.get("found_url", site_url)
                if discover_result.signals.get("has_schema"):
                    schema_result = await _run_tool("check_schema_markup", check_schema_markup, found_html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = await _run_tool(
                            "schema_recipe_extract", schema_recipe_extract,
                            schema_result.signals["recipeSchema"],
                        )
                        if extract_result.success and extract_result.candidate_update:
                            img_urls, step_imgs = await _extract_website_images(
                                found_html, found_url, extract_result.candidate_update,
                                extract_result.signals, job_id, _timed_out, model_override=model_override,
                            )
                            prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, found_url, "youtube_description_site_schema")
                            return extract_result.candidate_update, prov, "youtube_description_site_schema", None, img_urls, step_imgs

    # Step 4: Structured text from description → LLM extract
    # Only trust description extraction if the text contains actual recipe content
    # (ingredient-like patterns: quantities, measurements, ingredient lists).
    # Promotional/marketing descriptions without recipe data produce hallucinated results.
    if description and candidate_update is None and not _timed_out():
        if len(description) >= 80 and _description_has_recipe_content(description):
            llm_desc_result = await _run_tool(
                "llm_structured_extract", llm_structured_extract,
                description, "YouTube video description",
                model_override=model_override, available_tags=available_tag_names,
            )
            if llm_desc_result.success and llm_desc_result.candidate_update:
                yt_imgs = [thumbnail_url] if thumbnail_url else []
                return llm_desc_result.candidate_update, llm_desc_result.signals.get("provenance", {}), "youtube_description_llm", None, yt_imgs, {}

    # Step 5: Transcript → LLM extract
    if candidate_update is None and not _timed_out():
        transcript_result = await _run_tool("youtube_transcript_fetch", youtube_transcript_fetch, video_id)
        if transcript_result.success:
            transcript_text = transcript_result.signals.get("transcript_text", "")
            if transcript_text and len(transcript_text) >= 50:
                llm_transcript = await _run_tool(
                    "llm_structured_extract", llm_structured_extract,
                    transcript_text, "YouTube video transcript",
                    model_override=model_override, available_tags=available_tag_names,
                )
                if llm_transcript.success and llm_transcript.candidate_update:
                    yt_imgs = [thumbnail_url] if thumbnail_url else []
                    return llm_transcript.candidate_update, llm_transcript.signals.get("provenance", {}), "youtube_transcript_llm", "reconstruction", yt_imgs, {}

    # Step 6: Full video processing fallback (download → whisper + frames → merge)
    if candidate_update is None and not _timed_out():
        result = await _extract_via_video_processing(
            job_id, url, _run_tool, _emit, _timed_out,
            model_override=model_override, available_tag_names=available_tag_names,
        )
        if result:
            cu, prov, method, rmo, fb_imgs = result
            yt_imgs = [thumbnail_url] if thumbnail_url else fb_imgs
            return cu, prov, method, rmo, yt_imgs, {}

    yt_imgs = [thumbnail_url] if thumbnail_url and candidate_update else []
    return candidate_update, provenance, extraction_method, review_mode_override, yt_imgs, {}


async def _extract_from_social_photo(session, job_id, url, source_subtype, _run_tool, _emit, _timed_out, *, model_override=None, available_tag_names=None):
    """Social media PHOTO post flow: HTTP scrape → caption recipe extraction → image OCR/multimodal fallback.

    No yt-dlp involved — this is for photo posts only.
    """
    platform = source_subtype.replace("_photo", "")
    await _emit("job.state_changed", {"status": "processing", "internalState": "social_photo_extraction"})

    review_mode_override: str | None = None
    image_urls: list[str] = []

    # Step 1: Fetch the social page via HTTP to get OG caption + image
    page_result = await _run_tool("fetch_social_post_page", fetch_social_post_page, url)

    caption = ""
    post_image_url = ""
    all_image_urls: list[str] = []

    if page_result.success:
        caption = page_result.signals.get("caption", "")
        post_image_url = page_result.signals.get("image_url", "")
        all_image_urls = page_result.signals.get("all_image_urls", [])
        page_html = page_result.signals.get("html", "")

        # Also try to pull recipe links from the caption
        if caption and not _timed_out():
            link_result = await _run_tool("extract_recipe_links", extract_recipe_links, caption)
            recipe_urls = link_result.signals.get("urls", [])
            for link_info in recipe_urls[:3]:
                if _timed_out():
                    break
                linked_url = link_info.get("url", "")
                if not linked_url:
                    continue
                linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, linked_url)
                if not linked_fetch.success:
                    continue
                linked_html = linked_fetch.signals.get("html", "")
                if linked_fetch.signals.get("has_recipe_schema"):
                    schema_result = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = await _run_tool(
                            "schema_recipe_extract", schema_recipe_extract,
                            schema_result.signals["recipeSchema"],
                        )
                        if extract_result.success and extract_result.candidate_update:
                            img_urls, step_imgs = await _extract_website_images(
                                linked_html, linked_url, extract_result.candidate_update,
                                extract_result.signals, job_id, _timed_out, model_override=model_override,
                            )
                            prov = _enrich_provenance_with_source(
                                extract_result.signals.get("provenance", {}), url, linked_url,
                                f"{platform}_photo_caption_link_schema",
                            )
                            return extract_result.candidate_update, prov, f"{platform}_photo_caption_link_schema", None, img_urls
                text_result = await _run_tool("extract_page_text", extract_page_text, linked_html, linked_url)
                if text_result.success:
                    cleaned = text_result.signals.get("cleanedText", "")
                    if cleaned and len(cleaned) >= 100:
                        llm_result = await _run_tool(
                            "llm_structured_extract", llm_structured_extract,
                            cleaned, f"linked page from {platform} photo caption",
                            model_override=model_override, available_tags=available_tag_names,
                        )
                        if llm_result.success and llm_result.candidate_update:
                            linked_imgs = extract_images_from_html(linked_html, linked_url, limit=4)
                            prov = _enrich_provenance_with_source(
                                llm_result.signals.get("provenance", {}), url, linked_url,
                                f"{platform}_photo_caption_link_llm",
                            )
                            return llm_result.candidate_update, prov, f"{platform}_photo_caption_link_llm", None, linked_imgs

    # Helper: check if the post photo is a food image and suitable as hero
    async def _check_food_photo_for_hero() -> list[str]:
        """Quick multimodal check if the social post photo is a food image. Returns image_urls list."""
        if not post_image_url or _timed_out():
            return []
        await _emit("job.state_changed", {"status": "processing", "internalState": "checking_food_photo"})
        check_result = await _run_tool(
            "multimodal_llm_extract", multimodal_llm_extract,
            post_image_url, None,
            model_override=model_override, available_tags=available_tag_names,
        )
        is_food = check_result.signals.get("isFoodPhoto", False)
        if is_food:
            log.info("social_photo_is_food", job_id=job_id, image_url=post_image_url)
            return [post_image_url]
        return []

    # Step 2: Try LLM extraction directly from caption text
    if caption and len(caption) >= 80 and not _timed_out():
        await _emit("job.state_changed", {"status": "processing", "internalState": "caption_recipe_extraction"})
        llm_caption_result = await _run_tool(
            "llm_structured_extract", llm_structured_extract,
            caption, f"{platform} photo post caption",
            model_override=model_override, available_tags=available_tag_names,
        )
        if llm_caption_result.success and llm_caption_result.candidate_update:
            hero_imgs = await _check_food_photo_for_hero()
            prov = llm_caption_result.signals.get("provenance", {})
            prov["socialUrl"] = url
            prov["extractionNote"] = f"Recipe extracted from {platform} photo post caption"
            return llm_caption_result.candidate_update, prov, f"{platform}_photo_caption_llm", None, hero_imgs

    # Step 3: Try mentioned website discovery from caption
    if caption and not _timed_out():
        mentioned_sites = _extract_mentioned_sites(caption)
        for site_url in mentioned_sites:
            if _timed_out():
                break
            keywords = _extract_keywords_from_caption(caption)
            discover_result = await _run_tool(
                "discover_recipe_on_site", discover_recipe_on_site,
                site_url, keywords or ["recipe"],
            )
            if discover_result.success:
                found_html = discover_result.signals.get("html", "")
                found_url = discover_result.signals.get("found_url", site_url)
                if discover_result.signals.get("has_schema"):
                    schema_result = await _run_tool("check_schema_markup", check_schema_markup, found_html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = await _run_tool(
                            "schema_recipe_extract", schema_recipe_extract,
                            schema_result.signals["recipeSchema"],
                        )
                        if extract_result.success and extract_result.candidate_update:
                            img_urls, step_imgs = await _extract_website_images(
                                found_html, found_url, extract_result.candidate_update,
                                extract_result.signals, job_id, _timed_out, model_override=model_override,
                            )
                            if not img_urls:
                                img_urls = await _check_food_photo_for_hero()
                            prov = _enrich_provenance_with_source(
                                extract_result.signals.get("provenance", {}), url, found_url,
                                f"{platform}_photo_site_discovery_schema",
                            )
                            return extract_result.candidate_update, prov, f"{platform}_photo_site_discovery_schema", None, img_urls

    # Step 4: Fallback — process the photo itself via multimodal LLM (same as image upload)
    if post_image_url and not _timed_out():
        await _emit("job.state_changed", {"status": "processing", "internalState": "photo_image_extraction"})
        log.info("social_photo_image_fallback", job_id=job_id, image_url=post_image_url)

        multimodal_result = await _run_tool(
            "multimodal_llm_extract", multimodal_llm_extract,
            post_image_url, caption if caption else None,
            model_override=model_override, available_tags=available_tag_names,
        )
        if multimodal_result.success and multimodal_result.candidate_update:
            is_food = multimodal_result.signals.get("isFoodPhoto", False)
            if is_food:
                image_urls = [post_image_url] + [u for u in all_image_urls if u != post_image_url]
            prov = multimodal_result.signals.get("provenance", {})
            prov["socialUrl"] = url
            prov["extractionNote"] = f"Recipe extracted from {platform} photo via image analysis"
            review_mode_override = "reconstruction"

            if not _timed_out():
                try:
                    candidate_update = await enrich_extracted_recipe(
                        multimodal_result.candidate_update, model_override=model_override,
                    )
                    return candidate_update, prov, f"{platform}_photo_multimodal+enriched", review_mode_override, image_urls
                except Exception:
                    pass
            return multimodal_result.candidate_update, prov, f"{platform}_photo_multimodal", review_mode_override, image_urls

    return None, {}, "", None, []


async def _extract_from_social(session, job_id, url, source_subtype, _run_tool, _emit, artifacts, _timed_out, *, model_override=None, available_tag_names=None):
    """Social media VIDEO extraction flow: caption links → creator profile → bio links → site search."""
    await _emit("job.state_changed", {"status": "processing", "internalState": "social_extraction"})

    review_mode_override: str | None = None

    # Step 1: Fetch post metadata via yt-dlp
    meta_result = await _run_tool("yt_dlp_fetch_metadata", yt_dlp_fetch_metadata, url)
    caption = ""
    creator_url = ""
    thumbnail_url = ""
    if meta_result.success:
        caption = meta_result.signals.get("social_caption", "")
        creator_url = meta_result.signals.get("creator_url", "")
        if not creator_url:
            creator_url = meta_result.signals.get("video_metadata", {}).get("creatorUrl", "")
        thumbnail_url = meta_result.signals.get("video_metadata", {}).get("thumbnailUrl", "")

    # Step 1a: Extract recipe links from caption
    if caption and not _timed_out():
        link_result = await _run_tool("extract_recipe_links", extract_recipe_links, caption)
        recipe_urls = link_result.signals.get("urls", [])
        for link_info in recipe_urls[:3]:
            if _timed_out():
                break
            linked_url = link_info.get("url", "")
            if not linked_url:
                continue
            linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, linked_url)
            if not linked_fetch.success:
                continue
            linked_html = linked_fetch.signals.get("html", "")
            if linked_fetch.signals.get("has_recipe_schema"):
                schema_result = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                if schema_result.success and schema_result.signals.get("recipeSchema"):
                    extract_result = await _run_tool(
                        "schema_recipe_extract", schema_recipe_extract,
                        schema_result.signals["recipeSchema"],
                    )
                    if extract_result.success and extract_result.candidate_update:
                        img_urls, step_imgs = await _extract_website_images(
                            linked_html, linked_url, extract_result.candidate_update,
                            extract_result.signals, job_id, _timed_out, model_override=model_override,
                        )
                        prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, linked_url, f"{source_subtype}_caption_link_schema")
                        return extract_result.candidate_update, prov, f"{source_subtype}_caption_link_schema", None, img_urls, step_imgs
            text_result = await _run_tool("extract_page_text", extract_page_text, linked_html, linked_url)
            if text_result.success:
                cleaned = text_result.signals.get("cleanedText", "")
                if cleaned and len(cleaned) >= 100:
                    llm_result = await _run_tool(
                        "llm_structured_extract", llm_structured_extract,
                        cleaned, f"linked page from {source_subtype} caption",
                        model_override=model_override, available_tags=available_tag_names,
                    )
                    if llm_result.success and llm_result.candidate_update:
                        img_urls = extract_images_from_html(linked_html, linked_url, limit=4)
                        prov = _enrich_provenance_with_source(llm_result.signals.get("provenance", {}), url, linked_url, f"{source_subtype}_caption_link_llm")
                        return llm_result.candidate_update, prov, f"{source_subtype}_caption_link_llm", None, img_urls, {}

    # Step 2: Fetch creator profile → expand bio links → follow best link
    if creator_url and not _timed_out():
        profile_result = await _run_tool("fetch_creator_profile", fetch_creator_profile, creator_url)
        if profile_result.success:
            bio_urls = profile_result.signals.get("bio_urls", [])
            if bio_urls:
                expand_result = await _run_tool("expand_bio_links", expand_bio_links, bio_urls)
                if expand_result.success:
                    best_link = expand_result.signals.get("best_recipe_link")
                    if best_link and not _timed_out():
                        linked_fetch = await _run_tool("httpx_fetch", httpx_fetch, best_link)
                        if linked_fetch.success:
                            linked_html = linked_fetch.signals.get("html", "")
                            if linked_fetch.signals.get("has_recipe_schema"):
                                schema_result = await _run_tool("check_schema_markup", check_schema_markup, linked_html)
                                if schema_result.success and schema_result.signals.get("recipeSchema"):
                                    extract_result = await _run_tool(
                                        "schema_recipe_extract", schema_recipe_extract,
                                        schema_result.signals["recipeSchema"],
                                    )
                                    if extract_result.success and extract_result.candidate_update:
                                        img_urls, step_imgs = await _extract_website_images(
                                            linked_html, best_link, extract_result.candidate_update,
                                            extract_result.signals, job_id, _timed_out, model_override=model_override,
                                        )
                                        prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, best_link, f"{source_subtype}_bio_link_schema")
                                        return extract_result.candidate_update, prov, f"{source_subtype}_bio_link_schema", None, img_urls, step_imgs
                            text_result = await _run_tool("extract_page_text", extract_page_text, linked_html, best_link)
                            if text_result.success:
                                cleaned = text_result.signals.get("cleanedText", "")
                                if cleaned and len(cleaned) >= 100:
                                    llm_result = await _run_tool(
                                        "llm_structured_extract", llm_structured_extract,
                                        cleaned, f"creator blog from {source_subtype} bio",
                                        model_override=model_override, available_tags=available_tag_names,
                                    )
                                    if llm_result.success and llm_result.candidate_update:
                                        img_urls = extract_images_from_html(linked_html, best_link, limit=4)
                                        prov = _enrich_provenance_with_source(llm_result.signals.get("provenance", {}), url, best_link, f"{source_subtype}_bio_link_llm")
                                        return llm_result.candidate_update, prov, f"{source_subtype}_bio_link_llm", None, img_urls, {}

    # Step 3: Discover recipe on creator's site using caption keywords
    if creator_url and caption and not _timed_out():
        keywords = _extract_keywords_from_caption(caption)
        if keywords:
            from urllib.parse import urlparse as _urlparse
            parsed_creator = _urlparse(creator_url)
            site_base = f"{parsed_creator.scheme}://{parsed_creator.hostname}"

            discover_result = await _run_tool(
                "discover_recipe_on_site", discover_recipe_on_site,
                site_base, keywords,
            )
            if discover_result.success:
                found_html = discover_result.signals.get("html", "")
                found_url = discover_result.signals.get("found_url", site_base)
                if discover_result.signals.get("has_schema"):
                    schema_result = await _run_tool("check_schema_markup", check_schema_markup, found_html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = await _run_tool(
                            "schema_recipe_extract", schema_recipe_extract,
                            schema_result.signals["recipeSchema"],
                        )
                        if extract_result.success and extract_result.candidate_update:
                            img_urls, step_imgs = await _extract_website_images(
                                found_html, found_url, extract_result.candidate_update,
                                extract_result.signals, job_id, _timed_out, model_override=model_override,
                            )
                            prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, found_url, f"{source_subtype}_site_discovery_schema")
                            return extract_result.candidate_update, prov, f"{source_subtype}_site_discovery_schema", None, img_urls, step_imgs

    # Step 3b: Discover recipe on website mentioned in caption (e.g. "visit PLANTYOU DOT COM")
    if caption and not _timed_out():
        mentioned_sites = _extract_mentioned_sites(caption)
        for site_url in mentioned_sites:
            if _timed_out():
                break
            keywords = _extract_keywords_from_caption(caption)
            discover_result = await _run_tool(
                "discover_recipe_on_site", discover_recipe_on_site,
                site_url, keywords or ["recipe"],
            )
            if discover_result.success:
                found_html = discover_result.signals.get("html", "")
                found_url = discover_result.signals.get("found_url", site_url)
                if discover_result.signals.get("has_schema"):
                    schema_result = await _run_tool("check_schema_markup", check_schema_markup, found_html)
                    if schema_result.success and schema_result.signals.get("recipeSchema"):
                        extract_result = await _run_tool(
                            "schema_recipe_extract", schema_recipe_extract,
                            schema_result.signals["recipeSchema"],
                        )
                        if extract_result.success and extract_result.candidate_update:
                            img_urls, step_imgs = await _extract_website_images(
                                found_html, found_url, extract_result.candidate_update,
                                extract_result.signals, job_id, _timed_out, model_override=model_override,
                            )
                            prov = _enrich_provenance_with_source(extract_result.signals.get("provenance", {}), url, found_url, f"{source_subtype}_caption_site_schema")
                            return extract_result.candidate_update, prov, f"{source_subtype}_caption_site_schema", None, img_urls, step_imgs

    # Step 3c: LLM extract directly from caption text (Instagram/TikTok captions often contain the full recipe)
    if caption and len(caption) >= 80 and not _timed_out():
        llm_caption_result = await _run_tool(
            "llm_structured_extract", llm_structured_extract,
            caption, f"{source_subtype} post caption",
            model_override=model_override, available_tags=available_tag_names,
        )
        if llm_caption_result.success and llm_caption_result.candidate_update:
            social_imgs = [thumbnail_url] if thumbnail_url else []
            return llm_caption_result.candidate_update, llm_caption_result.signals.get("provenance", {}), f"{source_subtype}_caption_llm", None, social_imgs, {}

    # Step 4: Video processing fallback
    if not _timed_out():
        result = await _extract_via_video_processing(
            job_id, url, _run_tool, _emit, _timed_out,
            model_override=model_override, available_tag_names=available_tag_names,
        )
        if result:
            cu, prov, method, rmo, fb_imgs = result
            social_imgs = [thumbnail_url] if thumbnail_url else fb_imgs
            return cu, prov, method, rmo, social_imgs, {}

    return None, {}, "", None, [], {}


async def _extract_via_video_processing(job_id, url, _run_tool, _emit, _timed_out, *, model_override=None, available_tag_names=None):
    """Shared video processing fallback: download → whisper + frames → merge → LLM extract.

    Returns a 4-tuple (candidate_update, provenance, method, review_mode) on success,
    or None on failure.  When frames are available, also stores a fallback thumbnail
    path in the returned candidate_update under ``_fallback_thumbnail_path`` so callers
    can upload it when no external thumbnail URL is available.
    """
    await _emit("job.state_changed", {"status": "processing", "internalState": "video_processing"})

    tmp_dirs: list[str] = []
    fallback_thumb_path: str | None = None

    try:
        download_result = await _run_tool("yt_dlp_download_video", yt_dlp_download_video, url)
        if not download_result.success:
            return None

        video_path = download_result.signals.get("video_path", "")
        tmp_dir = download_result.signals.get("tmp_dir", "")
        if tmp_dir:
            tmp_dirs.append(tmp_dir)

        if not video_path or _timed_out():
            return None

        partials: list[dict] = []

        # Whisper transcription
        whisper_result = await _run_tool("whisper_transcribe", whisper_transcribe, video_path)
        if whisper_result.success:
            transcript_text = whisper_result.signals.get("transcript_text", "")
            log.info("whisper_result", job_id=job_id, text_len=len(transcript_text), success=True)
            if transcript_text:
                partials.append({"source": "whisper_transcript", "text": transcript_text})
        else:
            log.warning("whisper_failed", job_id=job_id, message=whisper_result.message)

        # Frame extraction + LLM analysis (batched for long videos)
        if not _timed_out():
            frames_result = await _run_tool("extract_key_frames", extract_key_frames, video_path)
            if frames_result.success:
                frame_paths = frames_result.signals.get("frame_paths", [])
                frames_dir = frames_result.signals.get("frames_dir", "")
                log.info("frames_extracted", job_id=job_id, count=len(frame_paths))
                if frames_dir:
                    tmp_dirs.append(frames_dir)

                if frame_paths:
                    mid = len(frame_paths) // 2
                    fallback_thumb_path = frame_paths[mid]

                if frame_paths and not _timed_out():
                    BATCH_SIZE = 12
                    batches = [
                        frame_paths[i : i + BATCH_SIZE]
                        for i in range(0, len(frame_paths), BATCH_SIZE)
                    ] if len(frame_paths) > BATCH_SIZE else [frame_paths]

                    log.info("frame_batches", job_id=job_id,
                             total_frames=len(frame_paths), batches=len(batches))

                    for batch_idx, batch in enumerate(batches):
                        if _timed_out():
                            break
                        frame_extract = await _run_tool(
                            "llm_frame_extract", llm_frame_extract,
                            batch, model_override=model_override,
                        )
                        if frame_extract.success:
                            partial = frame_extract.signals.get("partial_recipe")
                            visible_text = frame_extract.signals.get("visible_text", [])
                            cooking_actions = frame_extract.signals.get("cooking_actions", [])
                            observed_ings = frame_extract.signals.get("observed_ingredients", [])
                            frame_confidence = frame_extract.signals.get("confidence", "low")
                            if partial and frame_confidence != "low":
                                partial_entry = {"source": f"video_frames_batch_{batch_idx}", **partial}
                                if cooking_actions:
                                    partial_entry["cooking_actions"] = cooking_actions
                                if observed_ings:
                                    partial_entry["observed_ingredients"] = observed_ings
                                partials.append(partial_entry)
                                log.info("frame_extract_partial", job_id=job_id,
                                         batch=batch_idx, actions=len(cooking_actions),
                                         ingredients=len(observed_ings),
                                         confidence=frame_confidence)
                            elif partial and frame_confidence == "low":
                                log.info("frame_extract_skipped_low_confidence",
                                         job_id=job_id, batch=batch_idx)
                            elif visible_text or cooking_actions:
                                entry: dict[str, Any] = {"source": f"video_frames_batch_{batch_idx}"}
                                if visible_text:
                                    entry["text"] = " ".join(visible_text)
                                if cooking_actions:
                                    entry["cooking_actions"] = cooking_actions
                                if observed_ings:
                                    entry["observed_ingredients"] = observed_ings
                                partials.append(entry)
                                log.info("frame_extract_text", job_id=job_id,
                                         batch=batch_idx, text_len=len(" ".join(visible_text)))
                        else:
                            log.warning("frame_extract_failed", job_id=job_id,
                                        batch=batch_idx, message=frame_extract.message)
            else:
                log.warning("frames_extraction_failed", job_id=job_id, message=frames_result.message)

        log.info("video_partials_collected", job_id=job_id, count=len(partials),
                 sources=[p.get("source") for p in partials])

        if not partials:
            return None

        # If we only have one source, try LLM extract directly
        if len(partials) == 1 and "text" in partials[0] and not _timed_out():
            from app.tools.extraction_tools import llm_structured_extract
            llm_result = await _run_tool(
                "llm_structured_extract", llm_structured_extract,
                partials[0]["text"], "video transcription",
                model_override=model_override, available_tags=available_tag_names,
            )
            if llm_result.success and llm_result.candidate_update:
                fb_urls = await _upload_fallback_thumbnail(fallback_thumb_path, job_id) if fallback_thumb_path else []
                return (
                    llm_result.candidate_update,
                    llm_result.signals.get("provenance", {}),
                    "video_transcription_llm",
                    "reconstruction",
                    fb_urls,
                )

        # Merge multiple partial candidates
        if len(partials) > 1 and not _timed_out():
            merge_result = await _run_tool(
                "merge_partial_candidates", merge_partial_candidates,
                partials, model_override=model_override, available_tags=available_tag_names,
            )
            if merge_result.success and merge_result.candidate_update:
                fb_urls = await _upload_fallback_thumbnail(fallback_thumb_path, job_id) if fallback_thumb_path else []
                return (
                    merge_result.candidate_update,
                    merge_result.signals.get("provenance", {}),
                    "video_reconstruction_merge",
                    "reconstruction",
                    fb_urls,
                )

        return None

    finally:
        cleanup_temp_files(*tmp_dirs)


async def _upload_fallback_thumbnail(frame_path: str, job_id: str) -> list[str]:
    """Upload a video frame to S3 as a fallback thumbnail when no external thumbnail is available."""
    try:
        settings = get_settings()
        if not settings.s3_bucket or not os.path.exists(frame_path):
            return []

        from app.core.s3 import build_asset_ref, get_s3_client

        s3 = get_s3_client()
        asset_key = build_asset_ref("recipe-media", "system", f"video_thumb_{job_id}.jpg")
        with open(frame_path, "rb") as f:
            s3.put_object(
                Bucket=settings.s3_bucket,
                Key=asset_key,
                Body=f.read(),
                ContentType="image/jpeg",
            )
        log.info("fallback_thumbnail_uploaded", job_id=job_id, key=asset_key)
        return [asset_key]
    except Exception as exc:
        log.warning("fallback_thumbnail_upload_failed", job_id=job_id, error=str(exc))
        return []


def _description_has_recipe_content(text: str) -> bool:
    """Check if text contains actual recipe data (ingredients with quantities) vs just marketing."""
    import re as _re
    lower = text.lower()
    # Look for quantity+unit patterns like "2 cups", "1/2 tsp", "300g", "1 tablespoon"
    qty_pattern = _re.compile(
        r'\b\d+[\s/]*(?:cup|cups|tbsp|tsp|tablespoon|teaspoon|oz|ounce|pound|lb|'
        r'gram|grams|kg|ml|liter|litre|clove|cloves|pinch|dash|bunch|handful|'
        r'can|cans|inch|slice|slices|piece|pieces|medium|large|small)\b',
        _re.IGNORECASE,
    )
    qty_matches = qty_pattern.findall(text)
    if len(qty_matches) >= 3:
        return True
    # Look for numbered/bulleted ingredient or step lists
    list_pattern = _re.compile(r'(?:^|\n)\s*(?:\d+[\.\)]\s|[-•]\s)', _re.MULTILINE)
    list_matches = list_pattern.findall(text)
    if len(list_matches) >= 3:
        return True
    # Look for section headers like "Ingredients", "Instructions", "Directions"
    if _re.search(r'(?i)\b(?:ingredients|instructions|directions|method|steps)\s*[:\n]', text):
        return True
    # Explicit ingredient listing with commas (e.g. "flour, sugar, butter, eggs")
    if _re.search(r'(?i)(?:you.ll need|you need|what you need|ingredients?)\s*[:;]', lower):
        return True
    return False


def _extract_keywords_from_caption(caption: str) -> list[str]:
    """Pull food-related keywords from a social caption for site search."""
    import re as _re
    words = _re.findall(r"[a-zA-Z]{3,}", caption.lower())
    stop_words = {
        "the", "and", "for", "this", "that", "with", "from", "have", "your",
        "you", "are", "was", "were", "been", "being", "has", "had", "its",
        "link", "bio", "recipe", "check", "out", "new", "try", "make",
        "like", "just", "get", "here", "more", "click",
    }
    keywords = [w for w in words if w not in stop_words]
    return keywords[:10]


def _extract_mentioned_sites(caption: str) -> list[str]:
    """Extract website domains mentioned in caption text, including spelled-out ones.

    Handles patterns like "visit PLANTYOU DOT COM", "mysite.com", etc.
    """
    import re as _re

    sites: list[str] = []

    # Pattern 1: Spelled-out domains ("PLANTYOU DOT COM", "mysite dot com")
    spelled = _re.findall(
        r"([a-zA-Z0-9][\w-]*)\s+(?:DOT|dot|\.)\s+(COM|com|NET|net|ORG|org|IO|io|CO|co)",
        caption,
    )
    for name, tld in spelled:
        domain = f"{name.lower()}.{tld.lower()}"
        sites.append(f"https://{domain}")

    # Pattern 2: Bare domains in text ("plantyou.com", "myrecipes.co")
    bare = _re.findall(
        r"(?<!\w)([a-zA-Z0-9][\w-]+\.(?:com|net|org|io|co))\b",
        caption,
        _re.IGNORECASE,
    )
    for domain in bare:
        url = f"https://{domain.lower()}"
        if url not in sites:
            sites.append(url)

    return sites


async def _finalize_job(
    session: AsyncSession,
    job_id: str,
    status: str,
    internal_state: str,
    extraction_plan: list,
    artifact_ids: list,
    candidate_id: str | None = None,
    review_mode: str | None = None,
    error_type: str | None = None,
    error_code: str | None = None,
) -> None:
    now = datetime.now(tz=UTC)
    rerun_allowed = status == "failed"

    await ingestion_job_repo.update_job_status(
        session,
        job_id,
        status=status,
        internal_state=internal_state,
        candidate_id=candidate_id,
        review_mode=review_mode,
        extraction_plan=extraction_plan,
        normalized_artifact_ids=artifact_ids,
        error_type=error_type,
        error_code=error_code,
        rerun_allowed=rerun_allowed,
        completed_at=now,
        last_heartbeat_at=now,
    )
    await session.commit()


def _is_async(fn) -> bool:
    import asyncio
    return asyncio.iscoroutinefunction(fn)
