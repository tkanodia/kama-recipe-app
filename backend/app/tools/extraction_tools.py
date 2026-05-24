"""T-020: check_schema_markup — find JSON-LD recipe schema in HTML.
   T-021: schema_recipe_extract — parse recipe from schema.org markup.
   T-024: llm_structured_extract — LLM-based recipe extraction from text."""

import html as html_mod
import json
import re
from typing import Any

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.tools.base import ToolResult

log = structlog.get_logger()

_HTML_TAG_RE_SIMPLE = re.compile(r"<[^>]+>")


def _clean_schema_text(val: str) -> str:
    """Decode HTML entities and strip stray tags from schema.org text fields."""
    text = _HTML_TAG_RE_SIMPLE.sub(" ", val)
    text = html_mod.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


JSONLD_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']?application/ld\+json["\']?[^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def check_schema_markup(html: str) -> ToolResult:
    blocks = JSONLD_SCRIPT_RE.findall(html)
    if not blocks:
        return ToolResult(success=False, message="No JSON-LD blocks found")

    for block in blocks:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            continue

        recipe = _find_recipe_in_jsonld(data)
        if recipe:
            return ToolResult(
                success=True,
                message="Found Recipe schema markup",
                signals={"recipeSchema": recipe, "schemaFound": True},
            )

    return ToolResult(
        success=False,
        message="JSON-LD found but no Recipe schema type",
        signals={"schemaFound": False},
    )


