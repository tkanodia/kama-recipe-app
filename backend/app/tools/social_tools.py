"""T-035: Social media ingestion tools — yt-dlp metadata, creator profiles, bio link expansion."""

import re
from typing import Any
from urllib.parse import urlparse

import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import social_breaker
from app.tools.base import ToolResult

log = structlog.get_logger()

USER_AGENT = "Mozilla/5.0 (compatible; KamaBot/1.0; +https://kama.app)"

LINKTREE_DOMAINS = {
    "linktr.ee", "beacons.ai", "linkin.bio", "bio.link", "lnk.bio",
    "campsite.bio", "tap.bio", "solo.to", "carrd.co", "stan.store",
}

RECIPE_LINK_KEYWORDS = {"recipe", "cook", "food", "blog", "kitchen", "bake", "meal", "dish"}


async def fetch_social_post_page(url: str) -> ToolResult:
    """Fetch a social media post page via HTTP and extract OG/meta tags for caption text and images.

    Works for photo posts (Facebook, Instagram) where yt-dlp is not appropriate.
    """
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        html = resp.text
        caption = _extract_og_caption(html)
        image_url = _extract_og_image(html)
        page_title = ""
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            page_title = title_match.group(1).strip()

        all_images = _extract_all_meta_images(html)

        # Fallback: extract images from Facebook/Instagram CDN URLs embedded in HTML
        if not image_url:
            embedded = _extract_embedded_content_images(html)
            if embedded:
                image_url = embedded[0]
                all_images = list(dict.fromkeys(embedded + all_images))

        return ToolResult(
            success=True,
            message=f"Fetched social page: caption={len(caption)} chars, images={len(all_images)}",
            signals={
                "caption": caption,
                "image_url": image_url,
                "all_image_urls": all_images,
                "page_title": page_title,
                "html": html,
            },
        )
    except Exception as exc:
        log.warning("fetch_social_post_page_failed", url=url, error=str(exc))
        return ToolResult(success=False, message=f"Could not fetch social post page: {exc}")


def _extract_og_caption(html: str) -> str:
    """Extract post description/caption from OG and meta tags."""
    for pattern in [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+name=["\']twitter:description["\'][^>]+content=["\']([^"\']*)["\']',
    ]:
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match and len(match.group(1).strip()) > 10:
            return match.group(1).strip()
    return ""


def _extract_og_image(html: str) -> str:
    """Extract the primary image from OG tags."""
    for pattern in [
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
    ]:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_all_meta_images(html: str) -> list[str]:
    """Extract all image URLs from OG and meta tags."""
    images: list[str] = []
    seen: set[str] = set()
    for pattern in [
        r'<meta[^>]+property=["\']og:image(?::url)?["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::url)?["\']',
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
        for match in re.finditer(pattern, html, re.IGNORECASE):
            img = match.group(1).strip()
            if img and img not in seen:
                seen.add(img)
                images.append(img)
    return images


# Facebook/Instagram embed full-resolution photos as scontent CDN URLs in the HTML.
# These are typically the post's actual photo, even when OG tags are stripped by auth walls.
# The URLs include auth query parameters that are required for access — we must capture the
# full URL including ?_nc_cat=...&ccb=... etc.
_SCONTENT_PATTERN = re.compile(
    r'(https?://scontent[a-z0-9\-]*\.(?:xx\.)?fbcdn\.net/v/[^\s"<>\\]*\.(?:jpg|jpeg|png|webp)[^\s"<>\\]*)',
    re.IGNORECASE,
)
_CDNINSTAGRAM_PATTERN = re.compile(
    r'(https?://(?:scontent|instagram)[a-z0-9\-]*\.cdninstagram\.com/[^\s"<>\\]*\.(?:jpg|jpeg|png|webp)[^\s"<>\\]*)',
    re.IGNORECASE,
)
_SMALL_ASSET_MARKERS = {"emoji", "/images/", "static.xx", "30808-1/"}
_CONTENT_PHOTO_MARKERS = {"30808-6/", "30808-0/", "/p/", "_n.jpg", "_n.png"}


def _extract_embedded_content_images(html: str) -> list[str]:
    """Extract content photos from Facebook/Instagram HTML (CDN URLs embedded in the page).

    Captures full URLs including auth query parameters required by Facebook CDN.
    Filters out UI assets like emoji PNGs and profile thumbnails, prioritizing
    full-size post photos.
    """
    candidates: list[str] = []
    seen_base: set[str] = set()

    for pattern in [_SCONTENT_PATTERN, _CDNINSTAGRAM_PATTERN]:
        for match in pattern.finditer(html):
            raw = match.group(1)
            url = raw.replace("\\/", "/").replace("\\u0025", "%").replace("&amp;", "&")
            # Deduplicate by base path (before query params)
            base = url.split("?")[0]
            if base in seen_base:
                continue
            seen_base.add(base)

            lower = base.lower()
            if any(marker in lower for marker in _SMALL_ASSET_MARKERS):
                continue
            candidates.append(url)

    def _score(u: str) -> int:
        l = u.lower()
        return sum(2 for m in _CONTENT_PHOTO_MARKERS if m in l)

    candidates.sort(key=_score, reverse=True)
    return candidates[:5]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def yt_dlp_fetch_metadata(url: str) -> ToolResult:
    """Fetch social post metadata (caption, creator, thumbnail) via yt-dlp."""
    if social_breaker.is_open():
        return ToolResult(success=False, message="Social media circuit breaker is open")

    try:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                social_breaker.record_failure()
                return ToolResult(success=False, message="yt-dlp returned no info")

        caption = info.get("description") or info.get("title") or ""
        creator = info.get("uploader") or info.get("channel") or ""
        creator_url = info.get("uploader_url") or info.get("channel_url") or ""
        thumbnail = info.get("thumbnail") or ""
        duration = info.get("duration")
        platform = info.get("extractor_key", "unknown").lower()

        social_breaker.record_success()

        video_metadata: dict[str, Any] = {
            "platform": platform,
            "caption": caption,
            "creator": creator,
            "creatorUrl": creator_url,
            "thumbnailUrl": thumbnail,
            "duration": duration,
            "originalUrl": url,
        }

        return ToolResult(
            success=True,
            message=f"Fetched {platform} metadata for post by '{creator}'",
            artifacts=[{
                "artifactType": "video_metadata",
                "payload": video_metadata,
            }],
            signals={
                "social_caption": caption,
                "video_metadata": video_metadata,
                "creator_url": creator_url,
                "platform": platform,
            },
        )

    except Exception as exc:
        social_breaker.record_failure()
        log.error("yt_dlp_metadata_error", url=url, error=str(exc))
        return ToolResult(success=False, message=f"yt-dlp metadata fetch failed: {exc}")


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=10), reraise=True)
async def fetch_creator_profile(url: str) -> ToolResult:
    """Fetch a creator's profile page and extract bio text and links."""
    if not url:
        return ToolResult(success=False, message="No creator profile URL provided")

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

        html = resp.text
        bio_text = _extract_bio_text(html)
        bio_urls = _extract_bio_urls(html, str(resp.url))

        return ToolResult(
            success=True,
            message=f"Fetched creator profile ({len(bio_urls)} bio links found)",
            signals={
                "bio_text": bio_text,
                "bio_urls": bio_urls,
                "profile_url": str(resp.url),
            },
        )

    except Exception as exc:
        log.warning("creator_profile_fetch_failed", url=url, error=str(exc))
        return ToolResult(success=False, message=f"Could not fetch creator profile: {exc}")


