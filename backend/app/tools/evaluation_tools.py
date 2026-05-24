"""T-023: assess_parseability — evaluate recipe-likeness of gathered content.
   T-025: evaluate_candidate — check candidate completeness and eligibility."""

from typing import Any

from app.tools.base import ToolResult


def assess_parseability(
    artifacts: list[dict[str, Any]],
    source_subtype: str = "unknown",
) -> ToolResult:
    has_title_signal = False
    has_ingredient_signal = False
    has_step_signal = False
    text_quality = "unknown"

    for art in artifacts:
        a_type = art.get("artifactType", art.get("artifact_type", ""))
        payload = art.get("payload", {})

        if a_type == "url_metadata":
            if payload.get("pageTitle"):
                has_title_signal = True
            if payload.get("hasRecipeSchema"):
                has_ingredient_signal = True
                has_step_signal = True

        elif a_type == "cleaned_page_text":
            sections = payload.get("contentSections", [])
            for sec in sections:
                if sec.get("sectionType") == "ingredients":
                    has_ingredient_signal = True
                elif sec.get("sectionType") == "instructions":
                    has_step_signal = True
                elif sec.get("sectionType") == "title":
                    has_title_signal = True
            tl = payload.get("textLength", 0)
            text_quality = "high" if tl > 500 else ("medium" if tl > 200 else "low")

        elif a_type in ("ocr_text", "social_caption", "video_transcript"):
            has_title_signal = True
            text = payload.get("text", "")
            lower = text.lower()
            if any(kw in lower for kw in ("ingredient", "cup", "tbsp", "tsp", "tablespoon")):
                has_ingredient_signal = True
            if any(kw in lower for kw in ("step", "then", "minutes", "preheat", "stir", "bake")):
                has_step_signal = True

    recipe_likelihood = sum([has_title_signal, has_ingredient_signal, has_step_signal])

    if recipe_likelihood >= 2:
        review_mode = "quick" if recipe_likelihood == 3 else "standard"
    else:
        review_mode = "reconstruction"

    canonical_eligible = recipe_likelihood == 3
    draft_eligible = recipe_likelihood >= 1

    blocking_issues = []
    if not has_title_signal:
        blocking_issues.append("No title detected in source")
    if not has_ingredient_signal:
        blocking_issues.append("No ingredient-like content detected")
    if not has_step_signal:
        blocking_issues.append("No instruction-like content detected")

    assessment = {
        "artifactType": "parseability_assessment",
        "payload": {
            "sourceSubtypeDetected": source_subtype,
            "recipeLikelihood": recipe_likelihood,
            "reviewMode": review_mode,
            "canonicalEligible": canonical_eligible,
            "draftEligible": draft_eligible,
            "blockingIssues": blocking_issues,
            "textQuality": text_quality,
        },
    }

    return ToolResult(
        success=True,
        message=f"Parseability: likelihood={recipe_likelihood}/3, mode={review_mode}",
        artifacts=[assessment],
        signals={
            "reviewMode": review_mode,
            "canonicalEligible": canonical_eligible,
            "draftEligible": draft_eligible,
            "recipeLikelihood": recipe_likelihood,
        },
    )


def evaluate_candidate(
    title: str | None,
    ingredients: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    description: str | None = None,
    prep_time: int | None = None,
    cook_time: int | None = None,
    servings: int | None = None,
) -> ToolResult:
    findings: list[dict[str, Any]] = []

    has_title = bool(title and title.strip())
    has_ingredients = len(ingredients) >= 1
    has_steps = len(steps) >= 1

    if not has_title:
        findings.append({
            "code": "missing_title",
            "severity": "error",
            "field": "title",
            "message": "Recipe must have a title",
        })

    if not has_ingredients:
        findings.append({
            "code": "missing_ingredients",
            "severity": "error",
            "field": "ingredients",
            "message": "Recipe must have at least one ingredient",
        })
    else:
        empty_rows = [i for i, ing in enumerate(ingredients) if not ing.get("text", "").strip()]
        if empty_rows:
            findings.append({
                "code": "empty_ingredient_rows",
                "severity": "warning",
                "field": "ingredients",
                "message": f"{len(empty_rows)} ingredient row(s) have no text",
            })

        unmapped = [i for i, ing in enumerate(ingredients) if not ing.get("ingredientId")]
        if unmapped and len(unmapped) == len(ingredients):
            findings.append({
                "code": "no_mapped_ingredients",
                "severity": "info",
                "field": "ingredients",
                "message": "No ingredients mapped to the ingredient database yet",
            })

    if not has_steps:
        findings.append({
            "code": "missing_steps",
            "severity": "error",
            "field": "steps",
            "message": "Recipe must have at least one step",
        })
    else:
        empty_steps = [i for i, s in enumerate(steps) if not s.get("text", "").strip()]
        if empty_steps:
            findings.append({
                "code": "empty_step_rows",
                "severity": "warning",
                "field": "steps",
                "message": f"{len(empty_steps)} step(s) have no text",
            })

    if not description:
        findings.append({
            "code": "missing_description",
            "severity": "info",
            "field": "description",
            "message": "No description provided",
        })

    if cook_time is None and prep_time is None:
        findings.append({
            "code": "missing_times",
            "severity": "info",
            "field": "cookTimeMinutes",
            "message": "No prep or cook time provided",
        })

    if servings is None:
        findings.append({
            "code": "missing_servings",
            "severity": "info",
            "field": "servings",
            "message": "No serving size provided",
        })

    has_errors = any(f["severity"] == "error" for f in findings)
    canonical_eligible = not has_errors
    draft_eligible = has_title or has_ingredients or has_steps

    return ToolResult(
        success=True,
        message=f"Evaluation: canonical={canonical_eligible}, findings={len(findings)}",
        signals={
            "canonicalEligible": canonical_eligible,
            "draftEligible": draft_eligible,
            "reviewFindings": findings,
            "findingCounts": {
                "error": sum(1 for f in findings if f["severity"] == "error"),
                "warning": sum(1 for f in findings if f["severity"] == "warning"),
                "info": sum(1 for f in findings if f["severity"] == "info"),
            },
        },
    )
