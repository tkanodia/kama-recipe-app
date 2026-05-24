"""T-032: Text ingestion tools — cleaning, structure analysis, and preview generation."""

import re
import unicodedata

import structlog

from app.tools.base import ToolResult

log = structlog.get_logger()

_MULTI_WHITESPACE = re.compile(r"[ \t]{3,}")
_MULTI_NEWLINES = re.compile(r"\n{3,}")
_URL_NOISE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMAIL_NOISE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_UNICODE_REPLACEMENTS = re.compile(r"[\u200b\u200c\u200d\ufeff\u00ad]")
_ZERO_WIDTH = re.compile(r"[\u2028\u2029]")

_RECIPE_KEYWORDS = [
    "ingredient", "ingredients", "direction", "directions",
    "instruction", "instructions", "step", "steps",
    "servings", "serves", "prep time", "cook time",
    "preparation", "method", "recipe", "preheat",
    "tablespoon", "teaspoon", "tbsp", "tsp", "cup", "cups",
    "ounce", "oz", "pound", "lb", "gram", "kg", "ml",
    "bake", "stir", "mix", "fold", "chop", "dice", "simmer",
    "yield", "total time", "ready in",
]

_SECTION_HEADERS = re.compile(
    r"(?:^|\n)\s*(?:"
    r"ingredients?|directions?|instructions?|steps?|method|preparation|"
    r"notes?|tips?|variations?|nutrition(?:\s+facts)?|description|"
    r"for the \w+|sauce|topping|garnish|marinade|frosting|filling"
    r")\s*[:\-\n]",
    re.IGNORECASE,
)

_NUMBERED_STEP = re.compile(r"(?:^|\n)\s*(?:step\s+)?\d+[\.\)]\s+", re.IGNORECASE)
_BULLET_ITEM = re.compile(r"(?:^|\n)\s*[-•·*]\s+")
_MEASUREMENT = re.compile(
    r"\d+\s*(?:\/\d+)?\s*(?:cup|tbsp|tsp|oz|lb|g|kg|ml|l|teaspoon|tablespoon|pound|ounce)s?\b",
    re.IGNORECASE,
)