async def expand_bio_links(bio_urls: list[str]) -> ToolResult:
    """Follow linktree/beacons/redirect URLs and categorize destinations."""
    if not bio_urls:
        return ToolResult(success=True, message="No bio links to expand", signals={"links": []})

    categorized: list[dict[str, str]] = []
    best_recipe_link: str | None = None
    best_recipe_score = 0

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=10.0,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for link_url in bio_urls[:10]:
            try:
                resp = await client.head(link_url)
                resolved = str(resp.url)
            except Exception:
                resolved = link_url

            category = _categorize_link(resolved)
            entry = {"url": resolved, "original": link_url, "category": category}
            categorized.append(entry)

            score = _recipe_link_score(resolved)
            if score > best_recipe_score:
                best_recipe_score = score
                best_recipe_link = resolved

    return ToolResult(
        success=True,
        message=f"Expanded {len(categorized)} bio links",
        signals={
            "links": categorized,
            "best_recipe_link": best_recipe_link,
        },
    )


@retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5), reraise=True)
async def discover_recipe_on_site(site_url: str, keywords: list[str]) -> ToolResult:
    """Search a creator's website for a recipe matching the given keywords.

    Tries multiple strategies: site search endpoint, homepage link scan,
    and common WordPress/recipe blog search patterns.
    """
    if not site_url:
        return ToolResult(success=False, message="No site URL provided")

    from app.tools.extraction_tools import check_schema_markup

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:

            # Strategy 1: Try the site's search endpoint with keywords
            search_query = "+".join(keywords[:5])
            search_urls = [
                f"{site_url.rstrip('/')}/?s={search_query}",
                f"{site_url.rstrip('/')}/search?q={search_query}",
            ]
            for search_url in search_urls:
                try:
                    search_resp = await client.get(search_url)
                    if search_resp.status_code == 200:
                        search_html = search_resp.text
                        recipe_links = _find_recipe_page_links(search_html, str(search_resp.url), keywords)
                        for recipe_url in recipe_links[:3]:
                            try:
                                recipe_resp = await client.get(recipe_url)
                                recipe_html = recipe_resp.text
                                recipe_schema = check_schema_markup(recipe_html)
                                if recipe_schema.success and recipe_schema.signals.get("recipeSchema"):
                                    log.info("recipe_discovered_via_search", url=recipe_url, search=search_url)
                                    return ToolResult(
                                        success=True,
                                        message=f"Found recipe at {recipe_url}",
                                        signals={"found_url": recipe_url, "has_schema": True, "html": recipe_html},
                                    )
                            except Exception:
                                continue
                except Exception:
                    continue

            # Strategy 2: Check homepage for recipe schema or matching links
            resp = await client.get(site_url)
            resp.raise_for_status()
            html = resp.text

            schema_result = check_schema_markup(html)
            if schema_result.success and schema_result.signals.get("recipeSchema"):
                return ToolResult(
                    success=True,
                    message="Found recipe schema on creator's site",
                    signals={"found_url": str(resp.url), "has_schema": True, "html": html},
                )

            recipe_links = _find_recipe_page_links(html, str(resp.url), keywords)
            for recipe_url in recipe_links[:3]:
                try:
                    recipe_resp = await client.get(recipe_url)
                    recipe_html = recipe_resp.text
                    recipe_schema = check_schema_markup(recipe_html)
                    if recipe_schema.success and recipe_schema.signals.get("recipeSchema"):
                        return ToolResult(
                            success=True,
                            message=f"Found recipe at {recipe_url}",
                            signals={"found_url": recipe_url, "has_schema": True, "html": recipe_html},
                        )
                except Exception as exc:
                    log.debug("recipe_link_fetch_failed", url=recipe_url, error=str(exc))
                    continue

        return ToolResult(
            success=False,
            message="No matching recipe found on creator's site",
        )

    except Exception as exc:
        log.warning("discover_recipe_failed", site_url=site_url, error=str(exc))
        return ToolResult(success=False, message=f"Site search failed: {exc}")