def schema_recipe_extract(schema_data: dict[str, Any]) -> ToolResult:
    title = _clean_schema_text(schema_data.get("name", ""))
    if not title:
        return ToolResult(success=False, message="Schema has no recipe name")

    from app.tools.ingredient_parser import parse_ingredient_text

    ingredients = []
    raw_ingredients = schema_data.get("recipeIngredient", [])
    for i, text in enumerate(raw_ingredients):
        if isinstance(text, str):
            cleaned_text = _clean_schema_text(text)
            parsed = parse_ingredient_text(cleaned_text)
            ingredients.append({
                "text": parsed.get("displayText") or cleaned_text,
                "ingredientId": None,
                "quantity": parsed["quantity"],
                "unit": parsed["unit"],
            })

    steps = []
    step_images: dict[int, list[str]] = {}
    raw_instructions = schema_data.get("recipeInstructions", [])

    sections = [i for i in raw_instructions if isinstance(i, dict) and i.get("@type") == "HowToSection"]
    use_section_prefix = len(sections) > 1

    step_counter = 0
    for instr in raw_instructions:
        if isinstance(instr, str):
            step_counter += 1
            steps.append({"order": step_counter, "text": _clean_schema_text(instr), "mediaRefs": []})
        elif isinstance(instr, dict):
            instr_type = instr.get("@type", "")
            if instr_type == "HowToSection":
                section_name = _clean_schema_text(instr.get("name") or "")
                nested = instr.get("itemListElement", [])
                for sub in nested:
                    step_counter += 1
                    sub_text = ""
                    sub_imgs: list[str] = []
                    if isinstance(sub, str):
                        sub_text = _clean_schema_text(sub)
                    elif isinstance(sub, dict):
                        sub_text = _clean_schema_text(sub.get("text") or sub.get("name") or "")
                        sub_imgs = _extract_image_urls_from_schema_value(sub.get("image"))
                    if sub_text:
                        if use_section_prefix and section_name:
                            steps.append({"order": step_counter, "text": sub_text, "section": section_name, "mediaRefs": []})
                        else:
                            steps.append({"order": step_counter, "text": sub_text, "mediaRefs": []})
                        if sub_imgs:
                            step_images[step_counter] = sub_imgs
            else:
                step_text = _clean_schema_text(instr.get("text") or instr.get("name") or "")
                if step_text:
                    step_counter += 1
                    steps.append({"order": step_counter, "text": step_text, "mediaRefs": []})
                    instr_imgs = _extract_image_urls_from_schema_value(instr.get("image"))
                    if instr_imgs:
                        step_images[step_counter] = instr_imgs

    prep_time = _parse_duration(schema_data.get("prepTime"))
    cook_time = _parse_duration(schema_data.get("cookTime"))
    total_time = _parse_duration(schema_data.get("totalTime"))

    if cook_time is None and total_time is not None and prep_time is not None:
        cook_time = max(0, total_time - prep_time)
    elif cook_time is None and total_time is not None:
        cook_time = total_time

    servings = _parse_servings(schema_data.get("recipeYield"))
    raw_desc = schema_data.get("description", "")
    description = _clean_schema_text(raw_desc) if raw_desc else ""

    _MAX_GALLERY_IMAGES = 4  # 1 hero + 3 gallery
    all_images = _extract_image_urls_from_schema_value(schema_data.get("image"))
    seen_bases: set[str] = set()
    images: list[str] = []
    for img_url in all_images:
        base = img_url.split("?")[0].rsplit("-", 1)[0]
        if base not in seen_bases:
            seen_bases.add(base)
            images.append(img_url)
        if len(images) >= _MAX_GALLERY_IMAGES:
            break

    nutrition = _parse_schema_nutrition(schema_data.get("nutrition"))

    candidate_update = {
        "title": title,
        "ingredients": ingredients,
        "steps": steps,
        "description": description[:500] if description else None,
        "prepTimeMinutes": prep_time,
        "cookTimeMinutes": cook_time,
        "servings": servings,
        "nutrition": nutrition,
    }

    provenance = {
        field: {"sourceType": "schema_recipe_markup"}
        for field in ("title", "ingredients", "steps", "description", "prepTimeMinutes", "cookTimeMinutes", "servings", "nutrition")
        if candidate_update.get(field) is not None
    }

    confidence = "high" if (title and len(ingredients) >= 1 and len(steps) >= 1) else "medium"

    signals: dict[str, Any] = {
        "confidence": confidence,
        "imageUrls": images,
        "provenance": provenance,
        "extractionMethod": "schema_recipe_markup",
    }
    if step_images:
        signals["stepImages"] = {str(k): v for k, v in step_images.items()}

    return ToolResult(
        success=True,
        message=f"Extracted recipe '{title}' with {len(ingredients)} ingredients, {len(steps)} steps",
        candidate_update=candidate_update,
        signals=signals,
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), reraise=True)
async def llm_structured_extract(
    text: str,
    source_description: str = "webpage text",
    *,
    model_override: str | None = None,
    available_tags: list[str] | None = None,
) -> ToolResult:
    """Use the configured LLM provider to extract a recipe from raw text."""
    from app.core.llm import LLMConfigError, llm_chat

    truncated = text[:12000] if len(text) > 12000 else text

    prompt = (
        f"Extract the recipe from the following {source_description}. "
        "Return a JSON object with these fields:\n\n"

        "- title (string, required)\n"
        "- description (string, 1-2 sentences summarizing the dish)\n\n"

        "- ingredients (array of objects with: text, quantity, unit, section)\n"
        "  INGREDIENT RULES:\n"
        "  • 'text' = the ingredient name only (e.g. \"coriander seeds\", \"basmati rice\")\n"
        "  • 'quantity' = numeric amount as a string (e.g. \"2\", \"1/2\", \"3-4\"). "
        "Use null if unspecified.\n"
        "  • 'unit' = a standard cooking unit ONLY: tbsp, tsp, cup, oz, lb, g, kg, ml, L, "
        "pinch, piece, whole, bunch, sprig, can, clove, slice, handful. "
        "Use null if it's a count (e.g. \"2 onions\" → quantity=\"2\", unit=null, text=\"onions\"). "
        "Do NOT put descriptors, modifiers, or phrases like \"to taste\", \"as required\", \"large pinch\", "
        "\"nos\", \"80%\" etc. into the unit field — put those in the text field or omit them.\n"
        "  • 'section' = group name if the recipe has sub-components (e.g. \"Biryani Masala\", "
        "\"For the sauce\", \"Rice\"). null if no sections.\n"
        "  • Compound items like \"milk & saffron\" should be split into separate ingredients.\n"
        "  • Preserve ALL ingredients. Do NOT merge or skip any.\n\n"

        "- steps (array of objects with: order, text)\n"
        "  STEP RULES — THIS IS CRITICAL:\n"
        "  • Each distinct cooking action should be its own numbered step.\n"
        "  • PRESERVE the full detail from the source: specific temperatures, exact times, "
        "visual cues (\"until golden brown\"), quantities used at each stage, and chef "
        "techniques or tips.\n"
        "  • Do NOT collapse multiple actions into one summary. For example, do NOT write "
        "\"Prepare the biryani masala by grinding all spices\" — instead, write out the "
        "individual steps: dry roasting spices, cooling, grinding, etc.\n"
        "  • If the source describes a 20-step process, return ~20 steps, not 5 summaries.\n"
        "  • Include section context in each step if the recipe has sub-components "
        "(e.g. start with \"For the masala:\" or \"Rice:\").\n\n"

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
        "- nutrition (object or null) — only if explicitly stated in the source. "
        "Keys: calories, servingSize, carbohydrates, protein, fat, saturatedFat, "
        "unsaturatedFat, transFat, cholesterol, sodium, fiber, sugar. "
        "Values are strings with units (e.g. \"15 g\"). Omit keys not mentioned. "
        "Do NOT guess or calculate values.\n"
        "- notes (array of objects with: type, text) — tips, substitutions, storage advice, "
        "or variations the author mentions. type is one of: tip, substitution, storage, "
        "variation, general. Empty array if none found.\n"
        "- howToServe (string or null) — serving suggestions if mentioned by the author "
        "(e.g. \"Serve with crusty bread and a side salad\"). null if not mentioned.\n\n"
        'If you cannot identify a recipe, return {"error": "no_recipe_found"}.\n\n'
        f"Text:\n{truncated}"
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            json_mode=True,
            model_override=model_override,
        )
    except LLMConfigError as exc:
        return ToolResult(success=False, message=str(exc))
    except RuntimeError as exc:
        return ToolResult(success=False, message=str(exc))
    except Exception as exc:
        log.error("llm_extraction_failed", error=str(exc))
        return ToolResult(success=False, message=f"LLM extraction failed: {exc}")

    try:
        content = response.text
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            return ToolResult(success=False, message="LLM response contained no JSON")

        parsed = json.loads(json_match.group())

        if "error" in parsed:
            return ToolResult(
                success=False,
                message=parsed["error"],
                signals={"llmSaysNoRecipe": True},
            )

        ingredients = []
        for ing in parsed.get("ingredients", []):
            if isinstance(ing, str):
                ingredients.append({"text": ing, "ingredientId": None, "quantity": None, "unit": None})
            elif isinstance(ing, dict):
                entry: dict[str, Any] = {
                    "text": ing.get("text", ""),
                    "ingredientId": None,
                    "quantity": ing.get("quantity"),
                    "unit": ing.get("unit"),
                }
                if ing.get("section"):
                    entry["section"] = ing["section"]
                ingredients.append(entry)

        steps = []
        for i, step in enumerate(parsed.get("steps", [])):
            if isinstance(step, str):
                steps.append({"order": i + 1, "text": step, "mediaRefs": []})
            elif isinstance(step, dict):
                steps.append({
                    "order": step.get("order", i + 1),
                    "text": step.get("text", ""),
                    "mediaRefs": [],
                })

        raw_nutrition = parsed.get("nutrition")
        nutrition = raw_nutrition if isinstance(raw_nutrition, dict) and raw_nutrition else None

        raw_notes = parsed.get("notes", [])
        notes = _normalize_notes(raw_notes)

        raw_serve = parsed.get("howToServe")
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

        provenance = {
            field: {"sourceType": f"llm_extraction_from_{source_description.replace(' ', '_')}"}
            for field in candidate_update
            if candidate_update[field] is not None
        }

        confidence = "medium"
        if candidate_update["title"] and len(ingredients) >= 2 and len(steps) >= 2:
            confidence = "high"

        return ToolResult(
            success=True,
            message=f"LLM extracted '{candidate_update['title']}' with {len(ingredients)} ingredients",
            candidate_update=candidate_update,
            signals={
                "confidence": confidence,
                "provenance": provenance,
                "extractionMethod": f"llm_structured_extract_{source_description.replace(' ', '_')}",
            },
        )

    except json.JSONDecodeError:
        return ToolResult(success=False, message="LLM returned invalid JSON")


