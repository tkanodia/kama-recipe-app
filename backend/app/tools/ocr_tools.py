"""T-033: OCR tools — Google Cloud Vision text extraction with retry, circuit breaker,
quality validation, and multimodal LLM fallback for image-based recipe ingestion."""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import ocr_breaker
from app.core.llm import LLMConfigError, llm_chat
from app.tools.base import ToolResult

try:
    from google.cloud import vision
except ImportError:
    vision = None  # type: ignore[assignment]

log = structlog.get_logger()


def _resolve_image_bytes(image_path_or_url: str) -> bytes | None:
    """Download image bytes from S3 key, HTTP URL, or local file path."""
    if image_path_or_url.startswith(("http://", "https://")):
        return None  # caller handles URL downloads
    path = Path(image_path_or_url)
    if path.exists():
        return path.read_bytes()
    # Treat as S3 key
    from app.core.config import get_settings
    from app.core.s3 import get_s3_client
    settings = get_settings()
    if settings.s3_bucket:
        try:
            s3 = get_s3_client()
            resp = s3.get_object(Bucket=settings.s3_bucket, Key=image_path_or_url)
            return resp["Body"].read()
        except Exception as exc:
            log.warning("s3_image_download_failed", key=image_path_or_url, error=str(exc))
    return None


MIN_USEFUL_TEXT_LENGTH = 20
LOW_CONFIDENCE_THRESHOLD = 0.60
FALLBACK_CONFIDENCE_THRESHOLD = 0.40


