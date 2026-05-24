"""T-036: Video processing tools — download, transcribe, frame extraction, and merging."""

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import social_breaker, whisper_breaker
from app.core.config import get_settings
from app.tools.base import ToolResult

log = structlog.get_logger()

MAX_VIDEO_DURATION = 600  # 10 minutes — skip excessively long videos


async def yt_dlp_download_video(url: str) -> ToolResult:
    """Download video to a temp file via yt-dlp. Returns file path and duration."""
    if social_breaker.is_open():
        return ToolResult(success=False, message="Social circuit breaker is open")

    try:
        import yt_dlp

        tmp_dir = tempfile.mkdtemp(prefix="kama_video_")
        output_template = os.path.join(tmp_dir, "video.%(ext)s")

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "outtmpl": output_template,
            "format": "worst[ext=mp4]/worst",
            "max_filesize": 100 * 1024 * 1024,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is None:
                social_breaker.record_failure()
                return ToolResult(success=False, message="yt-dlp download returned no info")

        duration = info.get("duration", 0)
        if duration and duration > MAX_VIDEO_DURATION:
            _cleanup_dir(tmp_dir)
            return ToolResult(
                success=False,
                message=f"Video too long ({duration}s > {MAX_VIDEO_DURATION}s limit)",
            )

        downloaded = _find_downloaded_file(tmp_dir)
        if not downloaded:
            return ToolResult(success=False, message="Download completed but file not found")

        social_breaker.record_success()

        return ToolResult(
            success=True,
            message=f"Downloaded video ({duration}s) to {downloaded}",
            signals={
                "video_path": str(downloaded),
                "duration": duration,
                "tmp_dir": tmp_dir,
            },
        )

    except Exception as exc:
        social_breaker.record_failure()
        log.error("video_download_error", url=url, error=str(exc))
        return ToolResult(success=False, message=f"Video download failed: {exc}")


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=15), reraise=True)
async def whisper_transcribe(audio_path: str) -> ToolResult:
    """Extract audio and transcribe via OpenAI Whisper API."""
    settings = get_settings()
    if not settings.openai_api_key:
        return ToolResult(success=False, message="OPENAI_API_KEY required for Whisper")

    if whisper_breaker.is_open():
        return ToolResult(success=False, message="Whisper circuit breaker is open")

    audio_file = _extract_audio(audio_path)
    if not audio_file:
        return ToolResult(success=False, message="Audio extraction failed")

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)

        with open(audio_file, "rb") as f:
            transcript_resp = await client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        segments: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        if hasattr(transcript_resp, "segments") and transcript_resp.segments:
            for seg in transcript_resp.segments:
                segments.append({
                    "start": seg.start if hasattr(seg, "start") else seg.get("start", 0),
                    "end": seg.end if hasattr(seg, "end") else seg.get("end", 0),
                    "text": seg.text if hasattr(seg, "text") else seg.get("text", ""),
                })
                full_text_parts.append(
                    seg.text if hasattr(seg, "text") else seg.get("text", "")
                )

        full_text = transcript_resp.text if hasattr(transcript_resp, "text") else " ".join(full_text_parts)

        whisper_breaker.record_success()

        return ToolResult(
            success=True,
            message=f"Transcribed audio ({len(segments)} segments, {len(full_text)} chars)",
            artifacts=[{
                "artifactType": "whisper_transcript",
                "payload": {
                    "segmentCount": len(segments),
                    "textLength": len(full_text),
                },
            }],
            signals={
                "transcript_text": full_text,
                "transcript_segments": segments,
            },
        )

    except Exception as exc:
        whisper_breaker.record_failure()
        log.error("whisper_transcribe_error", audio_path=audio_path, error=str(exc))
        return ToolResult(success=False, message=f"Whisper transcription failed: {exc}")
    finally:
        if audio_file and os.path.exists(audio_file):
            try:
                os.unlink(audio_file)
            except OSError:
                pass


