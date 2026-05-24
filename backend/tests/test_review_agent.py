"""Unit tests for the review agent."""

import pytest
from app.agents.review_agent import run_review_agent


@pytest.mark.asyncio
async def test_complete_recipe_quick_review():
    result = await run_review_agent(
        title="Spaghetti Carbonara",
        ingredients=[
            {"text": "400g spaghetti"},
            {"text": "200g guanciale"},
            {"text": "4 egg yolks"},
            {"text": "100g pecorino romano"},
        ],
        steps=[
            {"text": "Cook pasta in salted water"},
            {"text": "Fry guanciale until crispy"},
            {"text": "Mix eggs and cheese"},
            {"text": "Combine everything"},
        ],
        description="Classic Roman pasta",
        prep_time_minutes=10,
        cook_time_minutes=20,
        servings=4,
    )
    assert result["canonicalEligible"]
    assert result["reviewMode"] == "quick"
    assert result["findingSummary"]["errors"] == 0


@pytest.mark.asyncio
async def test_missing_title_error():
    result = await run_review_agent(
        title="",
        ingredients=[{"text": "flour"}],
        steps=[{"text": "mix"}],
    )
    assert not result["canonicalEligible"]
    assert any(f["code"] == "missing_title" for f in result["reviewFindings"])


@pytest.mark.asyncio
async def test_missing_ingredients():
    result = await run_review_agent(
        title="Test Recipe",
        ingredients=[],
        steps=[{"text": "do something"}],
    )
    assert not result["canonicalEligible"]
    errors = [f for f in result["reviewFindings"] if f["severity"] == "error"]
    assert any(f["code"] == "missing_ingredients" for f in errors)


@pytest.mark.asyncio
async def test_duplicate_ingredients_warning():
    result = await run_review_agent(
        title="Test",
        ingredients=[
            {"text": "1 cup flour"},
            {"text": "1 cup flour"},
            {"text": "2 eggs"},
        ],
        steps=[{"text": "mix"}, {"text": "bake"}],
    )
    warnings = [f for f in result["reviewFindings"] if f["code"] == "duplicate_ingredients"]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_extreme_cook_time_warning():
    result = await run_review_agent(
        title="Marathon Roast",
        ingredients=[{"text": "1 roast"}],
        steps=[{"text": "cook forever"}],
        cook_time_minutes=2000,
    )
    warnings = [f for f in result["reviewFindings"] if f["code"] == "extreme_cook_time"]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_partial_recipe_draft_eligible():
    result = await run_review_agent(
        title="Just a Title",
        ingredients=[],
        steps=[],
    )
    assert result["draftEligible"]
    assert not result["canonicalEligible"]
    assert result["reviewMode"] == "reconstruction"