def _extract_bio_text(html: str) -> str:
    """Pull out meta description or og:description as a proxy for bio."""
    for pattern in [
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
    ]:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_bio_urls(html: str, page_url: str) -> list[str]:
    """Find external links in a profile page (likely bio links)."""
    page_domain = urlparse(page_url).hostname or ""
    href_pattern = re.compile(r'href=["\']?(https?://[^\s"\'<>]+)', re.IGNORECASE)
    found = set()

    for match in href_pattern.finditer(html):
        href = match.group(1).rstrip(".,;:!?)")
        href_domain = (urlparse(href).hostname or "").lower()
        if href_domain and href_domain != page_domain.lower():
            found.add(href)

    return list(found)[:20]


def _categorize_link(url: str) -> str:
    """Classify a resolved URL into a category."""
    lower = url.lower()
    parsed = urlparse(lower)
    domain = parsed.hostname or ""

    if domain in LINKTREE_DOMAINS:
        return "link_aggregator"
    if any(kw in lower for kw in ("recipe", "cook", "food", "blog", "kitchen")):
        return "recipe_blog"
    if any(kw in lower for kw in ("shop", "store", "merch", "buy")):
        return "shop"
    if any(d in domain for d in ("instagram", "tiktok", "youtube", "twitter", "facebook")):
        return "social_profile"
    if parsed.path in ("", "/", "/index.html"):
        return "website_home"

    return "other"


def _recipe_link_score(url: str) -> int:
    """Score a URL for recipe relevance — higher is better."""
    lower = url.lower()
    score = 0
    for kw in RECIPE_LINK_KEYWORDS:
        if kw in lower:
            score += 2
    if "blog" in lower:
        score += 1
    parsed = urlparse(lower)
    if parsed.path not in ("", "/"):
        score += 1
    return score


def _find_recipe_page_links(html: str, base_url: str, keywords: list[str]) -> list[str]:
    """Find links on a page that might lead to the target recipe."""
    href_pattern = re.compile(r'href=["\']?([^\s"\'<>]+)', re.IGNORECASE)
    candidates: list[tuple[int, str]] = []
    parsed_base = urlparse(base_url)
    base_domain = (parsed_base.hostname or "").lower()

    for match in href_pattern.finditer(html):
        raw = match.group(1).rstrip(".,;:!?)")
        if raw.startswith("#") or raw.startswith("javascript:") or raw.startswith("mailto:"):
            continue

        parsed = urlparse(raw)
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            continue

        if parsed.hostname:
            if parsed.hostname.lower() != base_domain:
                continue
            href = raw
        else:
            href = f"{parsed_base.scheme}://{parsed_base.netloc}{raw if raw.startswith('/') else '/' + raw}"

        lower = href.lower()
        score = 0
        for kw in keywords:
            if kw.lower() in lower:
                score += 3
        if "recipe" in lower:
            score += 2

        if score > 0:
            candidates.append((score, href))

    candidates.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for _, url in candidates:
        if url not in seen:
            seen.add(url)
            result.append(url)
            if len(result) >= 5:
                break
    return result
