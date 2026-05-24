"""Tests for Sprint 3 gap tasks: review agent wiring, alias accumulation, media materialization."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.review_agent import run_review_agent


# --- Review agent wiring (T-028.9) ---

@pytest.mark.asyncio
async def test_review_agent_returns_updated_eligibility():
    """Review agent should re-assess eligibility based on its own heuristics."""
    result = await run_review_agent(
        title="Good Recipe",
        ingredients=[{"text": "flour"}, {"text": "sugar"}, {"text": "eggs"}],
        steps=[{"text": "Mix"}, {"text": "Bake"}, {"text": "Serve"}],
        description="A simple recipe",
        prep_time_minutes=10,
        cook_time_minutes=30,
        servings=4,
        extraction_method="schema_recipe_markup",
    )
    assert result["canonicalEligible"] is True
    assert result["reviewMode"] == "quick"
    assert "fieldConfidenceMap" in result
    assert result["fieldConfidenceMap"]["title"] == "high"


@pytest.mark.asyncio
async def test_review_agent_flags_missing_fields():
    """Review agent detects missing required fields and marks not canonical-eligible."""
    result = await run_review_agent(
        title="",
        ingredients=[],
        steps=[],
    )
    assert result["canonicalEligible"] is False
    assert result["reviewMode"] == "reconstruction"
    codes = {f["code"] for f in result["reviewFindings"]}
    assert "missing_title" in codes
    assert "missing_ingredients" in codes
    assert "missing_steps" in codes


@pytest.mark.asyncio
async def test_review_agent_standard_mode_with_warnings():
    """A few warnings without errors produce standard review mode."""
    result = await run_review_agent(
        title="Simple Salad",
        ingredients=[{"text": "lettuce"}, {"text": "tomato"}, {"text": "dressing"}],
        steps=[{"text": "Wash lettuce"}, {"text": "Toss together"}],
        description="A basic salad",
    )
    assert result["canonicalEligible"] is True
    assert result["reviewMode"] in ("quick", "standard")


# --- Alias accumulation (T-054) ---

@pytest.mark.asyncio
async def test_accumulate_aliases_adds_new_alias():
    """When ingredient text differs from canonical name, append as alias."""
    from app.api.candidates import _accumulate_ingredient_aliases

    mock_ingredient = MagicMock()
    mock_ingredient.name = "All-Purpose Flour"
    mock_ingredient.aliases = ["plain flour"]

    ingredients = [
        {"ingredientId": "ing_001", "text": "AP flour"},
        {"ingredientId": "ing_002", "text": "sugar"},
    ]

    mock_sugar = MagicMock()
    mock_sugar.name = "Sugar"
    mock_sugar.aliases = []

    db = AsyncMock()

    with patch("app.api.candidates.ingredient_repo") as mock_repo:
        async def fake_get(session, iid):
            return {"ing_001": mock_ingredient, "ing_002": mock_sugar}.get(iid)

        mock_repo.get_by_id = AsyncMock(side_effect=fake_get)
        mock_repo.update_aliases = AsyncMock()

        await _accumulate_ingredient_aliases(db, ingredients)

        # "AP flour" differs from "All-Purpose Flour" and isn't in aliases
        mock_repo.update_aliases.assert_any_call(db, "ing_001", ["AP flour"])
        # "sugar" matches "Sugar" (case-insensitive) so no alias added
        calls = [c for c in mock_repo.update_aliases.call_args_list if c[0][1] == "ing_002"]
        assert len(calls) == 0


@pytest.mark.asyncio
async def test_accumulate_aliases_skips_existing():
    """Don't add alias if text already matches name or existing alias."""
    from app.api.candidates import _accumulate_ingredient_aliases

    mock_ingredient = MagicMock()
    mock_ingredient.name = "Butter"
    mock_ingredient.aliases = ["unsalted butter"]

    ingredients = [
        {"ingredientId": "ing_001", "text": "butter"},
        {"ingredientId": "ing_001", "text": "Unsalted Butter"},
    ]

    db = AsyncMock()

    with patch("app.api.candidates.ingredient_repo") as mock_repo:
        mock_repo.get_by_id = AsyncMock(return_value=mock_ingredient)
        mock_repo.update_aliases = AsyncMock()

        await _accumulate_ingredient_aliases(db, ingredients)

        mock_repo.update_aliases.assert_not_called()


@pytest.mark.asyncio
async def test_accumulate_aliases_skips_no_ingredient_id():
    """Rows without ingredientId are silently skipped."""
    from app.api.candidates import _accumulate_ingredient_aliases

    ingredients = [
        {"text": "mystery item"},
        {"ingredientId": "", "text": "also no id"},
    ]

    db = AsyncMock()

    with patch("app.api.candidates.ingredient_repo") as mock_repo:
        mock_repo.get_by_id = AsyncMock()
        mock_repo.update_aliases = AsyncMock()

        await _accumulate_ingredient_aliases(db, ingredients)

        mock_repo.get_by_id.assert_not_called()
        mock_repo.update_aliases.assert_not_called()


# --- Media materialization (T-099) ---

@pytest.mark.asyncio
async def test_materialize_no_images_returns_empty():
    """No image URLs means no work done."""
    from app.services.media_materialization_service import materialize_extracted_images

    db = AsyncMock()
    result = await materialize_extracted_images({}, "rec_001", "user_001", db)
    assert result == []


@pytest.mark.asyncio
async def test_materialize_no_bucket_registers_url_refs():
    """If S3_BUCKET is not configured, register images as URL refs instead of uploading."""
    from app.services.media_materialization_service import materialize_extracted_images

    db = AsyncMock()
    with patch("app.services.media_materialization_service.get_settings") as mock_settings:
        mock_settings.return_value.s3_bucket = None
        result = await materialize_extracted_images(
            {"imageUrls": ["https://example.com/img.jpg"]},
            "rec_001", "user_001", db,
        )
    assert len(result) == 1
    assert result[0].startswith("media_")


# --- Workers init (Task 5) ---

def test_workers_init_documents_background_execution():
    """Workers run in-process via background_runner; no separate broker process."""
    from pathlib import Path
    init_path = Path(__file__).resolve().parent.parent / "app" / "workers" / "__init__.py"
    content = init_path.read_text()
    assert "in-process" in content.lower()
