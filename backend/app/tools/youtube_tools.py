"""T-034: YouTube ingestion tools — API metadata, transcript fetch, and URL parsing."""

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.circuit_breaker import youtube_breaker
from app.core.config import get_settings
from app.tools.base import ToolResult

log = structlog.get_logger()

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_YOUTUBE_SHORT_DOMAINS = {"youtu.be"}
_YOUTUBE_LONG_DOMAINS = {"youtube.com", "www.youtube.com", "m.youtube.com"}


def extract_video_id(url: str) -> str | None:
    """Extract the 11-char video ID from various YouTube URL formats."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host in _YOUTUBE_SHORT_DOMAINS:
            vid = parsed.path.lstrip("/").split("/")[0]
            return vid if _VIDEO_ID_RE.match(vid) else None

        if host in _YOUTUBE_LONG_DOMAINS:
            path = parsed.path.lower()
            if path.startswith("/shorts/"):
                vid = parsed.path.split("/shorts/")[1].split("/")[0].split("?")[0]
                return vid if _VIDEO_ID_RE.match(vid) else None
            if path.startswith("/embed/"):
                vid = parsed.path.split("/embed/")[1].split("/")[0].split("?")[0]
                return vid if _VIDEO_ID_RE.match(vid) else None
            if path.startswith("/v/"):
                vid = parsed.path.split("/v/")[1].split("/")[0].split("?")[0]
                return vid if _VIDEO_ID_RE.match(vid) else None

            qs = parse_qs(parsed.query)
            v_param = qs.get("v", [None])[0]
            if v_param and _VIDEO_ID_RE.match(v_param):
                return v_param

        return None
    except Exception:
        return None


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def youtube_api_fetch(video_id: str) -> ToolResult:
    """Fetch video metadata and top comment via YouTube Data API v3."""
    settings = get_settings()
    if not settings.youtube_api_key:
        return ToolResult(
            success=False,
            message="YOUTUBE_API_KEY not configured",
        )

    if youtube_breaker.is_open():
        return ToolResult(success=False, message="YouTube API circuit breaker is open")

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey=settings.youtube_api_key)

        video_resp = (
            youtube.videos()
            .list(part="snippet", id=video_id)
            .execute()
        )

        items = video_resp.get("items", [])
        if not items:
            youtube_breaker.record_success()
            return ToolResult(success=False, message=f"Video {video_id} not found")

        snippet = items[0]["snippet"]
        title = snippet.get("title", "")
        description = snippet.get("description", "")
        channel_title = snippet.get("channelTitle", "")
        thumbnails = snippet.get("thumbnails", {})

        thumbnail_url = None
        for res in ("maxres", "high", "medium", "default"):
            if res in thumbnails:
                thumbnail_url = thumbnails[res].get("url")
                break

        first_comment: str | None = None
        try:
            comments_resp = (
                youtube.commentThreads()
                .list(part="snippet", videoId=video_id, maxResults=1, order="relevance")
                .execute()
            )
            comment_items = comments_resp.get("items", [])
            if comment_items:
                first_comment = (
                    comment_items[0]["snippet"]["topLevelComment"]["snippet"]
                    .get("textDisplay", "")
                )
        except Exception as exc:
            log.warning("youtube_comments_fetch_failed", video_id=video_id, error=str(exc))

        youtube_breaker.record_success()

        video_metadata: dict[str, Any] = {
            "videoId": video_id,
            "title": title,
            "description": description,
            "channelTitle": channel_title,
            "thumbnailUrl": thumbnail_url,
        }
        if first_comment:
            video_metadata["firstComment"] = first_comment

        return ToolResult(
            success=True,
            message=f"Fetched YouTube metadata for '{title}'",
            artifacts=[{
                "artifactType": "video_metadata",
                "payload": video_metadata,
            }],
            signals={
                "video_metadata": video_metadata,
                "description": description,
                "firstComment": first_comment,
                "thumbnailUrl": thumbnail_url,
            },
        )

    except Exception as exc:
        youtube_breaker.record_failure()
        log.error("youtube_api_error", video_id=video_id, error=str(exc))
        return ToolResult(success=False, message=f"YouTube API error: {exc}")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10), reraise=True)
async def youtube_transcript_fetch(video_id: str) -> ToolResult:
    """Fetch transcript with timestamps via youtube-transcript-api."""
    if youtube_breaker.is_open():
        return ToolResult(success=False, message="YouTube circuit breaker is open")

    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)

        segments: list[dict[str, Any]] = []
        full_text_parts: list[str] = []

        for entry in transcript:
            segments.append({
                "start": entry.start,
                "duration": entry.duration,
                "text": entry.text,
            })
            full_text_parts.append(entry.text)

        full_text = " ".join(full_text_parts)

        youtube_breaker.record_success()

        return ToolResult(
            success=True,
            message=f"Fetched transcript ({len(segments)} segments, {len(full_text)} chars)",
            artifacts=[{
                "artifactType": "video_transcript",
                "payload": {
                    "videoId": video_id,
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
        youtube_breaker.record_failure()
        log.warning("youtube_transcript_failed", video_id=video_id, error=str(exc))
        return ToolResult(success=False, message=f"Transcript unavailable: {exc}")
