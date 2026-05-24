"""Tests for YouTube tools — extract_video_id and classify_source integration."""

import pytest

from app.tools.youtube_tools import extract_video_id
from app.tools.source_tools import classify_source


class TestExtractVideoId:
    """Verify extract_video_id handles all known YouTube URL formats."""

    def test_standard_watch_url(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_short_url(self):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_shorts_url(self):
        url = "https://www.youtube.com/shorts/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_embed_url(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_v_url(self):
        url = "https://www.youtube.com/v/dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_mobile_url(self):
        url = "https://m.youtube.com/watch?v=dQw4w9WgXcQ"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_with_extra_params(self):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PLx0sYb&index=1"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_with_timestamp(self):
        url = "https://youtu.be/dQw4w9WgXcQ?t=42"
        assert extract_video_id(url) == "dQw4w9WgXcQ"

    def test_invalid_url_returns_none(self):
        assert extract_video_id("https://example.com") is None

    def test_non_youtube_returns_none(self):
        assert extract_video_id("https://www.instagram.com/p/abc123/") is None

    def test_malformed_url_returns_none(self):
        assert extract_video_id("not a url at all") is None

    def test_empty_string_returns_none(self):
        assert extract_video_id("") is None

    def test_youtube_url_without_v_param(self):
        url = "https://www.youtube.com/results?search_query=pasta"
        assert extract_video_id(url) is None


class TestClassifySourceYouTube:
    """Verify classify_source returns 'youtube' for YouTube URLs."""

    @pytest.mark.parametrize("url", [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=abc12345678",
        "https://youtube.com/shorts/dQw4w9WgXcQ",
    ])
    def test_youtube_urls_classified(self, url):
        result = classify_source("url", url=url)
        assert result.success
        assert result.signals["sourceSubtype"] == "youtube"

    def test_non_youtube_url(self):
        result = classify_source("url", url="https://www.allrecipes.com/recipe/12345")
        assert result.success
        assert result.signals["sourceSubtype"] == "recipe_webpage"