async def extract_key_frames(video_path: str, interval: float = 3.0) -> ToolResult:
    """Sample frames from a video at the given interval (seconds) using ffmpeg."""
    if not os.path.exists(video_path):
        return ToolResult(success=False, message=f"Video file not found: {video_path}")

    try:
        import ffmpeg

        tmp_dir = tempfile.mkdtemp(prefix="kama_frames_")
        output_pattern = os.path.join(tmp_dir, "frame_%04d.jpg")

        (
            ffmpeg.input(video_path)
            .filter("fps", fps=1 / interval)
            .output(output_pattern, **{"qscale:v": 2})
            .overwrite_output()
            .run(quiet=True)
        )

        frame_paths = sorted(Path(tmp_dir).glob("frame_*.jpg"))
        if not frame_paths:
            return ToolResult(success=False, message="No frames extracted")

        path_strs = [str(p) for p in frame_paths]

        return ToolResult(
            success=True,
            message=f"Extracted {len(path_strs)} key frames",
            signals={
                "frame_paths": path_strs,
                "frame_count": len(path_strs),
                "frames_dir": tmp_dir,
            },
        )

    except Exception as exc:
        log.error("frame_extraction_error", video_path=video_path, error=str(exc))
        return ToolResult(success=False, message=f"Frame extraction failed: {exc}")


def _evenly_sample(items: list, n: int) -> list:
    """Return *n* items evenly distributed across *items*."""
    if len(items) <= n:
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


