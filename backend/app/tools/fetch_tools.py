"""T-019: httpx_fetch — fetch URL content with redirect following.
   T-098: extract_page_text — extract readable text from HTML via trafilatura."""

import re

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import llm_breaker
from app.tools.base import ToolResult

log = structlog.get_logger()

USER_AGENT = (
    "Mozilla/5.0 (compatible; KamaBot/1.0; +https://kama.app)"
)
JSONLD_PATTERN = re.compile(
    r'<script[^>]+type=["\']?application/ld\+json["\']?[^>]*>', re.IGNORECASE
)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def httpx_fetch(url: str, timeout: float = 15.0) -> ToolResult:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.TimeoutException:
        return ToolResult(success=False, message=f"Timeout fetching {url}")
    except httpx.HTTPStatusError as e:
        return ToolResult(success=False, message=f"HTTP {e.response.status_code} for {url}")
    except httpx.RequestError as e:
        return ToolResult(success=False, message=f"Request error: {e}")

    html = resp.text
    resolved_url = str(resp.url)

    has_schema = bool(JSONLD_PATTERN.search(html))
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    page_title = title_match.group(1).strip() if title_match else None

    looks_like_recipe = _check_recipe_signals(html)

    artifacts = [
        {
            "artifactType": "url_metadata",
            "payload": {
                "originalUrl": url,
                "resolvedUrl": resolved_url,
                "statusCode": resp.status_code,
                "pageTitle": page_title,
                "contentLength": len(html),
                "hasRecipeSchema": has_schema,
            },
        },
        {
            "artifactType": "source_preview",
            "payload": {
                "previewType": "link_card",
                "title": page_title,
                "url": resolved_url,
                "domain": resp.url.host,
            },
        },
    ]

    return ToolResult(
        success=True,
        message=f"Fetched {resolved_url} ({len(html)} chars)",
        artifacts=artifacts,
        signals={
            "html": html,
            "resolvedUrl": resolved_url,
            "has_recipe_schema": has_schema,
            "looks_like_recipe_page": looks_like_recipe,
            "page_title": page_title,
        },
    )


def extract_page_text(html: str, source_url: str = "") -> ToolResult:
    try:
        import trafilatura
    except ImportError:
        return ToolResult(success=False, message="trafilatura not installed")

    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=False,
    )

    if not extracted or len(extracted.strip()) < 50:
        return ToolResult(
            success=False,
            message="Extracted text too short or empty",
            signals={"quality": "low", "textLength": len(extracted or "")},
        )

    content_sections = _detect_sections(extracted)

    artifact = {
        "artifactType": "cleaned_page_text",
        "payload": {
            "sourceUrl": source_url,
            "text": extracted,
            "extractionMethod": "main_content_cleaning",
            "contentSections": content_sections,
            "textLength": len(extracted),
        },
    }

    quality = "high" if len(extracted) > 500 else "medium"
    if len(extracted) < 200:
        quality = "low"

    return ToolResult(
        success=True,
        message=f"Extracted {len(extracted)} chars of page text",
        artifacts=[artifact],
        signals={
            "cleanedText": extracted,
            "quality": quality,
            "textLength": len(extracted),
            "contentSections": content_sections,
        },
    )


def _check_recipe_signals(html: str) -> bool:
    lower = html.lower()
    recipe_keywords = ["ingredient", "instruction", "recipe", "prep time", "cook time", "servings"]
    matches = sum(1 for kw in recipe_keywords if kw in lower)
    return matches >= 2


def _detect_sections(text: str) -> list[dict]:
    sections: list[dict] = []
    lines = text.split("\n")

    current_type = "unknown"
    section_start = 0

    ingredient_patterns = re.compile(
        r"^\s*[-•·*]?\s*\d*[./]?\d*\s*(cup|tbsp|tsp|oz|lb|g|kg|ml|l|teaspoon|tablespoon|pound|ounce)",
        re.IGNORECASE,
    )
    step_patterns = re.compile(r"^\s*(step\s+)?\d+[.):\s]", re.IGNORECASE)

    for i, line in enumerate(lines):
        stripped = line.strip().lower()

        if not stripped:
            continue

        if any(kw in stripped for kw in ("ingredient", "what you need", "you will need")):
            if current_type != "ingredients":
                if section_start < i:
                    sections.append({"sectionType": current_type, "startLine": section_start, "endLine": i - 1})
                current_type = "ingredients"
                section_start = i
        elif any(kw in stripped for kw in ("instruction", "direction", "method", "steps", "how to make")):
            if current_type != "instructions":
                if section_start < i:
                    sections.append({"sectionType": current_type, "startLine": section_start, "endLine": i - 1})
                current_type = "instructions"
                section_start = i
        elif any(kw in stripped for kw in ("note", "tip", "variation")):
            if current_type != "notes":
                if section_start < i:
                    sections.append({"sectionType": current_type, "startLine": section_start, "endLine": i - 1})
                current_type = "notes"
                section_start = i
        elif ingredient_patterns.match(line) and current_type == "unknown":
            if section_start < i:
                sections.append({"sectionType": current_type, "startLine": section_start, "endLine": i - 1})
            current_type = "ingredients"
            section_start = i
        elif step_patterns.match(line) and current_type == "unknown":
            if section_start < i:
                sections.append({"sectionType": current_type, "startLine": section_start, "endLine": i - 1})
            current_type = "instructions"
            section_start = i

    if section_start < len(lines):
        sections.append({"sectionType": current_type, "startLine": section_start, "endLine": len(lines) - 1})

    return sections
