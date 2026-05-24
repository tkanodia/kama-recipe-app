"""T-081: Shopping list generation service.

Groups ingredients by ingredient.category directly when ingredientId is mapped.
Falls back to LLM classification only for unmapped ingredients (no ingredientId).
"""

from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tables import Artifact
from app.repositories import artifact_repo, canonical_recipe_repo, ingredient_repo

log = structlog.get_logger()

CATEGORY_DISPLAY_ORDER = [
    "produce", "meat_seafood", "dairy", "grains_bread",
    "spices_seasoning", "oils_vinegars", "canned_jarred",
    "frozen", "baking", "nuts_seeds", "beverages", "other",
]

CATEGORY_DISPLAY_NAMES: dict[str, str] = {
    "produce": "Produce",
    "meat_seafood": "Meat & Seafood",
    "dairy": "Dairy",
    "grains_bread": "Grains & Bread",
    "spices_seasoning": "Spices & Seasoning",
    "oils_vinegars": "Oils & Vinegars",
    "canned_jarred": "Canned & Jarred",
    "frozen": "Frozen",
    "baking": "Baking",
    "nuts_seeds": "Nuts & Seeds",
    "beverages": "Beverages",
    "other": "Other",
}


async def generate_shopping_list(
    session: AsyncSession,
    recipe_ids: list[str],
    user_id: str,
    title: str | None = None,
) -> dict[str, Any]:
    log.info("shopping_list_generate_start", user_id=user_id, recipe_count=len(recipe_ids))
    all_ingredients: list[dict[str, Any]] = []
    recipe_titles: dict[str, str] = {}

    for recipe_id in recipe_ids:
        recipe = await canonical_recipe_repo.get_by_id(session, recipe_id)
        if recipe is None or recipe.user_id != user_id:
            continue
        recipe_titles[recipe_id] = recipe.title
        for ing in recipe.ingredients:
            all_ingredients.append({**ing, "_sourceRecipeId": recipe_id})

    deduped = _deduplicate_ingredients(all_ingredients)
    categorized = await _categorize_items(session, deduped)
    categories = _build_categories(categorized, recipe_titles)

    list_title = title or _auto_title(recipe_titles)

    total_items = sum(len(c["items"]) for c in categories)
    log.info(
        "shopping_list_generate_done",
        total_items=total_items, section_count=len(categories),
    )
    return {
        "title": list_title,
        "sourceRecipeIds": recipe_ids,
        "categories": categories,
        "recipeCount": len(recipe_ids),
    }