async def llm_frame_extract(frame_paths: list[str], *, model_override: str | None = None) -> ToolResult:
    """Analyse sampled video frames with a multimodal LLM.

    Frames are evenly sampled across the full video (up to MAX_FRAMES_PER_BATCH
    per call) so the entire duration is represented.  The prompt asks the LLM to
    both read visible text *and* describe the cooking actions / ingredients it
    sees — critical for videos that use no text overlays.
    """
    from app.core.llm import LLMConfigError, llm_chat

    if not frame_paths:
        return ToolResult(success=False, message="No frames provided")

    import base64

    MAX_FRAMES_PER_BATCH = 12

    sampled = _evenly_sample(frame_paths, MAX_FRAMES_PER_BATCH)

    content_parts: list[dict[str, Any]] = [{
        "type": "text",
        "text": (
            "These are frames sampled evenly across a cooking video. "
            "Your job is to extract recipe information that is ACTUALLY VISIBLE "
            "in these frames.\n\n"
            "For each frame, note:\n"
            "1. Any visible text (recipe cards, titles, ingredient lists, captions).\n"
            "2. What food/ingredients are CLEARLY visible and identifiable.\n"
            "3. What cooking action is being performed (chopping, roasting, blending, "
            "plating, etc.).\n\n"
            "CRITICAL RULES:\n"
            "- ONLY report ingredients you can ACTUALLY SEE in the frames. Do NOT guess "
            "or infer ingredients that are not visible.\n"
            "- ONLY report cooking actions you can ACTUALLY SEE happening. Do NOT invent "
            "steps based on what you think the recipe might involve.\n"
            "- If a frame just shows a finished dish or plated food, describe what you "
            "see but do NOT reverse-engineer a full recipe from the final presentation.\n"
            "- It is MUCH better to return incomplete data than to hallucinate details.\n\n"
            "The video may show MULTIPLE recipe components (e.g. a dip AND "
            "a roasted vegetable side). Capture all components you can ACTUALLY SEE "
            "being prepared — but do NOT invent components.\n\n"
            "Return a JSON object with:\n"
            '- "visible_text": array of strings (each text block found)\n'
            '- "recipe_card_detected": boolean\n'
            '- "cooking_actions": array of strings describing each distinct cooking '
            "step ACTUALLY OBSERVED in the frames, in chronological order\n"
            '- "observed_ingredients": array of strings — ONLY ingredients you can '
            "clearly identify in the frames (do NOT guess)\n"
            '- "confidence": "high" if you see clear recipe content (text overlays, '
            'recipe cards, multiple cooking steps), "low" if you are mostly guessing\n'
            '- "partial_recipe": object with:\n'
            "    - title (string)\n"
            "    - ingredients (array of {text, quantity, unit, section}) — ONLY "
            "ingredients you are confident about\n"
            "    - steps (array of {order, text}) — ONLY steps you actually observed\n"
            "    - sections (array of section names if multiple components)\n\n"
            "If no recipe content is visible at all, or you would be mostly guessing, "
            "return "
            '{"visible_text": [], "recipe_card_detected": false, '
            '"cooking_actions": [], "observed_ingredients": [], '
            '"confidence": "low", "partial_recipe": null}'
        ),
    }]

    for fpath in sampled:
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "rb") as f:
                img_data = base64.b64encode(f.read()).decode("utf-8")
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_data}"},
            })
        except Exception as exc:
            log.debug("frame_read_error", path=fpath, error=str(exc))

    if len(content_parts) < 2:
        return ToolResult(success=False, message="Could not read any frame images")

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": content_parts}],
            max_tokens=8192,
            json_mode=True,
            model_override=model_override or "gpt-4o",
        )
    except (LLMConfigError, RuntimeError) as exc:
        return ToolResult(success=False, message=str(exc))
    except Exception as exc:
        log.error("llm_frame_extract_error", error=str(exc))
        return ToolResult(success=False, message=f"LLM frame extraction failed: {exc}")

    try:
        json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not json_match:
            return ToolResult(success=False, message="LLM returned no JSON for frames")

        parsed = json.loads(json_match.group())
        visible_text = parsed.get("visible_text", [])
        recipe_card = parsed.get("recipe_card_detected", False)
        partial_recipe = parsed.get("partial_recipe")
        cooking_actions = parsed.get("cooking_actions", [])
        observed_ingredients = parsed.get("observed_ingredients", [])
        confidence = parsed.get("confidence", "low")

        return ToolResult(
            success=True,
            message=f"Extracted from {len(sampled)} frames ({len(visible_text)} text blocks, "
                    f"{len(cooking_actions)} actions, {len(observed_ingredients)} ingredients, "
                    f"confidence={confidence})",
            signals={
                "visible_text": visible_text,
                "recipe_card_detected": recipe_card,
                "confidence": confidence,
                "partial_recipe": partial_recipe,
                "cooking_actions": cooking_actions,
                "observed_ingredients": observed_ingredients,
                "frames_analyzed": len(sampled),
            },
        )

    except json.JSONDecodeError:
        return ToolResult(success=False, message="LLM returned invalid JSON for frame analysis")


