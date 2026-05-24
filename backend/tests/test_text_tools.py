"""Unit tests for text ingestion tools — no database, no external services."""

from app.tools.text_tools import analyze_text_structure, clean_text, create_text_preview


class TestCleanText:
    def test_basic_cleaning(self):
        raw = "  Hello   world  \n\n\n\n\nLine 2  "
        result = clean_text(raw)
        assert result.success
        cleaned = result.signals["cleanedText"]
        assert "Hello" in cleaned
        assert result.signals["originalLength"] == len(raw)
        assert result.signals["cleanedLength"] <= len(raw)

    def test_unicode_normalization(self):
        raw = "Preheat\u200b the \ufeffoven"
        result = clean_text(raw)
        assert result.success
        assert "\u200b" not in result.signals["cleanedText"]
        assert "\ufeff" not in result.signals["cleanedText"]

    def test_multi_whitespace_collapse(self):
        raw = "Mix      flour    and     sugar"
        result = clean_text(raw)
        assert result.success
        cleaned = result.signals["cleanedText"]
        assert "      " not in cleaned

    def test_multi_newline_collapse(self):
        raw = "Line 1\n\n\n\n\nLine 2"
        result = clean_text(raw)
        assert result.success
        cleaned = result.signals["cleanedText"]
        assert "\n\n\n" not in cleaned

    def test_empty_text_fails(self):
        result = clean_text("")
        assert not result.success

    def test_whitespace_only_fails(self):
        result = clean_text("   \n\n  ")
        assert not result.success

    def test_artifact_produced(self):
        result = clean_text("Some recipe text here.")
        assert result.success
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["artifactType"] == "cleaned_pasted_text"
        assert result.artifacts[0]["payload"]["text"] == "Some recipe text here."

    def test_noise_percentage(self):
        raw = "Hello\u200b\u200b\u200b\u200b world"
        result = clean_text(raw)
        assert result.success
        assert result.signals["noiseRemovedPct"] > 0

    def test_crlf_normalization(self):
        raw = "Line 1\r\nLine 2\rLine 3"
        result = clean_text(raw)
        assert result.success
        cleaned = result.signals["cleanedText"]
        assert "\r" not in cleaned
        assert "Line 1\nLine 2\nLine 3" == cleaned


class TestAnalyzeTextStructure:
    def test_structured_recipe_high(self):
        text = (
            "Chocolate Cake\n\n"
            "Ingredients:\n"
            "- 2 cups flour\n"
            "- 1 cup sugar\n"
            "- 3 eggs\n\n"
            "Instructions:\n"
            "1. Preheat oven to 350F\n"
            "2. Mix dry ingredients\n"
            "3. Add wet ingredients\n"
            "4. Bake for 30 minutes\n\n"
            "Servings: 12\n"
            "Prep time: 15 minutes\n"
        )
        result = analyze_text_structure(text)
        assert result.success
        assert result.signals["recipeLikelihood"] == "high"
        assert result.signals["isRecipeText"] is True

    def test_freeform_notes_low(self):
        text = "Had a great dinner last night, can't remember what I put in it though."
        result = analyze_text_structure(text)
        assert result.success
        assert result.signals["recipeLikelihood"] == "low"
        assert result.signals["isRecipeText"] is False

    def test_medium_likelihood(self):
        text = (
            "Quick pasta recipe\n"
            "Ingredients:\n"
            "You need spaghetti, garlic, and olive oil.\n"
            "1 cup pasta\n"
            "2 tbsp olive oil\n"
            "Cook the spaghetti in boiling water.\n"
            "Mix with garlic and oil.\n"
            "Servings: 2\n"
        )
        result = analyze_text_structure(text)
        assert result.success
        assert result.signals["recipeLikelihood"] in ("medium", "high")
        assert result.signals["isRecipeText"] is True

    def test_empty_text_fails(self):
        result = analyze_text_structure("")
        assert not result.success

    def test_section_detection(self):
        text = (
            "My Recipe\n\n"
            "Ingredients:\n"
            "- flour\n"
            "- sugar\n\n"
            "Instructions:\n"
            "1. Mix\n"
            "2. Bake\n"
        )
        result = analyze_text_structure(text)
        assert result.success
        sections = result.signals["detectedSections"]
        section_types = [s["sectionType"] for s in sections]
        assert "ingredients" in section_types
        assert "instructions" in section_types

    def test_artifact_produced(self):
        text = "Just some text with ingredients and steps to test."
        result = analyze_text_structure(text)
        assert result.success
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["artifactType"] == "text_structure_analysis"


class TestCreateTextPreview:
    def test_basic_preview(self):
        text = "This is a sample recipe for testing purposes."
        result = create_text_preview(text)
        assert result.success
        assert len(result.artifacts) == 1
        assert result.artifacts[0]["artifactType"] == "source_preview"
        assert result.artifacts[0]["payload"]["previewType"] == "pasted_text"

    def test_long_text_truncated(self):
        text = "A" * 500
        result = create_text_preview(text)
        assert result.success
        excerpt = result.artifacts[0]["payload"]["excerpt"]
        assert len(excerpt) <= 201  # 200 chars + ellipsis
        assert excerpt.endswith("…")

    def test_short_text_not_truncated(self):
        text = "Short text"
        result = create_text_preview(text)
        assert result.success
        excerpt = result.artifacts[0]["payload"]["excerpt"]
        assert excerpt == "Short text"
        assert "…" not in excerpt

    def test_empty_text_fails(self):
        result = create_text_preview("")
        assert not result.success

    def test_word_and_line_counts(self):
        text = "one two three\nfour five\nsix"
        result = create_text_preview(text)
        assert result.success
        payload = result.artifacts[0]["payload"]
        assert payload["wordCount"] == 6
        assert payload["lineCount"] == 3
