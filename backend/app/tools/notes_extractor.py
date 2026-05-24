"""Extract chef's notes, tips, and tricks from recipe pages.

Tier 1: HTML pattern matching for common recipe plugin note containers.
Tier 2: LLM fallback when HTML patterns find nothing.
"""

from __future__ import annotations

import html as html_mod
import re
from typing import Any

import structlog

from app.tools.extraction_tools import _normalize_notes

log = structlog.get_logger()

_NOTE_SECTION_CLASSES = [
    "wprm-recipe-notes",
    "tasty-recipes-notes",
    "recipe-notes",
    "recipe-card-notes",
    "easyrecipe-notes",
    "mv-recipe-notes",
    "recipe_notes",
]

_NOTE_SECTION_OPEN_RE = re.compile(
    r'<(div|section|aside)[^>]*class=["\'][^"\']*'
    r"(?:" + "|".join(re.escape(c) for c in _NOTE_SECTION_CLASSES) + r")"
    r'[^"\']*["\'][^>]*>',
    re.IGNORECASE,
)

_NOTE_HEADING_RE = re.compile(
    r"<h[2-4][^>]*>\s*(?:Notes?|Tips?|Chef.?s?\s*(?:Notes?|Tips?)|"
    r"Recipe\s*Notes?|Cooking\s*(?:Notes?|Tips?)|Kitchen\s*Tips?|"
    r"Helpful\s*(?:Tips?|Hints?))\s*</h[2-4]>"
    r"(.*?)(?=<h[2-4]|<div\s+class=[\"'](?:wprm|tasty|recipe)|$)",
    re.IGNORECASE | re.DOTALL,
)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_OPEN_TAG_RE = re.compile(r"<(div|section|aside)[\s>]", re.IGNORECASE)
_CLOSE_TAG_RE = re.compile(r"</(div|section|aside)\s*>", re.IGNORECASE)


def _extract_balanced_block(html: str, start: int, tag: str) -> str | None:
    """Extract the inner content of a tag starting at *start*, handling nesting."""
    depth = 1
    pos = start
    tag_lower = tag.lower()
    open_re = re.compile(rf"<{tag_lower}[\s>]", re.IGNORECASE)
    close_re = re.compile(rf"</{tag_lower}\s*>", re.IGNORECASE)
    while depth > 0 and pos < len(html):
        next_open = open_re.search(html, pos)
        next_close = close_re.search(html, pos)
        if next_close is None:
            break
        if next_open and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            if depth == 0:
                return html[start:next_close.start()]
            pos = next_close.end()
    return None


def _strip_html(raw: str) -> str:
    text = _HTML_TAG_RE.sub(" ", raw)
    text = html_mod.unescape(text)
    return _WHITESPACE_RE.sub(" ", text).strip()


def _classify_note(text: str) -> str:
    lower = text.lower()
    # Check opening label first (e.g. "Leftovers and storage – ...")
    label = lower[:60].split("–")[0].split("-")[0].strip()

    if any(w in label for w in ("store", "storage", "leftover", "reheat", "freez")):
        return "storage"
    if any(w in label for w in ("substitut", "replac", "swap", "instead")):
        return "substitution"

    if any(w in lower for w in ("store", "storage", "refrigerat", "freeze", "keep for up to", "leftover", "shelf life", "reheat", "airtight container")):
        return "storage"
    if any(w in lower for w in ("substitut", "replac", "swap", "instead of", "alternative", "in place of", "closest substitute", "also be used")):
        return "substitution"
    if any(w in lower for w in ("variation", "vary", "try adding", "you can also")):
        return "variation"
    if any(w in lower for w in ("tip", "trick", "make sure", "pro tip", "hint", "key is", "recommend", "optional but")):
        return "tip"
    return "general"


_NOISE_PHRASES = re.compile(
    r"^(?:nutrition\s+per\s+serving|nutritional?\s+info|"
    r"nutrition\s+facts?|per\s+serving|amount\s+per\s+serving)$",
    re.IGNORECASE,
)


_WPRM_SPACER_RE = re.compile(
    r'<div[^>]*class=["\'][^"\']*wprm-spacer[^"\']*["\'][^>]*>\s*</div>',
    re.IGNORECASE,
)


