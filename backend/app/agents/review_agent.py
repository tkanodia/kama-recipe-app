"""T-028: Review agent — verifies and enriches recipe candidates.

Called after extraction to validate fields, flag issues, and determine
eligibility for canonical vs draft save.
"""

import re
from typing import Any

import structlog

from app.tools.base import ToolResult

log = structlog.get_logger()


async def run_review_agent(
    title: str,
    ingredients: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    description: str | None = None,
    prep_time_minutes: int | None = None,
    cook_time_minutes: int | None = None,
    servings: int | None = None,
    extraction_method: str = "",
    source_subtype: str = "",
) -> dict[str, Any]:
    """Returns a review summary with findings, eligibility, and review mode."""

    findings: list[dict[str, Any]] = []
    field_confidence: dict[str, str] = {}

    # --- Title validation ---
    if not title or not title.strip():
        findings.append({
            "code": "missing_title", "severity": "error", "field": "title",
            "message": "Recipe has no title",
        })
        field_confidence["title"] = "none"
    elif len(title.strip()) < 3:
        findings.append({
            "code": "short_title", "severity": "warning", "field": "title",
            "message": "Title is very short",
        })
        field_confidence["title"] = "low"
    else:
        field_confidence["title"] = "high"

    # --- Ingredients validation ---
    if not ingredients:
        findings.append({
            "code": "missing_ingredients", "severity": "error", "field": "ingredients",
            "message": "No ingredients provided",
        })
        field_confidence["ingredients"] = "none"
    else:
        valid_count = sum(1 for i in ingredients if i.get("text", "").strip())
        empty_count = len(ingredients) - valid_count
        if empty_count > 0:
            findings.append({
                "code": "empty_ingredient_rows", "severity": "warning", "field": "ingredients",
                "message": f"{empty_count} ingredient row(s) have no text",
            })

        if valid_count < 2:
            findings.append({
                "code": "few_ingredients", "severity": "warning", "field": "ingredients",
                "message": f"Only {valid_count} ingredient(s) — seems incomplete",
            })
            field_confidence["ingredients"] = "medium"
        else:
            field_confidence["ingredients"] = "high"

        # Check for duplicate ingredients
        seen_texts = set()
        dupe_count = 0
        for ing in ingredients:
            t = ing.get("text", "").strip().lower()
            if t and t in seen_texts:
                dupe_count += 1
            seen_texts.add(t)
        if dupe_count > 0:
            findings.append({
                "code": "duplicate_ingredients", "severity": "warning", "field": "ingredients",
                "message": f"{dupe_count} duplicate ingredient(s) detected",
            })

    # --- Steps validation ---
    if not steps:
        findings.append({
            "code": "missing_steps", "severity": "error", "field": "steps",
            "message": "No steps provided",
        })
        field_confidence["steps"] = "none"
    else:
        valid_steps = sum(1 for s in steps if s.get("text", "").strip())
        if valid_steps < 2:
            findings.append({
                "code": "few_steps", "severity": "warning", "field": "steps",
                "message": f"Only {valid_steps} step(s) — may be incomplete",
            })
            field_confidence["steps"] = "medium"
        else:
            field_confidence["steps"] = "high"

        for i, step in enumerate(steps):
            text = step.get("text", "")
            if len(text) > 2000:
                findings.append({
                    "code": "long_step", "severity": "info", "field": "steps",
                    "message": f"Step {i + 1} is very long ({len(text)} chars) — may need splitting",
                })

    # --- Optional fields ---
    if not description:
        findings.append({
            "code": "missing_description", "severity": "info", "field": "description",
            "message": "No description provided",
        })
        field_confidence["description"] = "none"
    else:
        field_confidence["description"] = "high"

    if cook_time_minutes is None and prep_time_minutes is None:
        findings.append({
            "code": "missing_times", "severity": "info", "field": "prepTimeMinutes",
            "message": "No cooking times provided",
        })
    else:
        if prep_time_minutes is not None:
            field_confidence["prepTimeMinutes"] = "high" if prep_time_minutes > 0 else "low"
        if cook_time_minutes is not None:
            field_confidence["cookTimeMinutes"] = "high" if cook_time_minutes > 0 else "low"

    if servings is None:
        findings.append({
            "code": "missing_servings", "severity": "info", "field": "servings",
            "message": "No serving size provided",
        })
    else:
        field_confidence["servings"] = "high" if servings > 0 else "low"

    # --- Time sanity check ---
    if prep_time_minutes is not None and prep_time_minutes > 600:
        findings.append({
            "code": "extreme_prep_time", "severity": "warning", "field": "prepTimeMinutes",
            "message": f"Prep time is {prep_time_minutes} minutes — seems unreasonably long",
        })
        field_confidence["prepTimeMinutes"] = "low"
    if cook_time_minutes is not None and cook_time_minutes > 1440:
        findings.append({
            "code": "extreme_cook_time", "severity": "warning", "field": "cookTimeMinutes",
            "message": f"Cook time is {cook_time_minutes} minutes — seems unreasonably long",
        })
        field_confidence["cookTimeMinutes"] = "low"

    # --- Eligibility determination ---
    error_count = sum(1 for f in findings if f["severity"] == "error")
    warning_count = sum(1 for f in findings if f["severity"] == "warning")

    canonical_eligible = error_count == 0
    draft_eligible = bool(title) or bool(ingredients) or bool(steps)

    if error_count == 0 and warning_count == 0:
        review_mode = "quick"
    elif error_count == 0 and warning_count <= 2:
        review_mode = "standard"
    else:
        review_mode = "reconstruction"

    return {
        "reviewFindings": findings,
        "fieldConfidenceMap": field_confidence,
        "canonicalEligible": canonical_eligible,
        "draftEligible": draft_eligible,
        "reviewMode": review_mode,
        "findingSummary": {
            "errors": error_count,
            "warnings": warning_count,
            "info": sum(1 for f in findings if f["severity"] == "info"),
        },
    }
