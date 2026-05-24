"""Unit tests for ingestion tools — no database, no external services."""

from app.tools.source_tools import classify_source, extract_recipe_links
from app.tools.extraction_tools import check_schema_markup, schema_recipe_extract
from app.tools.evaluation_tools import assess_parseability, evaluate_candidate


class TestClassifySource:
    def test_url_recipe_webpage(self):
        result = classify_source("url", url="https://www.allrecipes.com/recipe/12345")
        assert result.success
        assert result.signals["sourceSubtype"] == "recipe_webpage"

    def test_url_youtube(self):
        result = classify_source("url", url="https://www.youtube.com/watch?v=abc123")
        assert result.success
        assert result.signals["sourceSubtype"] == "youtube"

    def test_url_instagram(self):
        result = classify_source("url", url="https://www.instagram.com/p/abc123/")
        assert result.success
        assert result.signals["sourceSubtype"] == "instagram_photo"

    def test_url_tiktok(self):
        result = classify_source("url", url="https://www.tiktok.com/@user/video/123")
        assert result.success
        assert result.signals["sourceSubtype"] == "tiktok"

    def test_image_source(self):
        result = classify_source("image", file_asset_ref="s3://bucket/img.jpg")
        assert result.success
        assert result.signals["sourceSubtype"] == "image"

    def test_text_source(self):
        result = classify_source("text")
        assert result.success
        assert result.signals["sourceSubtype"] == "text"
        assert result.signals["textStructure"] == "ambiguous"

    def test_text_source_structured(self):
        recipe_text = (
            "Chocolate Cake\n\n"
            "Ingredients:\n"
            "- 2 cups flour\n"
            "- 1 cup sugar\n\n"
            "Steps:\n"
            "1. Mix dry ingredients\n"
            "2. Add wet ingredients\n"
            "3. Bake at 350F\n"
        )
        result = classify_source("text", raw_text=recipe_text)
        assert result.success
        assert result.signals["textStructure"] == "structured_recipe"

    def test_text_source_freeform(self):
        freeform = "Made a really yummy pasta last night with some garlic and tomatoes, should save this."
        result = classify_source("text", raw_text=freeform)
        assert result.success
        assert result.signals["textStructure"] == "freeform_notes"


class TestExtractRecipeLinks:
    def test_finds_urls(self):
        text = '<a href="https://example.com/recipe/pasta">Pasta</a> and https://food.com/soup'
        result = extract_recipe_links(text)
        assert result.success
        assert len(result.signals["urls"]) >= 1

    def test_filters_cdns(self):
        text = "https://cdn.example.com/image.jpg https://example.com/recipe"
        result = extract_recipe_links(text)
        urls = [u["url"] for u in result.signals["urls"]]
        assert not any("cdn" in u for u in urls)

    def test_empty_text(self):
        result = extract_recipe_links("")
        assert result.success
        assert result.signals["urls"] == []


class TestCheckSchemaMarkup:
    def test_finds_recipe_schema(self):
        html = '''
        <html><head>
        <script type="application/ld+json">
        {"@type": "Recipe", "name": "Test", "recipeIngredient": ["1 cup flour"]}
        </script>
        </head><body></body></html>
        '''
        result = check_schema_markup(html)
        assert result.success
        assert result.signals["schemaFound"]
        assert result.signals["recipeSchema"]["name"] == "Test"

    def test_no_schema(self):
        result = check_schema_markup("<html><body>No recipe here</body></html>")
        assert not result.success

    def test_schema_in_graph(self):
        html = '''
        <script type="application/ld+json">
        {"@graph": [{"@type": "WebPage"}, {"@type": "Recipe", "name": "Nested"}]}
        </script>
        '''
        result = check_schema_markup(html)
        assert result.success
        assert result.signals["recipeSchema"]["name"] == "Nested"


class TestSchemaRecipeExtract:
    def test_basic_extraction(self):
        schema = {
            "name": "Chocolate Cake",
            "description": "A rich chocolate cake",
            "recipeIngredient": ["2 cups flour", "1 cup sugar", "3 eggs"],
            "recipeInstructions": [
                {"text": "Mix dry ingredients"},
                {"text": "Add wet ingredients"},
                {"text": "Bake at 350F for 30 minutes"},
            ],
            "prepTime": "PT15M",
            "cookTime": "PT30M",
            "recipeYield": "12 servings",
        }
        result = schema_recipe_extract(schema)
        assert result.success
        assert result.candidate_update["title"] == "Chocolate Cake"
        assert len(result.candidate_update["ingredients"]) == 3
        assert len(result.candidate_update["steps"]) == 3
        assert result.candidate_update["prepTimeMinutes"] == 15
        assert result.candidate_update["cookTimeMinutes"] == 30
        assert result.candidate_update["servings"] == 12

    def test_iso_duration_hours_and_minutes(self):
        schema = {"name": "Slow Roast", "cookTime": "PT2H30M", "recipeIngredient": [], "recipeInstructions": []}
        result = schema_recipe_extract(schema)
        assert result.candidate_update["cookTimeMinutes"] == 150

    def test_missing_name(self):
        result = schema_recipe_extract({"recipeIngredient": ["flour"]})
        assert not result.success


class TestEvaluateCandidate:
    def test_complete_recipe(self):
        result = evaluate_candidate(
            title="Pasta",
            ingredients=[{"text": "spaghetti"}, {"text": "sauce"}],
            steps=[{"text": "Boil pasta"}, {"text": "Add sauce"}],
            description="Simple pasta",
            cook_time=20,
            servings=4,
        )
        assert result.success
        assert result.signals["canonicalEligible"]

    def test_missing_title(self):
        result = evaluate_candidate(
            title="",
            ingredients=[{"text": "flour"}],
            steps=[{"text": "mix"}],
        )
        assert not result.signals["canonicalEligible"]
        errors = [f for f in result.signals["reviewFindings"] if f["severity"] == "error"]
        assert any(f["code"] == "missing_title" for f in errors)

    def test_no_ingredients(self):
        result = evaluate_candidate(title="Test", ingredients=[], steps=[{"text": "cook"}])
        assert not result.signals["canonicalEligible"]

    def test_draft_eligible_with_partial(self):
        result = evaluate_candidate(title="Just a Title", ingredients=[], steps=[])
        assert result.signals["draftEligible"]
        assert not result.signals["canonicalEligible"]


class TestAssessParseability:
    def test_full_signals(self):
        artifacts = [
            {
                "artifactType": "url_metadata",
                "payload": {"pageTitle": "Recipe Page", "hasRecipeSchema": True},
            }
        ]
        result = assess_parseability(artifacts, source_subtype="recipe_webpage")
        assert result.success
        assert result.signals["canonicalEligible"]

    def test_low_signals(self):
        artifacts = [
            {"artifactType": "url_metadata", "payload": {"pageTitle": None, "hasRecipeSchema": False}},
        ]
        result = assess_parseability(artifacts, source_subtype="unknown")
        assert result.success
        assert not result.signals["canonicalEligible"]