_VALID_NOTE_TYPES = {"tip", "substitution", "storage", "variation", "general"}


def _normalize_notes(raw: Any) -> list[dict[str, str]]:
    """Validate and normalize LLM-returned notes into [{type, text}, ...]."""
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, dict) and item.get("text"):
            note_type = item.get("type", "general")
            if note_type not in _VALID_NOTE_TYPES:
                note_type = "general"
            result.append({"type": note_type, "text": str(item["text"]).strip()})
    return result


_SCHEMA_NUTRITION_KEYS = {
    "calories": "calories",
    "carbohydrateContent": "carbohydrates",
    "proteinContent": "protein",
    "fatContent": "fat",
    "saturatedFatContent": "saturatedFat",
    "unsaturatedFatContent": "unsaturatedFat",
    "transFatContent": "transFat",
    "cholesterolContent": "cholesterol",
    "sodiumContent": "sodium",
    "fiberContent": "fiber",
    "sugarContent": "sugar",
    "servingSize": "servingSize",
}


def _parse_schema_nutrition(nutrition_data: Any) -> dict[str, str] | None:
    """Map schema.org NutritionInformation to our normalized nutrition dict."""
    if not isinstance(nutrition_data, dict):
        return None

    result: dict[str, str] = {}
    for schema_key, our_key in _SCHEMA_NUTRITION_KEYS.items():
        val = nutrition_data.get(schema_key)
        if val is not None:
            result[our_key] = str(val).strip()

    return result if result else None