def _sync_vision_calls(image_content: bytes) -> dict[str, Any]:
    """Run synchronous Google Cloud Vision API calls (meant to be called via to_thread)."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds_path and not os.path.isabs(creds_path):
        creds_path = str(Path.cwd() / creds_path)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = creds_path

    client = vision.ImageAnnotatorClient()
    image = vision.Image()
    image.content = image_content

    text_response = client.text_detection(image=image)
    doc_response = client.document_text_detection(image=image)

    if text_response.error.message:
        return {"error": text_response.error.message}

    full_text = ""
    line_blocks: list[dict[str, Any]] = []
    overall_confidence = 0.0
    handwriting_detected = False

    text_annotations = text_response.text_annotations
    if text_annotations:
        full_text = text_annotations[0].description.strip()
        for annotation in text_annotations[1:]:
            vertices = annotation.bounding_poly.vertices
            block = {
                "text": annotation.description,
                "boundingBox": [{"x": v.x, "y": v.y} for v in vertices],
            }
            line_blocks.append(block)

    if doc_response.full_text_annotation:
        pages = doc_response.full_text_annotation.pages
        if pages:
            page = pages[0]
            overall_confidence = page.confidence if hasattr(page, "confidence") else 0.0

            for block in page.blocks:
                if hasattr(block, "block_type"):
                    block_type = vision.Block.BlockType(block.block_type)
                    if block_type.name == "TEXT":
                        pass
        if not full_text and doc_response.full_text_annotation.text:
            full_text = doc_response.full_text_annotation.text.strip()

    label_response = client.label_detection(image=image, max_results=10)
    for label in label_response.label_annotations:
        if label.description.lower() in ("handwriting", "calligraphy", "handwritten"):
            handwriting_detected = True
            break

    return {
        "full_text": full_text,
        "line_blocks": line_blocks,
        "overall_confidence": overall_confidence,
        "handwriting_detected": handwriting_detected,
    }


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def ocr_extract(image_path_or_url: str) -> ToolResult:
    """Extract text from an image using Google Cloud Vision API.

    Supports local file paths and HTTP(S) URLs. Wraps calls with a circuit breaker
    and tenacity retry. Vision API calls run in a thread pool to avoid blocking
    the event loop.
    """
    if ocr_breaker.is_open():
        return ToolResult(
            success=False,
            message="OCR circuit breaker is open — refusing call",
            signals={"circuitBreakerOpen": True},
        )

    try:
        if vision is None:
            return ToolResult(success=False, message="google-cloud-vision is not installed")

        if image_path_or_url.startswith(("http://", "https://")):
            image_content = await _download_image(image_path_or_url)
        else:
            resolved = _resolve_image_bytes(image_path_or_url)
            if resolved is None:
                return ToolResult(success=False, message=f"Image not found: {image_path_or_url}")
            image_content = resolved

        result = await asyncio.to_thread(_sync_vision_calls, image_content)

        if "error" in result:
            ocr_breaker.record_failure()
            return ToolResult(
                success=False,
                message=f"Vision API error: {result['error']}",
            )

        full_text = result["full_text"]
        line_blocks = result["line_blocks"]
        overall_confidence = result["overall_confidence"]
        handwriting_detected = result["handwriting_detected"]

        ocr_breaker.record_success()

        quality_assessment = _assess_ocr_quality(full_text, overall_confidence)

        artifacts = [
            {
                "artifactType": "ocr_text",
                "payload": {
                    "text": full_text,
                    "extractionMethod": "google_cloud_vision",
                    "textLength": len(full_text),
                },
            },
            {
                "artifactType": "image_analysis",
                "payload": {
                    "overallConfidence": overall_confidence,
                    "handwritingDetected": handwriting_detected,
                    "lineBlockCount": len(line_blocks),
                    "qualityAssessment": quality_assessment,
                },
            },
        ]

        return ToolResult(
            success=True,
            message=f"OCR extracted {len(full_text)} chars (confidence: {overall_confidence:.2f})",
            artifacts=artifacts,
            signals={
                "extractedText": full_text,
                "lineBlocks": line_blocks,
                "overallConfidence": overall_confidence,
                "handwritingDetected": handwriting_detected,
                "qualityAssessment": quality_assessment,
                "textLength": len(full_text),
            },
        )

    except Exception as exc:
        ocr_breaker.record_failure()
        log.error("ocr_extract_failed", error=str(exc), image=image_path_or_url)
        raise


def create_image_preview(
    image_path_or_url: str,
    file_name: str | None = None,
    file_size_bytes: int | None = None,
) -> ToolResult:
    """Generate a source_preview artifact for an uploaded image."""
    preview_url = image_path_or_url if image_path_or_url.startswith("http") else None
    display_name = file_name or Path(image_path_or_url).name

    return ToolResult(
        success=True,
        message="Created image source preview",
        artifacts=[{
            "artifactType": "source_preview",
            "payload": {
                "previewType": "uploaded_image",
                "fileName": display_name,
                "imageUrl": preview_url,
                "fileSizeBytes": file_size_bytes,
            },
        }],
        signals={"previewGenerated": True},
    )


async def multimodal_llm_extract(
    image_path_or_url: str,
    ocr_text: str | None = None,
    *,
    model_override: str | None = None,
    available_tags: list[str] | None = None,
) -> ToolResult:
    """Fallback: send the image directly to a multimodal LLM (GPT-4o) for recipe extraction.

    Used when OCR confidence is too low to rely on text extraction alone.
    """
    try:
        if image_path_or_url.startswith(("http://", "https://")):
            image_bytes = await _download_image(image_path_or_url)
        else:
            image_bytes = _resolve_image_bytes(image_path_or_url)
            if image_bytes is None:
                return ToolResult(success=False, message=f"Image not found: {image_path_or_url}")

        b64_image = base64.b64encode(image_bytes).decode("utf-8")

        content_parts: list[dict[str, Any]] = []

        prompt_text = (
            "Analyze this image and return a JSON object.\n\n"
            "First, determine if the image shows food or a recipe. Set:\n"
            "- isFoodPhoto (boolean) — true if the image shows a prepared dish, food plating, or cooking in progress\n\n"
            "If a recipe is visible (handwritten, printed, or overlaid text), extract:\n"
            "- title (string)\n"
            "- description (string, 1-2 sentences)\n"
            "- ingredients (array of objects with: text, quantity, unit)\n"
            "- steps (array of objects with: order, text)\n"
            "- prepTimeMinutes (integer, required) — extract if visible; otherwise estimate from steps\n"
            "- cookTimeMinutes (integer, required) — extract if visible; otherwise estimate from steps\n"
            "- servings (integer, required) — extract if visible; otherwise estimate from ingredient quantities\n"
            "- recipeTags (array of strings) — classify with relevant tags. "
        )
        if available_tags:
            tag_list = ", ".join(available_tags)
            prompt_text += (
                f"Choose from: [{tag_list}]. You may also suggest new tags if needed.\n"
            )
        else:
            prompt_text += (
                "Suggest 2-5 tags: cuisine, meal type, diet, cooking method, or dish type.\n"
            )
        prompt_text += (
            "- nutrition (object or null) — only if visible in the image. "
            "Keys: calories, servingSize, carbohydrates, protein, fat, saturatedFat, "
            "unsaturatedFat, transFat, cholesterol, sodium, fiber, sugar. "
            "Values as strings with units. Omit keys not visible. Do NOT guess.\n"
            "- notes (array of objects with: type, text) — any tips, substitutions, "
            "storage advice, or variations visible. type is one of: tip, substitution, "
            "storage, variation, general. Empty array if none.\n"
            "- howToServe (string or null) — serving suggestions if visible. null if not.\n\n"
        )
        if ocr_text:
            prompt_text += (
                f"Partial OCR text was extracted but may be unreliable:\n{ocr_text[:2000]}\n\n"
                "Use the image as the primary source and the OCR text to fill gaps.\n"
            )
        prompt_text += 'If no recipe is visible, return {"isFoodPhoto": true/false, "error": "no_recipe_found"}.'

        content_parts.append({"type": "text", "text": prompt_text})
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
        })

        effective_model = model_override or "gpt-4o"

        response = await llm_chat(
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=4096,
            json_mode=True,
            model_override=effective_model,
        )

        content = response.text
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return ToolResult(success=False, message="Multimodal LLM returned no JSON")

        parsed = json.loads(json_match.group())
        is_food_photo = parsed.pop("isFoodPhoto", False)
        if "error" in parsed:
            return ToolResult(
                success=False,
                message=parsed["error"],
                signals={"llmSaysNoRecipe": True, "isFoodPhoto": is_food_photo},
            )

        from app.tools.extraction_tools import _normalize_notes

        # Normalize ingredients to ensure quantity/unit are always present
        raw_ingredients = parsed.get("ingredients", [])
        ingredients = []
        for ing in raw_ingredients:
            if isinstance(ing, str):
                ingredients.append({"text": ing, "ingredientId": None, "quantity": None, "unit": None})
            elif isinstance(ing, dict):
                ingredients.append({
                    "text": ing.get("text", ""),
                    "ingredientId": None,
                    "quantity": ing.get("quantity"),
                    "unit": ing.get("unit"),
                })

        # Normalize steps
        raw_steps = parsed.get("steps", [])
        steps = []
        for i, step in enumerate(raw_steps):
            if isinstance(step, str):
                steps.append({"order": i + 1, "text": step, "mediaRefs": []})
            elif isinstance(step, dict):
                steps.append({
                    "order": step.get("order", i + 1),
                    "text": step.get("text", ""),
                    "mediaRefs": [],
                })

        raw_nutrition = parsed.pop("nutrition", None)
        nutrition = raw_nutrition if isinstance(raw_nutrition, dict) and raw_nutrition else None
        raw_notes = parsed.pop("notes", [])
        notes = _normalize_notes(raw_notes)
        raw_serve = parsed.pop("howToServe", None)
        how_to_serve = str(raw_serve).strip() if raw_serve else None

        raw_tags = parsed.get("recipeTags", [])
        recipe_tags = [t.strip() for t in raw_tags if isinstance(t, str) and t.strip()] if isinstance(raw_tags, list) else []

        candidate_update = {
            "title": parsed.get("title", ""),
            "ingredients": ingredients,
            "steps": steps,
            "description": parsed.get("description"),
            "prepTimeMinutes": parsed.get("prepTimeMinutes"),
            "cookTimeMinutes": parsed.get("cookTimeMinutes"),
            "servings": parsed.get("servings"),
            "nutrition": nutrition,
            "notes": notes,
            "howToServe": how_to_serve,
            "recipeTags": recipe_tags,
        }

        return ToolResult(
            success=True,
            message=f"Multimodal LLM extracted recipe: {candidate_update.get('title', 'untitled')}",
            candidate_update=candidate_update,
            signals={
                "extractionMethod": "multimodal_llm_fallback",
                "confidence": "medium",
                "isFoodPhoto": is_food_photo,
                "provenance": {
                    field: {"sourceType": "multimodal_llm_vision"}
                    for field in candidate_update
                    if candidate_update.get(field) is not None
                },
            },
        )

    except LLMConfigError as exc:
        return ToolResult(success=False, message=str(exc))
    except json.JSONDecodeError:
        return ToolResult(success=False, message="Multimodal LLM returned invalid JSON")
    except Exception as exc:
        log.error("multimodal_llm_failed", error=str(exc))
        return ToolResult(success=False, message=f"Multimodal LLM extraction failed: {exc}")


def _assess_ocr_quality(text: str, confidence: float) -> str:
    """Rate OCR output quality for downstream decisions."""
    if not text or len(text.strip()) < MIN_USEFUL_TEXT_LENGTH:
        return "unusable"
    if confidence < FALLBACK_CONFIDENCE_THRESHOLD:
        return "very_low"
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return "low"
    return "acceptable"


async def _download_image(url: str) -> bytes:
    """Download image bytes from a URL."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def enrich_extracted_recipe(
    candidate_update: dict[str, Any],
    *,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Post-extraction enrichment: expand terse steps, improve description, add
    serving suggestions — without changing any factual details like quantities,
    ingredients, times, or servings."""

    recipe_json = json.dumps(candidate_update, indent=2, default=str)

    prompt = (
        "You are a professional recipe editor. Below is a recipe that was extracted "
        "from an image (cookbook page, screenshot, or handwritten note). The extraction "
        "may be terse, abbreviated, or missing context that a reader would need.\n\n"
        "Your job is to ENRICH the recipe while strictly preserving all factual details:\n\n"
        "RULES:\n"
        "- DO NOT change any ingredient names, quantities, units, or the ingredient list order.\n"
        "- DO NOT change prep time, cook time, or servings.\n"
        "- DO NOT invent new steps or remove existing steps.\n"
        "- DO NOT change the recipe title unless it's clearly incomplete.\n"
        "- DO NOT modify nutrition data or notes.\n\n"
        "WHAT TO IMPROVE:\n"
        "- Expand terse/shorthand steps into clear, complete sentences. "
        "E.g. 'add flour, mix' → 'Add the flour to the wet ingredients and mix until just combined.'\n"
        "- Add helpful details implicit from context: equipment needed, visual cues "
        "(e.g. 'until golden brown'), technique tips (e.g. 'fold gently to keep air').\n"
        "- If the description is missing or bare, write a 1-2 sentence appetizing description.\n"
        "- If howToServe is null and there's an obvious serving suggestion from context, add one.\n"
        "- Fix grammar, spelling, and capitalization in steps.\n\n"
        "Return the COMPLETE recipe as a JSON object with the same structure.\n\n"
        f"Recipe:\n{recipe_json}"
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
            json_mode=True,
            model_override=model_override or "gpt-4o",
        )

        json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not json_match:
            log.warning("enrich_no_json_returned")
            return candidate_update

        enriched = json.loads(json_match.group())

        # Safety: preserve fields the LLM must not change
        for key in ("ingredients", "prepTimeMinutes", "cookTimeMinutes", "servings", "nutrition"):
            if key in candidate_update:
                enriched[key] = candidate_update[key]

        # Preserve notes if LLM dropped them
        if "notes" in candidate_update and not enriched.get("notes"):
            enriched["notes"] = candidate_update["notes"]

        log.info("recipe_enriched", title=enriched.get("title", ""))
        return enriched

    except Exception as exc:
        log.warning("enrich_failed_using_original", error=str(exc))
        return candidate_update


async def extract_dish_photo_from_image(
    image_bytes: bytes,
    *,
    model_override: str | None = None,
) -> tuple[bytes, str] | None:
    """Detect and crop a dish photo from a recipe image (cookbook page, screenshot).

    Uses GPT-4o to identify the bounding box of the food photo as percentages,
    then crops precisely with Pillow.
    Returns (cropped_jpeg_bytes, region_description) or None if no dish photo found.
    """
    try:
        from PIL import Image as PILImage
        import io
    except ImportError:
        log.warning("pillow_not_installed_skipping_crop")
        return None

    b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = (
        "This image is a recipe page (from a cookbook, screenshot, or handwritten note). "
        "Does it contain a PHOTO of the finished dish or food?\n\n"
        "If YES, I need you to identify the TIGHT bounding box of JUST the food photo, "
        "excluding any surrounding text, titles, logos, or whitespace.\n\n"
        "Respond with a JSON object:\n"
        "{\n"
        '  "hasPhoto": true,\n'
        '  "bbox": {\n'
        '    "left": <percentage from left edge, 0-100>,\n'
        '    "top": <percentage from top edge, 0-100>,\n'
        '    "right": <percentage from left edge where photo ends, 0-100>,\n'
        '    "bottom": <percentage from top edge where photo ends, 0-100>\n'
        "  },\n"
        '  "description": "<brief description of the food>"\n'
        "}\n\n"
        "Example: if the food photo occupies the right side from 50% to 95% horizontally "
        "and 10% to 50% vertically, respond with:\n"
        '{"hasPhoto": true, "bbox": {"left": 50, "top": 10, "right": 95, "bottom": 50}, '
        '"description": "avocado toast with eggs"}\n\n'
        "Be PRECISE — crop tightly around the food photo only. Do not include text areas.\n\n"
        "If NO photo of food is visible (only text, diagrams, or illustrations), respond:\n"
        '{"hasPhoto": false}\n\n'
        "Only identify actual photographs of food, not hand-drawn illustrations or icons."
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}],
            max_tokens=300,
            json_mode=True,
            model_override=model_override or "gpt-4o",
        )

        json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not json_match:
            return None

        parsed = json.loads(json_match.group())
        if not parsed.get("hasPhoto"):
            return None

        bbox = parsed.get("bbox")
        if not bbox or not all(k in bbox for k in ("left", "top", "right", "bottom")):
            log.warning("dish_photo_no_bbox", parsed=parsed)
            return None

        left_pct = max(0, min(100, float(bbox["left"])))
        top_pct = max(0, min(100, float(bbox["top"])))
        right_pct = max(0, min(100, float(bbox["right"])))
        bottom_pct = max(0, min(100, float(bbox["bottom"])))

        if right_pct <= left_pct or bottom_pct <= top_pct:
            log.warning("dish_photo_invalid_bbox", bbox=bbox)
            return None

        # Small inward padding (2%) to ensure text at edges is excluded
        pad = 2.0
        left_pct = min(left_pct + pad, right_pct)
        top_pct = min(top_pct + pad, bottom_pct)
        right_pct = max(right_pct - pad, left_pct)
        bottom_pct = max(bottom_pct - pad, top_pct)

        img = PILImage.open(io.BytesIO(image_bytes))
        w, h = img.size
        crop_box = (
            int(left_pct / 100 * w),
            int(top_pct / 100 * h),
            int(right_pct / 100 * w),
            int(bottom_pct / 100 * h),
        )
        cropped = img.crop(crop_box)

        cw, ch = cropped.size
        if cw < 100 or ch < 100:
            log.info("cropped_region_too_small", width=cw, height=ch)
            return None

        buf = io.BytesIO()
        cropped.convert("RGB").save(buf, format="JPEG", quality=85)
        cropped_bytes = buf.getvalue()

        region_desc = f"{left_pct:.0f}%-{right_pct:.0f}% x {top_pct:.0f}%-{bottom_pct:.0f}%"
        log.info(
            "dish_photo_cropped",
            region=region_desc,
            bbox=bbox,
            original_size=f"{w}x{h}",
            crop_size=f"{cw}x{ch}",
            description=parsed.get("description", ""),
        )
        return cropped_bytes, region_desc

    except Exception as exc:
        log.warning("dish_photo_extraction_failed", error=str(exc))
        return None