async def merge_partial_candidates(partials: list[dict], *, model_override: str | None = None, available_tags: list[str] | None = None) -> ToolResult:
    """LLM-assisted merge of partial recipe data from multiple sources."""
    from app.core.llm import LLMConfigError, llm_chat

    if not partials:
        return ToolResult(success=False, message="No partial candidates to merge")

    prompt = (
        "You are merging partial recipe extractions from multiple sources (video caption, "
        "transcript, video frames, etc.) into a single coherent recipe.\n\n"
        "CRITICAL: The video may contain MULTIPLE sub-recipes or components (e.g. a main "
        "dish plus a side, a dip plus roasted vegetables, a sauce plus a protein). You MUST "
        "include ALL components — do NOT drop any. Use 'section' on ingredients and separate "
        "step groups to keep components organized.\n\n"
        "Some sources may include 'cooking_actions' and 'observed_ingredients' from visual "
        "analysis. Use these to fill gaps where text/transcript is incomplete — they represent "
        "real cooking steps that were observed in the video.\n\n"
        "Partial sources:\n"
    )
    for i, partial in enumerate(partials):
        prompt += f"\n--- Source {i + 1} ---\n{json.dumps(partial, indent=2, default=str)}\n"

    prompt += (
        "\nMerge these into a single JSON recipe object with:\n"
        "- title (string) — use a title that covers ALL components shown\n"
        "- description (string, 1-2 sentences)\n"
        "- ingredients (array of {text, quantity, unit, section})\n"
        "  • 'text' = ingredient name only (e.g. \"coriander seeds\")\n"
        "  • 'quantity' = numeric amount as string, or null\n"
        "  • 'unit' = standard cooking unit (tbsp, tsp, cup, g, kg, ml, etc.) or null for counts\n"
        "  • 'section' = group name if recipe has sub-components (e.g. \"Hummus\", "
        "\"Roasted Vegetables\"), or null for single-component recipes\n"
        "  • Split compound items (e.g. \"salt and pepper\" → two entries)\n"
        "  • Include ALL ingredients from ALL observed components/sub-recipes\n"
        "- steps (array of {order, text}) — preserve FULL detail from sources. Each distinct "
        "action is its own step with specific temperatures, times, and visual cues. "
        "Do NOT summarize multiple steps into one. Include steps for EVERY component.\n"
        "- prepTimeMinutes (integer, required) — extract if stated; otherwise estimate "
        "from the steps (e.g. marinating, soaking, chopping times).\n"
        "- cookTimeMinutes (integer, required) — extract if stated; otherwise estimate "
        "by summing cooking durations mentioned in steps.\n"
        "- servings (integer, required) — extract if stated; otherwise estimate from "
        "ingredient quantities (e.g. 500g meat ≈ 4 servings).\n"
        "- recipeTags (array of strings) — classify this recipe with relevant tags. "
    )
    if available_tags:
        tag_list = ", ".join(available_tags)
        prompt += (
            f"Choose from these existing tags when possible: [{tag_list}]. "
            "You may also suggest new tags if none of the existing ones fit.\n"
        )
    else:
        prompt += (
            "Suggest 2-5 descriptive tags such as cuisine type (e.g. \"Indian\", \"Italian\"), "
            "meal type (\"Breakfast\", \"Dinner\"), diet (\"Vegetarian\", \"Gluten-Free\"), "
            "cooking method (\"Slow Cooker\", \"Grilled\"), or dish type (\"Soup\", \"Dessert\").\n"
        )
    prompt += (
        "- nutrition (object or null) — only include if explicitly provided in sources. "
        "Keys: calories, servingSize, carbohydrates, protein, fat, saturatedFat, "
        "unsaturatedFat, transFat, cholesterol, sodium, fiber, sugar. Do NOT guess.\n"
        "- notes (array of {type, text}) — merge all tips/substitutions/storage/variation/general "
        "notes from sources. Deduplicate. Empty array if none.\n"
        "- howToServe (string or null) — serving suggestions. null if not mentioned.\n\n"
        "Use the most complete and reliable data from each source. "
        "Prefer structured data over transcribed speech.\n\n"
        "CRITICAL: Do NOT add ingredients or steps that are not supported by at least one "
        "source. If 'observed_ingredients' or 'cooking_actions' from frame analysis mention "
        "items that are NOT corroborated by the transcript or visible text, IGNORE them — "
        "visual analysis from still frames is unreliable and may hallucinate ingredients "
        "that are not actually in the video. Only include frame observations that are "
        "confirmed by other sources (transcript, captions, visible text overlays).\n\n"
        "If the transcript is very short or the video caption is vague (e.g. just an emoji), "
        "keep the recipe simple and only include what you are confident about. "
        "It is better to produce a shorter, accurate recipe than a longer, fabricated one."
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            json_mode=True,
            model_override=model_override,
        )
    except (LLMConfigError, RuntimeError) as exc:
        return ToolResult(success=False, message=str(exc))
    except Exception as exc:
        log.error("merge_partials_error", error=str(exc))
        return ToolResult(success=False, message=f"Merge failed: {exc}")

    try:
        json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not json_match:
            return ToolResult(success=False, message="LLM merge returned no JSON")

        merged = json.loads(json_match.group())

        ingredients = []
        for ing in merged.get("ingredients", []):
            if isinstance(ing, str):
                ingredients.append({"text": ing, "ingredientId": None, "quantity": None, "unit": None})
            elif isinstance(ing, dict):
                ingredients.append({
                    "text": ing.get("text", ""),
                    "ingredientId": None,
                    "quantity": ing.get("quantity"),
                    "unit": ing.get("unit"),
                })

        steps = []
        for i, step in enumerate(merged.get("steps", [])):
            if isinstance(step, str):
                steps.append({"order": i + 1, "text": step, "mediaRefs": []})
            elif isinstance(step, dict):
                steps.append({
                    "order": step.get("order", i + 1),
                    "text": step.get("text", ""),
                    "mediaRefs": [],
                })

        from app.tools.extraction_tools import _normalize_notes

        raw_nutrition = merged.get("nutrition")
        nutrition = raw_nutrition if isinstance(raw_nutrition, dict) and raw_nutrition else None
        notes = _normalize_notes(merged.get("notes", []))
        raw_serve = merged.get("howToServe")
        how_to_serve = str(raw_serve).strip() if raw_serve else None

        raw_tags = merged.get("recipeTags", [])
        recipe_tags = [t.strip() for t in raw_tags if isinstance(t, str) and t.strip()] if isinstance(raw_tags, list) else []

        candidate_update = {
            "title": merged.get("title", ""),
            "ingredients": ingredients,
            "steps": steps,
            "description": merged.get("description"),
            "prepTimeMinutes": merged.get("prepTimeMinutes"),
            "cookTimeMinutes": merged.get("cookTimeMinutes"),
            "servings": merged.get("servings"),
            "nutrition": nutrition,
            "notes": notes,
            "howToServe": how_to_serve,
            "recipeTags": recipe_tags,
        }

        provenance = {
            field: {"sourceType": "video_reconstruction_merge"}
            for field in candidate_update
            if candidate_update[field] is not None
        }

        return ToolResult(
            success=True,
            message=f"Merged {len(partials)} partial candidates into '{candidate_update['title']}'",
            candidate_update=candidate_update,
            signals={
                "provenance": provenance,
                "merge_source_count": len(partials),
                "extractionMethod": "video_reconstruction_merge",
            },
        )

    except json.JSONDecodeError:
        return ToolResult(success=False, message="LLM merge returned invalid JSON")


