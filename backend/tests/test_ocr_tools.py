"""Unit tests for OCR tools — mocked Google Cloud Vision, no external services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.ocr_tools import (
    _assess_ocr_quality,
    create_image_preview,
    multimodal_llm_extract,
    ocr_extract,
)


class TestAssessOcrQuality:
    def test_acceptable(self):
        assert _assess_ocr_quality("Some long enough text for testing", 0.85) == "acceptable"

    def test_low_confidence(self):
        assert _assess_ocr_quality("Some text here to test", 0.50) == "low"

    def test_very_low_confidence(self):
        assert _assess_ocr_quality("Some text content here", 0.30) == "very_low"

    def test_empty_text(self):
        assert _assess_ocr_quality("", 0.95) == "unusable"

    def test_short_text(self):
        assert _assess_ocr_quality("hi", 0.95) == "unusable"


class TestCreateImagePreview:
    def test_url_preview(self):
        result = create_image_preview(
            "https://s3.amazonaws.com/bucket/recipe.jpg",
            file_name="recipe.jpg",
            file_size_bytes=204800,
        )
        assert result.success
        assert len(result.artifacts) == 1
        artifact = result.artifacts[0]
        assert artifact["artifactType"] == "source_preview"
        assert artifact["payload"]["previewType"] == "uploaded_image"
        assert artifact["payload"]["fileName"] == "recipe.jpg"
        assert artifact["payload"]["imageUrl"] == "https://s3.amazonaws.com/bucket/recipe.jpg"
        assert artifact["payload"]["fileSizeBytes"] == 204800

    def test_local_path_preview(self):
        result = create_image_preview("/tmp/recipe.png")
        assert result.success
        payload = result.artifacts[0]["payload"]
        assert payload["imageUrl"] is None
        assert payload["fileName"] == "recipe.png"


def _build_mock_vision():
    """Set up mock Vision API objects for a successful OCR call."""
    mock_text_annotation = MagicMock()
    mock_text_annotation.description = "Chocolate Cake Recipe\nIngredients:\n2 cups flour"
    mock_text_annotation.bounding_poly.vertices = [
        MagicMock(x=0, y=0), MagicMock(x=100, y=0),
        MagicMock(x=100, y=50), MagicMock(x=0, y=50),
    ]

    mock_word = MagicMock()
    mock_word.description = "Chocolate"
    mock_word.bounding_poly.vertices = [
        MagicMock(x=0, y=0), MagicMock(x=50, y=0),
        MagicMock(x=50, y=20), MagicMock(x=0, y=20),
    ]

    mock_text_response = MagicMock()
    mock_text_response.text_annotations = [mock_text_annotation, mock_word]
    mock_text_response.error.message = ""

    mock_page = MagicMock()
    mock_page.confidence = 0.92
    mock_page.blocks = []

    mock_doc_response = MagicMock()
    mock_doc_response.full_text_annotation.pages = [mock_page]
    mock_doc_response.full_text_annotation.text = "Chocolate Cake Recipe\nIngredients:\n2 cups flour"

    return mock_text_response, mock_doc_response


class TestOcrExtract:
    @pytest.mark.asyncio
    async def test_circuit_breaker_open(self):
        from app.core.circuit_breaker import ocr_breaker
        ocr_breaker.reset()
        ocr_breaker._failure_count = 10
        ocr_breaker._state = ocr_breaker._state.__class__("open")

        result = await ocr_extract.__wrapped__("https://example.com/img.jpg")
        assert not result.success
        assert "circuit breaker" in result.message.lower()

        ocr_breaker.reset()

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        from app.core.circuit_breaker import ocr_breaker
        ocr_breaker.reset()

        mock_vision = MagicMock()
        mock_vision.ImageAnnotatorClient.return_value = MagicMock()
        mock_vision.Image.return_value = MagicMock()

        with patch("app.tools.ocr_tools.vision", mock_vision):
            result = await ocr_extract.__wrapped__("/nonexistent/path/image.jpg")

        assert not result.success
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        from app.core.circuit_breaker import ocr_breaker
        ocr_breaker.reset()

        mock_text_response, mock_doc_response = _build_mock_vision()

        food_label = MagicMock()
        food_label.description = "Food"
        food_label.score = 0.95
        mock_label_response = MagicMock()
        mock_label_response.label_annotations = [food_label]

        mock_client = MagicMock()
        mock_client.text_detection.return_value = mock_text_response
        mock_client.document_text_detection.return_value = mock_doc_response
        mock_client.label_detection.return_value = mock_label_response

        mock_vision = MagicMock()
        mock_vision.ImageAnnotatorClient.return_value = mock_client
        mock_vision.Image.return_value = MagicMock()
        mock_vision.Block.BlockType = MagicMock()

        with patch("app.tools.ocr_tools.vision", mock_vision), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"fake image bytes"):
            result = await ocr_extract.__wrapped__("/tmp/recipe.jpg")

        assert result.success
        assert result.signals["extractedText"] == "Chocolate Cake Recipe\nIngredients:\n2 cups flour"
        assert result.signals["overallConfidence"] == 0.92
        assert result.signals["handwritingDetected"] is False
        assert len(result.artifacts) == 2
        assert result.artifacts[0]["artifactType"] == "ocr_text"
        assert result.artifacts[1]["artifactType"] == "image_analysis"

    @pytest.mark.asyncio
    async def test_handwriting_detection(self):
        from app.core.circuit_breaker import ocr_breaker
        ocr_breaker.reset()

        mock_text_annotation = MagicMock()
        mock_text_annotation.description = "Some handwritten text here for testing"
        mock_text_annotation.bounding_poly.vertices = [
            MagicMock(x=0, y=0), MagicMock(x=100, y=0),
            MagicMock(x=100, y=50), MagicMock(x=0, y=50),
        ]

        mock_text_response = MagicMock()
        mock_text_response.text_annotations = [mock_text_annotation]
        mock_text_response.error.message = ""

        mock_page = MagicMock()
        mock_page.confidence = 0.70
        mock_page.blocks = []
        mock_doc_response = MagicMock()
        mock_doc_response.full_text_annotation.pages = [mock_page]
        mock_doc_response.full_text_annotation.text = "Some handwritten text here for testing"

        handwriting_label = MagicMock()
        handwriting_label.description = "Handwriting"
        mock_label_response = MagicMock()
        mock_label_response.label_annotations = [handwriting_label]

        mock_client = MagicMock()
        mock_client.text_detection.return_value = mock_text_response
        mock_client.document_text_detection.return_value = mock_doc_response
        mock_client.label_detection.return_value = mock_label_response

        mock_vision = MagicMock()
        mock_vision.ImageAnnotatorClient.return_value = mock_client
        mock_vision.Image.return_value = MagicMock()
        mock_vision.Block.BlockType = MagicMock()

        with patch("app.tools.ocr_tools.vision", mock_vision), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"fake"):
            result = await ocr_extract.__wrapped__("/tmp/handwritten.jpg")

        assert result.success
        assert result.signals["handwritingDetected"] is True


class TestMultimodalLlmExtract:
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        mock_response = MagicMock()
        mock_response.text = '{"title": "Pasta", "ingredients": [{"text": "spaghetti"}], "steps": [{"order": 1, "text": "Boil"}]}'

        with patch("app.tools.ocr_tools.llm_chat", new_callable=AsyncMock) as mock_llm, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"fake image data"):
            mock_llm.return_value = mock_response

            result = await multimodal_llm_extract("/tmp/recipe.jpg", model_override="gpt-4o")

        assert result.success
        assert result.candidate_update["title"] == "Pasta"
        assert result.signals["extractionMethod"] == "multimodal_llm_fallback"

    @pytest.mark.asyncio
    async def test_no_recipe_found(self):
        mock_response = MagicMock()
        mock_response.text = '{"error": "no_recipe_found"}'

        with patch("app.tools.ocr_tools.llm_chat", new_callable=AsyncMock) as mock_llm, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"fake"):
            mock_llm.return_value = mock_response

            result = await multimodal_llm_extract("/tmp/cat.jpg")

        assert not result.success
        assert result.signals.get("llmSaysNoRecipe") is True

    @pytest.mark.asyncio
    async def test_file_not_found(self):
        result = await multimodal_llm_extract("/nonexistent/img.jpg")
        assert not result.success
        assert "not found" in result.message.lower()

    @pytest.mark.asyncio
    async def test_with_ocr_text_hint(self):
        mock_response = MagicMock()
        mock_response.text = '{"title": "Cake", "ingredients": [], "steps": []}'

        with patch("app.tools.ocr_tools.llm_chat", new_callable=AsyncMock) as mock_llm, \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.read_bytes", return_value=b"fake"):
            mock_llm.return_value = mock_response

            result = await multimodal_llm_extract("/tmp/recipe.jpg", ocr_text="partial cake recipe text")

        assert result.success
        call_args = mock_llm.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
        content = messages[0]["content"]
        text_part = next(p for p in content if p["type"] == "text")
        assert "partial cake recipe text" in text_part["text"]