def _extract_image_urls_from_schema_value(img: Any) -> list[str]:
    """Pull image URLs from a schema.org image value (string, list, or ImageObject)."""
    urls: list[str] = []
    if isinstance(img, str) and img.startswith("http"):
        urls.append(img)
    elif isinstance(img, list):
        for item in img:
            if isinstance(item, str) and item.startswith("http"):
                urls.append(item)
            elif isinstance(item, dict) and "url" in item:
                urls.append(item["url"])
    elif isinstance(img, dict) and "url" in img:
        urls.append(img["url"])
    return urls


def _find_recipe_in_jsonld(data: Any) -> dict | None:
    if isinstance(data, dict):
        schema_type = data.get("@type", "")
        if isinstance(schema_type, list):
            if "Recipe" in schema_type:
                return data
        elif schema_type == "Recipe":
            return data
        if "@graph" in data:
            return _find_recipe_in_jsonld(data["@graph"])
    elif isinstance(data, list):
        for item in data:
            result = _find_recipe_in_jsonld(item)
            if result:
                return result
    return None


ISO_DURATION_RE = re.compile(
    r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", re.IGNORECASE
)


def _parse_duration(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    m = ISO_DURATION_RE.match(s)
    if m:
        hours = int(m.group(1) or 0)
        minutes = int(m.group(2) or 0)
        return hours * 60 + minutes
    digits = re.findall(r"\d+", s)
    if digits:
        return int(digits[0])
    return None


def _parse_servings(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if isinstance(value, list):
        s = str(value[0]).strip()
    digits = re.findall(r"\d+", s)
    if digits:
        return int(digits[0])
    return None


_IMG_TAG_RE = re.compile(
    r"<img\s+([^>]+)>",
    re.IGNORECASE,
)

_SKIP_PATTERNS = (
    "favicon", "logo", "icon", "avatar", "gravatar", "pixel",
    "tracking", "/ad/", "/ads/", "advertisement", "banner", "widget",
    "button", "sprite", "emoji", "badge", "arrow",
    "/themes/", "/plugins/",
    "author-photo", "social-share",
    "pinterest", "facebook-share", "twitter-share",
    "wp-content/themes", "wp-includes",
)

_BOOST_PATTERNS = (
    "how-to-make", "process", "step", "making",
    "ingredient", "prepare", "method", "instruction",
)

_RESIZE_SUFFIX_RE = re.compile(r"-\d+x\d+(?=\.\w+$)")


def _strip_resize_suffix(url: str) -> str:
    """Remove WordPress-style resize suffix (e.g. -500x500) from filename."""
    return _RESIZE_SUFFIX_RE.sub("", url)


def extract_images_from_html(html: str, page_url: str | None = None, *, limit: int = 15) -> list[str]:
    """Extract recipe-relevant image URLs from raw HTML (legacy, flat list)."""
    candidates = extract_images_with_context(html, page_url, limit=limit)
    return [c["url"] for c in candidates]


def extract_images_with_context(
    html: str,
    page_url: str | None = None,
    *,
    limit: int = 20,
) -> list[dict[str, str]]:
    """Extract images from HTML with alt text, filename, and context.

    Returns list of dicts: {url, alt, filename, context}.
    Filters obvious junk and deduplicates by base image identity.
    """
    from urllib.parse import urlparse

    page_domain = urlparse(page_url).hostname if page_url else None
    img_tags = _IMG_TAG_RE.findall(html)
    if not img_tags:
        return []

    seen_bases: set[str] = set()
    scored: list[tuple[int, dict[str, str]]] = []

    for attrs in img_tags:
        # Try src first, then fall back to largest srcSet entry
        src_m = re.search(
            r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp))(?:\?[^"\']*)?["\']',
            attrs, re.IGNORECASE,
        )
        if src_m:
            raw_url = src_m.group(1)
        else:
            srcset_m = re.search(r'srcSet=["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            if not srcset_m:
                continue
            entries = srcset_m.group(1).split(",")
            best_url, best_w = None, 0
            for entry in entries:
                parts = entry.strip().split()
                if not parts:
                    continue
                url_part = parts[0]
                if not re.search(r"\.(?:jpg|jpeg|png|webp)", url_part, re.IGNORECASE):
                    continue
                w = 0
                if len(parts) > 1 and parts[1].endswith("w"):
                    try:
                        w = int(parts[1][:-1])
                    except ValueError:
                        pass
                if w > best_w or best_url is None:
                    best_url, best_w = url_part, w
            if not best_url:
                continue
            raw_url = best_url
        base_url = raw_url.split("?")[0]
        canonical = _strip_resize_suffix(base_url)
        if canonical in seen_bases:
            continue
        seen_bases.add(canonical)

        low = base_url.lower()
        if any(skip in low for skip in _SKIP_PATTERNS):
            continue

        alt_m = re.search(r'alt=["\']([^"\']*)["\']', attrs, re.IGNORECASE)
        alt = alt_m.group(1).strip() if alt_m else ""

        filename = base_url.rsplit("/", 1)[-1] if "/" in base_url else base_url

        score = 0
        if page_domain and page_domain in low:
            score += 3
        if "/uploads/" in low or "/content/" in low or "/tachyon/" in low:
            score += 2
        if any(boost in low for boost in _BOOST_PATTERNS):
            score += 4
        if any(boost in alt.lower() for boost in _BOOST_PATTERNS):
            score += 3
        if "-social" in low:
            score -= 2
        if any(dim in low for dim in ("500x", "720x", "1024x", "1200x")):
            score += 1

        scored.append((score, {
            "url": base_url,
            "alt": alt,
            "filename": filename,
            "context": "",
        }))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:limit]]


async def classify_recipe_images(
    image_candidates: list[dict[str, str]],
    steps: list[dict[str, Any]],
    recipe_title: str,
    *,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Use LLM to filter irrelevant images and map relevant ones to steps.

    Accepts image candidates (with url, alt, filename) and recipe steps.
    Returns {galleryImages: [url, ...], stepImages: {"1": [url], ...}}.
    """
    from app.core.llm import llm_chat

    if not image_candidates:
        return {"galleryImages": [], "stepImages": {}}

    img_list = "\n".join(
        f"{i+1}. filename=\"{c['filename']}\" alt=\"{c['alt']}\""
        for i, c in enumerate(image_candidates)
    )
    step_list = "\n".join(
        f"Step {s['order']}: {s['text'][:120]}"
        for s in steps
    )

    prompt = (
        f'Recipe: "{recipe_title}"\n\n'
        f"Cooking steps:\n{step_list}\n\n"
        f"Images found on the page:\n{img_list}\n\n"
        "Classify each image into one of these categories:\n"
        '- "step_N" — image clearly shows work related to step N (use the step number)\n'
        '- "gallery" — photo of the FINISHED/PLATED dish (the final output that a reader would want to see)\n'
        '- "skip" — everything else: process shots without a clear step, ingredient flat-lays,\n'
        "  author photos, pets, site branding, social icons, ads, lifestyle shots,\n"
        "  generic cooking images, or duplicate angles of the same dish\n\n"
        "Return a JSON object with:\n"
        '- "classifications": array of objects {imageNumber, category, reason}\n'
        "  where imageNumber is the 1-based image index from the list above,\n"
        '  category is "step_N", "gallery", or "skip",\n'
        "  and reason is a brief explanation.\n\n"
        "RULES:\n"
        '- Only use "gallery" for images showing the completed, plated/served dish.\n'
        "- AT MOST 3 images should be gallery — pick the best/most distinct angles.\n"
        "  If more than 3 look like the finished dish, keep the 3 best and skip the rest.\n"
        '- Only use "step_N" when the filename or alt text strongly links to that step.\n'
        "- When in doubt, skip. Be aggressive about filtering irrelevant images.\n"
        "- Process shots that don't clearly match a step should be skipped.\n"
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            json_mode=True,
            model_override=model_override,
        )

        content = response.text
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            log.warning("image_classify_no_json")
            return _fallback_classify(image_candidates)

        parsed = json.loads(json_match.group())
        classifications = parsed.get("classifications", [])

        gallery_images: list[str] = []
        step_images: dict[str, list[str]] = {}

        for entry in classifications:
            idx = entry.get("imageNumber", 0) - 1
            category = entry.get("category", "skip")
            if idx < 0 or idx >= len(image_candidates):
                continue

            url = image_candidates[idx]["url"]
            if category == "skip":
                continue
            elif category == "gallery":
                gallery_images.append(url)
            elif category.startswith("step_"):
                step_num = category.replace("step_", "")
                step_images.setdefault(step_num, []).append(url)

        return {"galleryImages": gallery_images[:3], "stepImages": step_images}

    except Exception as exc:
        log.warning("image_classify_failed", error=str(exc))
        return _fallback_classify(image_candidates)


_FALLBACK_SKIP = (
    "dozer", "nagi", "author", "profile", "avatar", "headshot",
    "logo", "icon", "badge", "social", "pinterest", "facebook",
    "twitter", "collage", "graphic", "text-overlay",
    "step", "process", "making", "how-to", "ingredient",
    "batter", "mixing", "chopping", "prep",
)

_FALLBACK_PREFER = ("finished", "final", "served", "plated", "ready")


def _fallback_classify(image_candidates: list[dict[str, str]]) -> dict[str, Any]:
    """Heuristic fallback when LLM classification fails — keep max 3 best photos."""
    scored: list[tuple[int, str]] = []
    for c in image_candidates:
        low_file = c["filename"].lower()
        low_alt = c["alt"].lower()
        combined = low_file + " " + low_alt
        if any(skip in combined for skip in _FALLBACK_SKIP):
            continue
        score = 0
        if any(pref in combined for pref in _FALLBACK_PREFER):
            score += 5
        scored.append((score, c["url"]))
    scored.sort(key=lambda x: x[0], reverse=True)
    gallery = [url for _, url in scored[:3]]
    return {"galleryImages": gallery, "stepImages": {}}


async def llm_refine_candidate(
    candidate: dict[str, Any],
    source_text: str | None = None,
    *,
    model_override: str | None = None,
) -> dict[str, Any]:
    """Post-extraction LLM pass to refine ingredients and steps quality.

    Fixes bad unit parsing, adds ingredient sections, expands summary steps
    into detailed ones using source text context when available.
    Returns the refined candidate dict (same structure, better content).
    """
    from app.core.llm import llm_chat

    ingredients = candidate.get("ingredients", [])
    steps = candidate.get("steps", [])

    if len(ingredients) < 2 and len(steps) < 2:
        return candidate

    ing_json = json.dumps(ingredients, indent=2)
    steps_json = json.dumps(steps, indent=2)

    source_context = ""
    if source_text:
        trimmed = source_text[:8000]
        source_context = (
            f"\n\nORIGINAL SOURCE TEXT (use this to add detail to steps and fix ingredients):\n"
            f"{trimmed}\n"
        )

    prompt = (
        f"Refine this extracted recipe for quality. The recipe title is: \"{candidate.get('title', '')}\"\n\n"

        "CURRENT INGREDIENTS:\n"
        f"{ing_json}\n\n"

        "CURRENT STEPS:\n"
        f"{steps_json}\n"
        f"{source_context}\n\n"

        "Return a JSON object with two keys: \"ingredients\" and \"steps\".\n\n"

        "INGREDIENT REFINEMENT RULES:\n"
        "1. Fix invalid units: 'nos', 'no', 'numbers', 'to taste', 'as required', "
        "'if required', 'large pinch', '80%' are NOT valid units. "
        "Valid units: tbsp, tsp, cup, oz, lb, g, kg, ml, L, pinch, piece, whole, "
        "bunch, sprig, can, clove, slice, handful. Use null for counts or unspecified.\n"
        "2. Move modifiers/notes from 'unit' into 'text': e.g. \"a large pinch\" → "
        "quantity=null, unit=\"pinch\", text=\"salt, large\". \"to taste\" → add \"to taste\" "
        "to the text field, unit=null.\n"
        "3. Add 'section' field to group ingredients by sub-recipe (e.g. \"Biryani Masala\", "
        "\"Birista\", \"Rice\", \"Marination\"). If no clear sections, use null.\n"
        "4. Split compound ingredients: \"milk & saffron\" → two separate entries.\n"
        "5. Each ingredient object should have: text, quantity, unit, section.\n"
        "6. Deduplicate only if truly the same ingredient in the same section.\n\n"

        "STEP REFINEMENT RULES:\n"
        "1. If a step summarizes multiple actions (e.g. \"Prepare the biryani masala by grinding "
        "all the listed spices\"), expand it into the actual detailed sub-steps using the "
        "source text. Include: specific spice names, dry-roasting instructions, cooling, "
        "grinding texture, timing.\n"
        "2. Each step should describe ONE clear action with specific details: temperatures, "
        "times (e.g. \"fry for 8-10 minutes until deep golden brown\"), visual cues, quantities.\n"
        "3. Preserve any chef tips or technique details from the source.\n"
        "4. Keep the steps in logical cooking order. Re-number sequentially.\n"
        "5. Each step object should have: order (integer), text (string).\n"
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8192,
            json_mode=True,
            model_override=model_override,
        )

        json_match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not json_match:
            log.warning("llm_refine_no_json")
            return candidate

        refined = json.loads(json_match.group())

        refined_ingredients = []
        for ing in refined.get("ingredients", []):
            if isinstance(ing, dict) and ing.get("text"):
                entry: dict[str, Any] = {
                    "text": ing.get("text", ""),
                    "ingredientId": None,
                    "quantity": ing.get("quantity"),
                    "unit": ing.get("unit"),
                }
                if ing.get("section"):
                    entry["section"] = ing["section"]
                refined_ingredients.append(entry)

        refined_steps = []
        for i, step in enumerate(refined.get("steps", [])):
            if isinstance(step, str) and step.strip():
                refined_steps.append({"order": i + 1, "text": step, "mediaRefs": []})
            elif isinstance(step, dict) and step.get("text"):
                refined_steps.append({
                    "order": step.get("order", i + 1),
                    "text": step["text"],
                    "mediaRefs": [],
                })

        if len(refined_ingredients) >= len(ingredients) * 0.7:
            candidate["ingredients"] = refined_ingredients
        else:
            log.warning("llm_refine_skipped_ingredients",
                        original=len(ingredients), refined=len(refined_ingredients))

        if len(refined_steps) >= len(steps):
            candidate["steps"] = refined_steps
        else:
            log.warning("llm_refine_skipped_steps",
                        original=len(steps), refined=len(refined_steps))

        log.info("llm_refine_complete",
                 ingredients=len(candidate["ingredients"]),
                 steps=len(candidate["steps"]))

        return candidate

    except Exception as exc:
        log.warning("llm_refine_failed", error=str(exc))
        return candidate
