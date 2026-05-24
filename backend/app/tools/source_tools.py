"""T-018: classify_source — determine source subtype from URL domain or input type.
   T-022: extract_recipe_links — scan text for recipe URLs."""

import re
from urllib.parse import urlparse

from app.tools.base import ToolResult

YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
INSTAGRAM_DOMAINS = {"instagram.com", "www.instagram.com"}
TIKTOK_DOMAINS = {"tiktok.com", "www.tiktok.com", "vm.tiktok.com"}
FACEBOOK_DOMAINS = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"}

SOCIAL_DOMAINS = INSTAGRAM_DOMAINS | TIKTOK_DOMAINS | FACEBOOK_DOMAINS

# URL path patterns that indicate photo (non-video) posts
_FB_PHOTO_PATTERNS = re.compile(r"/(photo|photos|permalink\.php)", re.IGNORECASE)
_INSTA_PHOTO_PATTERN = re.compile(r"/(p|stories)/", re.IGNORECASE)
_INSTA_REEL_PATTERN = re.compile(r"/reel/", re.IGNORECASE)
CDN_PATTERNS = {"cdn", "static", "assets", "media", "img", "images"}
TRACKING_PATTERNS = {"bit.ly", "t.co", "goo.gl", "amzn.to", "tinyurl.com"}

URL_REGEX = re.compile(r"https?://[^\s<>\"')\]]+", re.IGNORECASE)


def classify_source(
    source_type: str,
    url: str | None = None,
    file_asset_ref: str | None = None,
    raw_text: str | None = None,
) -> ToolResult:
    if source_type == "url" and url:
        parsed = urlparse(url)
        domain = parsed.hostname or ""
        domain_lower = domain.lower()

        if domain_lower in YOUTUBE_DOMAINS:
            subtype = "youtube"
        elif domain_lower in INSTAGRAM_DOMAINS:
            subtype = _classify_instagram_post(parsed)
        elif domain_lower in TIKTOK_DOMAINS:
            subtype = "tiktok"
        elif domain_lower in FACEBOOK_DOMAINS:
            subtype = _classify_facebook_post(parsed)
        else:
            subtype = "recipe_webpage"

        return ToolResult(
            success=True,
            message=f"Classified URL as {subtype}",
            signals={
                "sourceSubtype": subtype,
                "domain": domain_lower,
                "suggestedTools": _suggested_tools_for(subtype),
            },
        )

    if source_type == "image":
        return ToolResult(
            success=True,
            message="Classified as image source",
            signals={
                "sourceSubtype": "image",
                "suggestedTools": ["ocr_extract", "assess_parseability", "llm_structured_extract"],
            },
        )

    if source_type == "text":
        text_structure = _detect_text_structure(raw_text) if raw_text else "ambiguous"
        return ToolResult(
            success=True,
            message=f"Classified as text source (structure: {text_structure})",
            signals={
                "sourceSubtype": "text",
                "textStructure": text_structure,
                "suggestedTools": ["clean_text", "analyze_text_structure", "llm_structured_extract"],
            },
        )

    return ToolResult(success=False, message=f"Unknown source type: {source_type}")


def extract_recipe_links(text: str) -> ToolResult:
    raw_urls = URL_REGEX.findall(text)
    if not raw_urls:
        return ToolResult(success=True, message="No URLs found", signals={"urls": []})

    recipe_urls: list[dict] = []
    for raw in raw_urls:
        url = raw.rstrip(".,;:!?)")
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()

        if any(p in domain for p in CDN_PATTERNS):
            continue
        if domain in TRACKING_PATTERNS:
            continue
        if any(url.lower().endswith(ext) for ext in (".jpg", ".png", ".gif", ".mp4", ".css", ".js")):
            continue

        confidence = "medium"
        source = "page_body"
        if any(kw in url.lower() for kw in ("recipe", "cook", "food", "dish")):
            confidence = "high"

        recipe_urls.append({"url": url, "source": source, "confidence": confidence})

    return ToolResult(
        success=True,
        message=f"Found {len(recipe_urls)} potential recipe URLs",
        artifacts=[{
            "artifactType": "linked_recipe_urls",
            "payload": {"urls": recipe_urls},
        }] if recipe_urls else [],
        signals={"urls": recipe_urls},
    )


_STRUCTURED_HEADERS = re.compile(
    r"(?:^|\n)\s*(?:ingredients?|directions?|instructions?|steps?|method|preparation)\s*[:\-]",
    re.IGNORECASE,
)
_NUMBERED_STEPS = re.compile(r"(?:^|\n)\s*\d+[\.\)]\s+\S", re.MULTILINE)
_BULLET_LIST = re.compile(r"(?:^|\n)\s*[-•·*]\s+\S", re.MULTILINE)


def _detect_text_structure(text: str) -> str:
    """Classify pasted text as structured_recipe, freeform_notes, or ambiguous."""
    if not text or len(text.strip()) < 20:
        return "ambiguous"

    header_hits = len(_STRUCTURED_HEADERS.findall(text))
    numbered_hits = len(_NUMBERED_STEPS.findall(text))
    bullet_hits = len(_BULLET_LIST.findall(text))

    structural_score = header_hits * 2 + min(numbered_hits, 5) + min(bullet_hits, 5)

    if structural_score >= 4:
        return "structured_recipe"
    if structural_score <= 1 and header_hits == 0:
        return "freeform_notes"
    return "ambiguous"


def _classify_instagram_post(parsed) -> str:
    """Instagram /reel/ → video; /p/ or /stories/ → photo; default → video."""
    path = parsed.path or ""
    if _INSTA_REEL_PATTERN.search(path):
        return "instagram"
    if _INSTA_PHOTO_PATTERN.search(path):
        return "instagram_photo"
    return "instagram"


def _classify_facebook_post(parsed) -> str:
    """Facebook /photo, /photos, /permalink → photo; fb.watch → video; default → photo."""
    path = parsed.path or ""
    domain = (parsed.hostname or "").lower()
    if domain == "fb.watch":
        return "facebook"
    if _FB_PHOTO_PATTERNS.search(path):
        return "facebook_photo"
    if "/videos/" in path or "/watch" in path or "/reel" in path:
        return "facebook"
    return "facebook_photo"


def _suggested_tools_for(subtype: str) -> list[str]:
    if subtype == "recipe_webpage":
        return ["httpx_fetch", "check_schema_markup", "extract_page_text", "llm_structured_extract"]
    if subtype == "youtube":
        return ["youtube_api_fetch", "extract_recipe_links", "httpx_fetch", "youtube_transcript_fetch"]
    if subtype in ("instagram", "tiktok", "facebook"):
        return ["yt_dlp_fetch_metadata", "extract_recipe_links", "fetch_creator_profile"]
    if subtype in ("instagram_photo", "facebook_photo"):
        return ["fetch_social_post_page", "llm_structured_extract", "multimodal_llm_extract"]
    return ["httpx_fetch"]