def clean_text(raw_text: str) -> ToolResult:
    """Clean pasted text: normalize whitespace, remove noise, strip unicode artifacts.

    Returns a ToolResult with the cleaned text and metadata about what changed.
    """
    if not raw_text or not raw_text.strip():
        return ToolResult(
            success=False,
            message="Empty text provided",
            signals={"originalLength": len(raw_text) if raw_text else 0},
        )

    original_length = len(raw_text)

    text = raw_text
    text = unicodedata.normalize("NFKC", text)
    text = _UNICODE_REPLACEMENTS.sub("", text)
    text = _ZERO_WIDTH.sub("\n", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_WHITESPACE.sub("  ", text)
    text = _MULTI_NEWLINES.sub("\n\n", text)

    lines = text.split("\n")
    cleaned_lines = [line.rstrip() for line in lines]
    text = "\n".join(cleaned_lines)
    text = text.strip()

    cleaned_length = len(text)
    removed = original_length - cleaned_length
    noise_pct = round((removed / original_length) * 100, 1) if original_length > 0 else 0.0

    log.debug("text_cleaned", original_length=original_length, cleaned_length=cleaned_length, noise_pct=noise_pct)

    return ToolResult(
        success=True,
        message=f"Cleaned text: {original_length} → {cleaned_length} chars ({noise_pct}% noise removed)",
        artifacts=[{
            "artifactType": "cleaned_pasted_text",
            "payload": {
                "text": text,
                "originalLength": original_length,
                "cleanedLength": cleaned_length,
                "noiseRemovedPct": noise_pct,
            },
        }],
        signals={
            "cleanedText": text,
            "originalLength": original_length,
            "cleanedLength": cleaned_length,
            "noiseRemovedPct": noise_pct,
        },
    )


def analyze_text_structure(text: str) -> ToolResult:
    """Analyze pasted text for recipe-like structure and section boundaries.

    Returns recipeLikelihood (high/medium/low), detectedSections, and isRecipeText flag.
    """
    if not text or not text.strip():
        return ToolResult(
            success=False,
            message="No text to analyze",
            signals={"recipeLikelihood": "low", "isRecipeText": False},
        )

    lower = text.lower()

    keyword_hits = sum(1 for kw in _RECIPE_KEYWORDS if kw in lower)
    section_matches = _SECTION_HEADERS.findall(text)
    numbered_steps = _NUMBERED_STEP.findall(text)
    bullet_items = _BULLET_ITEM.findall(text)
    measurements = _MEASUREMENT.findall(text)

    detected_sections = _identify_sections(text)

    score = 0
    score += min(keyword_hits, 10)
    score += len(section_matches) * 3
    score += min(len(numbered_steps), 5) * 2
    score += min(len(bullet_items), 5)
    score += min(len(measurements), 8) * 2

    if score >= 15:
        recipe_likelihood = "high"
    elif score >= 6:
        recipe_likelihood = "medium"
    else:
        recipe_likelihood = "low"

    is_recipe = recipe_likelihood in ("high", "medium")

    log.debug(
        "text_structure_analyzed",
        keyword_hits=keyword_hits,
        section_count=len(section_matches),
        score=score,
        likelihood=recipe_likelihood,
    )

    return ToolResult(
        success=True,
        message=f"Text analysis: recipeLikelihood={recipe_likelihood}, {len(detected_sections)} sections found",
        artifacts=[{
            "artifactType": "text_structure_analysis",
            "payload": {
                "recipeLikelihood": recipe_likelihood,
                "isRecipeText": is_recipe,
                "detectedSections": detected_sections,
                "keywordHits": keyword_hits,
                "sectionHeaderCount": len(section_matches),
                "numberedStepCount": len(numbered_steps),
                "measurementCount": len(measurements),
                "structureScore": score,
            },
        }],
        signals={
            "recipeLikelihood": recipe_likelihood,
            "isRecipeText": is_recipe,
            "detectedSections": detected_sections,
            "structureScore": score,
        },
    )


def create_text_preview(raw_text: str) -> ToolResult:
    """Generate a source_preview artifact from pasted text (first 200 chars as excerpt)."""
    if not raw_text or not raw_text.strip():
        return ToolResult(success=False, message="Empty text — no preview to create")

    excerpt = raw_text.strip()[:200]
    if len(raw_text.strip()) > 200:
        excerpt += "…"

    word_count = len(raw_text.split())
    line_count = len(raw_text.strip().splitlines())

    return ToolResult(
        success=True,
        message="Created text source preview",
        artifacts=[{
            "artifactType": "source_preview",
            "payload": {
                "previewType": "pasted_text",
                "excerpt": excerpt,
                "wordCount": word_count,
                "lineCount": line_count,
                "totalLength": len(raw_text),
            },
        }],
        signals={
            "previewGenerated": True,
            "wordCount": word_count,
        },
    )


def _identify_sections(text: str) -> list[dict]:
    """Detect probable section boundaries with start/end character positions."""
    sections: list[dict] = []
    lines = text.split("\n")

    ingredient_header = re.compile(
        r"^\s*(?:ingredients?|what you(?:'ll)? need|you will need)\s*[:\-]?\s*$",
        re.IGNORECASE,
    )
    instruction_header = re.compile(
        r"^\s*(?:instructions?|directions?|method|steps?|preparation|how to (?:make|prepare))\s*[:\-]?\s*$",
        re.IGNORECASE,
    )
    notes_header = re.compile(
        r"^\s*(?:notes?|tips?|variations?|nutrition)\s*[:\-]?\s*$",
        re.IGNORECASE,
    )

    current_section: dict | None = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue

        detected_type = None
        if ingredient_header.match(stripped):
            detected_type = "ingredients"
        elif instruction_header.match(stripped):
            detected_type = "instructions"
        elif notes_header.match(stripped):
            detected_type = "notes"

        if detected_type:
            if current_section:
                current_section["endLine"] = i - 1
                sections.append(current_section)
            current_section = {
                "sectionType": detected_type,
                "startLine": i,
                "endLine": len(lines) - 1,
                "headerText": stripped,
            }

    if current_section:
        current_section["endLine"] = len(lines) - 1
        sections.append(current_section)

    return sections