def _deduplicate_ingredients(
    ingredients: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    unmapped: dict[str, dict[str, Any]] = {}

    for ing in ingredients:
        ingredient_id = ing.get("ingredientId")
        text = ing.get("text", "").strip()
        source_recipe = ing.get("_sourceRecipeId")
        qty = ing.get("quantity")
        unit = ing.get("unit")

        if ingredient_id:
            if ingredient_id in by_id:
                entry = by_id[ingredient_id]
                if source_recipe not in entry["sourceRecipeIds"]:
                    entry["sourceRecipeIds"].append(source_recipe)
                entry["_qty_parts"].append((qty, unit))
            else:
                by_id[ingredient_id] = {
                    "ingredientId": ingredient_id,
                    "displayText": text,
                    "sourceRecipeIds": [source_recipe],
                    "checked": False,
                    "_qty_parts": [(qty, unit)],
                }
        else:
            text_lower = text.lower()
            if text_lower in unmapped:
                entry = unmapped[text_lower]
                if source_recipe not in entry["sourceRecipeIds"]:
                    entry["sourceRecipeIds"].append(source_recipe)
                entry["_qty_parts"].append((qty, unit))
            else:
                unmapped[text_lower] = {
                    "ingredientId": None,
                    "displayText": text,
                    "sourceRecipeIds": [source_recipe],
                    "checked": False,
                    "_qty_parts": [(qty, unit)],
                }

    result = list(by_id.values())
    result.extend(unmapped.values())

    for item in result:
        qty_str, unit_str = _combine_quantities(item.pop("_qty_parts"))
        item["quantity"] = qty_str
        item["unit"] = unit_str

    return result


def _parse_number(s: str | int | float | None) -> float | None:
    """Parse a quantity string into a float. Handles fractions like '1/2' and mixed like '1 1/2'."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    if not s:
        return None
    s = str(s).strip()
    parts = s.split()
    total = 0.0
    for part in parts:
        if "/" in part:
            nums = part.split("/")
            try:
                total += float(nums[0]) / float(nums[1])
            except (ValueError, ZeroDivisionError):
                return None
        else:
            try:
                total += float(part)
            except ValueError:
                return None
    return total


def _format_number(n: float) -> str:
    """Format a float as a clean string (no trailing .0)."""
    if n == int(n):
        return str(int(n))
    return f"{n:.2g}"


def _combine_quantities(
    parts: list[tuple[Any, Any]],
) -> tuple[str | None, str | None]:
    """Combine multiple (quantity, unit) pairs into a single cumulative quantity.

    Same unit → sum numerics.
    Mixed units → concatenate as 'X unit1 + Y unit2'.
    Non-numeric → keep first occurrence.
    """
    if not parts:
        return None, None
    if len(parts) == 1:
        qty, unit = parts[0]
        qty_s = str(qty) if qty is not None else None
        unit_s = str(unit) if unit else None
        return qty_s, unit_s

    by_unit: dict[str, list[tuple[Any, Any]]] = {}
    for qty, unit in parts:
        key = str(unit or "").strip().lower()
        by_unit.setdefault(key, []).append((qty, unit))

    combined_segments: list[str] = []
    final_unit: str | None = None

    for unit_key, group in by_unit.items():
        numerics: list[float] = []
        non_numeric: list[str] = []
        raw_unit = str(group[0][1]) if group[0][1] else None

        for qty, _ in group:
            parsed = _parse_number(qty)
            if parsed is not None:
                numerics.append(parsed)
            elif qty:
                non_numeric.append(str(qty))

        if numerics:
            total = sum(numerics)
            segment = _format_number(total)
            if raw_unit:
                segment += f" {raw_unit}"
            combined_segments.append(segment)
            if final_unit is None:
                final_unit = raw_unit
        elif non_numeric:
            combined_segments.append(non_numeric[0] + (f" {raw_unit}" if raw_unit else ""))

    if len(combined_segments) == 1 and final_unit:
        total_str = _format_number(sum(
            n for qty, _ in parts if (n := _parse_number(qty)) is not None
        ))
        return total_str, final_unit

    if combined_segments:
        return " + ".join(combined_segments), None

    qty, unit = parts[0]
    return (str(qty) if qty is not None else None, str(unit) if unit else None)


async def _categorize_items(
    session: AsyncSession,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Look up category from DB for mapped items. Unmapped → LLM fallback."""
    for item in items:
        ingredient_id = item.get("ingredientId")
        if ingredient_id:
            db_ing = await ingredient_repo.get_by_id(session, ingredient_id)
            if db_ing:
                item["category"] = db_ing.category
            else:
                item["category"] = await _llm_guess_category(item["displayText"])
        else:
            item["category"] = await _llm_guess_category(item["displayText"])

    return items


async def _llm_guess_category(text: str) -> str:
    """Fallback: guess category for unmapped ingredients.
    Uses simple heuristics first, LLM only if truly ambiguous.
    """
    lower = text.lower().strip()

    heuristic_map: list[tuple[list[str], str]] = [
        (["chicken", "beef", "pork", "lamb", "turkey", "duck", "veal", "bacon",
          "sausage", "ham", "prosciutto", "pancetta", "chorizo", "steak",
          "salmon", "tuna", "shrimp", "prawn", "cod", "tilapia", "halibut",
          "crab", "lobster", "scallop", "clam", "mussel", "oyster", "fish",
          "anchov", "sardine", "squid", "calamari", "octopus"], "meat_seafood"),
        (["milk", "cream", "cheese", "butter", "yogurt", "egg", "sour cream",
          "ricotta", "mascarpone", "ghee", "paneer", "buttermilk"], "dairy"),
        (["sugar", "honey", "maple", "molasses", "agave", "vanilla", "extract",
          "stevia", "corn syrup", "baking powder", "baking soda", "yeast",
          "cocoa", "chocolate chip", "cornstarch", "gelatin",
          "cream of tartar", "sprinkles"], "baking"),
        (["oil", "olive oil", "coconut oil", "sesame oil", "cooking spray",
          "vinegar", "balsamic", "soy sauce", "fish sauce", "ketchup",
          "mustard", "mayo", "hot sauce", "worcestershire", "bbq",
          "barbecue", "hoisin", "teriyaki", "sriracha", "pesto", "salsa",
          "oyster sauce", "miso", "harissa", "gochujang", "sambal",
          "chutney", "tahini"], "oils_vinegars"),
        (["salt", "pepper", "cumin", "paprika", "cinnamon", "oregano", "thyme",
          "rosemary", "basil", "dill", "sage", "turmeric", "chili powder",
          "cayenne", "nutmeg", "cardamom", "garam masala", "curry",
          "bay leaf", "allspice", "clove", "saffron", "sumac",
          "za'atar", "five spice", "italian season", "onion powder",
          "garlic powder"], "spices_seasoning"),
        (["rice", "quinoa", "oats", "barley", "bulgur", "farro", "couscous",
          "cornmeal", "breadcrumb", "millet", "pasta", "spaghetti", "penne",
          "fettuccine", "linguine", "rigatoni", "macaroni", "noodle",
          "lasagna", "orzo", "gnocchi", "flour", "bread", "tortilla",
          "pita", "naan", "baguette", "ciabatta", "croissant", "bagel",
          "muffin", "pizza dough", "pie crust", "puff pastry"], "grains_bread"),
        (["canned", "tomato paste", "tomato sauce", "broth", "stock",
          "coconut milk", "chipotle", "olive", "caper", "pickle",
          "chickpea", "garbanzo", "black bean", "kidney bean", "lentil",
          "bean", "pinto", "split pea"], "canned_jarred"),
        (["almond", "walnut", "cashew", "pecan", "pistachio", "peanut",
          "sesame seed", "sunflower", "pumpkin seed", "chia", "flax",
          "hemp", "pine nut", "hazelnut", "macadamia", "poppy seed",
          "peanut butter", "almond butter"], "nuts_seeds"),
        (["frozen"], "frozen"),
        (["wine", "juice", "mirin", "shaoxing"], "beverages"),
    ]

    for keywords, category in heuristic_map:
        if any(kw in lower for kw in keywords):
            return category

    # Everything else defaults to "produce" for fresh items or "other"
    produce_hints = [
        "lettuce", "tomato", "onion", "garlic", "ginger", "pepper",
        "carrot", "celery", "potato", "broccoli", "spinach", "kale",
        "mushroom", "zucchini", "cucumber", "avocado", "lemon", "lime",
        "apple", "banana", "berry", "mango", "pineapple",
    ]
    if any(h in lower for h in produce_hints):
        return "produce"

    return "other"


def _build_categories(
    items: list[dict[str, Any]],
    recipe_titles: dict[str, str],
) -> list[dict[str, Any]]:
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        cat = item.get("category", "other")
        source_ids = item.get("sourceRecipeIds", [])
        first_recipe_id = source_ids[0] if source_ids else None
        recipe_title = _multi_recipe_label(source_ids, recipe_titles)
        clean_item = {
            "text": item.get("displayText", ""),
            "quantity": item.get("quantity"),
            "unit": item.get("unit"),
            "ingredientName": item.get("displayText", ""),
            "recipeId": first_recipe_id,
            "recipeTitle": recipe_title,
            "checked": False,
        }
        by_category.setdefault(cat, []).append(clean_item)

    categories = []
    for cat in CATEGORY_DISPLAY_ORDER:
        if cat in by_category:
            categories.append({
                "category": CATEGORY_DISPLAY_NAMES.get(cat, cat.title()),
                "items": by_category.pop(cat),
            })

    for cat, cat_items in sorted(by_category.items()):
        categories.append({
            "category": CATEGORY_DISPLAY_NAMES.get(cat, cat.title()),
            "items": cat_items,
        })

    return categories


def _multi_recipe_label(
    source_ids: list[str], recipe_titles: dict[str, str]
) -> str | None:
    if not source_ids:
        return None
    first_title = recipe_titles.get(source_ids[0])
    if not first_title:
        return None
    if len(source_ids) == 1:
        return first_title
    return f"{first_title} + {len(source_ids) - 1} more"


def _auto_title(recipe_titles: dict[str, str]) -> str:
    names = list(recipe_titles.values())
    if not names:
        return "Shopping List"
    if len(names) == 1:
        return f"Shopping list for {names[0]}"
    if len(names) == 2:
        return f"Shopping list for {names[0]} & {names[1]}"
    return f"Shopping list for {names[0]} + {len(names) - 1} more"


async def generate_and_persist_shopping_list(
    session: AsyncSession,
    recipe_ids: list[str],
    user_id: str,
    title: str | None = None,
) -> Artifact:
    content = await generate_shopping_list(session, recipe_ids, user_id, title=title)

    artifact = await artifact_repo.create(
        session,
        user_id=user_id,
        artifact_type="shopping_list",
        title=content["title"],
        content=content,
        source_recipe_ids=content.get("sourceRecipeIds", recipe_ids),
    )
    log.info("shopping_list_persisted", artifact_id=artifact.id)
    return artifact