def cleanup_temp_files(*paths: str) -> None:
    """Remove temporary files and directories created during video processing."""
    import shutil

    for path in paths:
        if not path:
            continue
        try:
            p = Path(path)
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink(missing_ok=True)
        except Exception as exc:
            log.debug("cleanup_failed", path=path, error=str(exc))


def _extract_audio(video_path: str) -> str | None:
    """Extract audio track from video as WAV for Whisper."""
    try:
        import ffmpeg

        audio_path = video_path.rsplit(".", 1)[0] + ".wav"
        (
            ffmpeg.input(video_path)
            .output(audio_path, acodec="pcm_s16le", ac=1, ar="16000")
            .overwrite_output()
            .run(quiet=True)
        )
        return audio_path if os.path.exists(audio_path) else None
    except Exception as exc:
        log.error("audio_extraction_error", video_path=video_path, error=str(exc))
        return None


def _find_downloaded_file(directory: str) -> str | None:
    """Find the downloaded video file in a temp directory."""
    for ext in (".mp4", ".webm", ".mkv", ".avi", ".mov"):
        for f in Path(directory).glob(f"*{ext}"):
            return str(f)
    all_files = list(Path(directory).iterdir())
    if all_files:
        return str(all_files[0])
    return None


def _cleanup_dir(directory: str) -> None:
    """Remove a temp directory quietly."""
    import shutil
    try:
        shutil.rmtree(directory, ignore_errors=True)
    except Exception:
        pass