def _split_into_notes(raw_text: str) -> list[str]:
    """Split a block of note text into individual note items."""
    # Phase 1: split on WPRM spacer divs (each spacer separates logical notes,
    # but sub-lists within a note stay grouped with their parent text).
    spacer_chunks = _WPRM_SPACER_RE.split(raw_text)

    # Merge chunks: if a chunk is inside a list (starts with <li>, </li>,
    # <ul>, or similar) it's a sub-item of the previous note.
    merged: list[str] = []
    for chunk in spacer_chunks:
        stripped = chunk.strip()
        if not stripped:
            continue
        is_sublist = bool(re.match(
            r"^\s*</?(?:li|ul|ol)\b", stripped, re.IGNORECASE
        ))
        if is_sublist and merged:
            merged[-1] += " " + stripped
        else:
            merged.append(stripped)

    items: list[str] = []
    for block in merged:
        fragments = re.split(r"(?:<br\s*/?>|</?p[^>]*>|•|◦)", block)
        for frag in fragments:
            cleaned = _strip_html(frag)
            if len(cleaned) < 15:
                continue
            # Split on inline numbered prefixes ("1. Foo ... 2. Bar ...")
            numbered = re.split(r"(?:^|\s)(?=\d+\.\s+[A-Z])", cleaned)
            for part in numbered:
                part = re.sub(r"^\d+\.\s*", "", part).strip()
                if len(part) > 15 and not _NOISE_PHRASES.match(part):
                    items.append(part)

    if not items and len(raw_text.strip()) > 15:
        full = _strip_html(raw_text)
        if not _NOISE_PHRASES.match(full):
            items.append(full)

    return items


def _add_notes(
    raw_block: str,
    notes: list[dict[str, str]],
    seen: set[str],
) -> None:
    for text in _split_into_notes(raw_block):
        norm = text.lower().strip()
        if norm not in seen:
            seen.add(norm)
            notes.append({"type": _classify_note(text), "text": text})


def extract_chef_notes_from_html(html: str) -> list[dict[str, str]]:
    """Tier 1: Extract notes from recipe page HTML using pattern matching.

    Looks for common recipe plugin containers and heading-based note sections.
    Returns a list of {type, text} dicts, or empty list if nothing found.
    """
    notes: list[dict[str, str]] = []
    seen_texts: set[str] = set()

    for match in _NOTE_SECTION_OPEN_RE.finditer(html):
        tag = match.group(1)
        content_start = match.end()
        block = _extract_balanced_block(html, content_start, tag)
        if block:
            _add_notes(block, notes, seen_texts)

    for match in _NOTE_HEADING_RE.finditer(html):
        _add_notes(match.group(1), notes, seen_texts)

    return notes


async def extract_chef_notes_llm(
    page_text: str,
    *,
    model_override: str | None = None,
) -> list[dict[str, str]]:
    """Tier 2: LLM fallback for notes extraction when HTML patterns find nothing."""
    from app.core.llm import LLMConfigError, llm_chat
    import json

    truncated = page_text[:8000] if len(page_text) > 8000 else page_text

    prompt = (
        "Below is the text content of a recipe page. Extract any chef's notes, tips, "
        "cooking tricks, substitution suggestions, storage instructions, or recipe variations "
        "mentioned by the author.\n\n"
        "Return a JSON object with a single key \"notes\" containing an array of objects, "
        "each with:\n"
        "- type: one of \"tip\", \"substitution\", \"storage\", \"variation\", \"general\"\n"
        "- text: the note content\n\n"
        "Only extract notes that are actually present in the text. Do NOT invent notes.\n"
        "If there are no notes, return {\"notes\": []}.\n\n"
        f"Text:\n{truncated}"
    )

    try:
        response = await llm_chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            json_mode=True,
            model_override=model_override,
        )

        import re as _re
        json_match = _re.search(r"\{.*\}", response.text, _re.DOTALL)
        if not json_match:
            return []

        parsed = json.loads(json_match.group())
        return _normalize_notes(parsed.get("notes", []))

    except LLMConfigError:
        log.warning("notes_llm_not_configured")
        return []
    except Exception as exc:
        log.error("notes_llm_extraction_failed", error=str(exc))
        return []


_SERVE_HEADING_RE = re.compile(
    r"<h[2-5][^>]*>\s*(?:How\s+to\s+[Ss]erve|Serving\s+[Ss]uggestions?|"
    r"What\s+to\s+[Ss]erve\s+[Ww]ith|Serve\s+[Ww]ith|Serving\s+[Ii]deas?)"
    r"[^<]*</h[2-5]>"
    r"(.*?)(?=<h[2-5]|<div\s+class=[\"'](?:wprm|tasty|recipe)|$)",
    re.IGNORECASE | re.DOTALL,
)

_SERVE_SECTION_RE = re.compile(
    r'<(?:div|section)[^>]*class=["\'][^"\']*'
    r"(?:wprm-recipe-serving|serving-suggestions|how-to-serve)"
    r'[^"\']*["\'][^>]*>(.*?)</(?:div|section)>',
    re.IGNORECASE | re.DOTALL,
)


def extract_how_to_serve_from_html(html: str) -> str | None:
    """Extract serving suggestions from recipe page HTML.

    Returns a cleaned text string, or None if nothing found.
    """
    for pattern in (_SERVE_SECTION_RE, _SERVE_HEADING_RE):
        match = pattern.search(html)
        if match:
            text = _strip_html(match.group(1))
            if len(text) > 20:
                return text

    return None
