"""Tests for social media URL classification."""

import pytest

from app.tools.source_tools import classify_source


class TestClassifySourceSocial:
    """Verify classify_source returns correct subtypes for social media URLs."""

    @pytest.mark.parametrize("url,expected", [
        ("https://www.instagram.com/p/ABC123/", "instagram_photo"),
        ("https://instagram.com/reel/XYZ789/", "instagram"),
        ("https://www.tiktok.com/@user/video/12345", "tiktok"),
        ("https://vm.tiktok.com/ZMdABC123/", "tiktok"),
        ("https://www.facebook.com/watch/?v=12345", "facebook"),
        ("https://m.facebook.com/story.php?id=123", "facebook_photo"),
        ("https://fb.watch/abc123/", "facebook"),
    ])
    def test_social_urls_classified(self, url, expected):
        result = classify_source("url", url=url)
        assert result.success
        assert result.signals["sourceSubtype"] == expected

    def test_social_urls_suggest_correct_tools(self):
        result = classify_source("url", url="https://www.instagram.com/p/ABC123/")
        assert result.success
        tools = result.signals.get("suggestedTools", [])
        assert "fetch_social_post_page" in tools

    def test_youtube_not_classified_as_social(self):
        result = classify_source("url", url="https://www.youtube.com/watch?v=abc123")
        assert result.success
        assert result.signals["sourceSubtype"] == "youtube"
        assert result.signals["sourceSubtype"] not in ("instagram", "tiktok", "facebook")
