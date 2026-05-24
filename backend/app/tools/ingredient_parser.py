"""Parse raw ingredient text into structured quantity / unit / name components,
and match parsed names against the ingredient database."""

from __future__ import annotations

import re
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import ingredient_repo

log = structlog.get_logger()

# Fraction unicode → decimal
_UNICODE_FRACS: dict[str, float] = {
    "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3,
    "¼": 0.25, "¾": 0.75,
    "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
    "⅙": 1 / 6, "⅚": 5 / 6,
    "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
}

_UNIT_SYNONYMS: dict[str, str] = {
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsps": "tbsp", "tbs": "tbsp", "T": "tbsp",
    "teaspoon": "tsp", "teaspoons": "tsp", "tsps": "tsp", "t": "tsp",
    "cup": "cup", "cups": "cup", "c": "cup",
    "ounce": "oz", "ounces": "oz",
    "pound": "lb", "pounds": "lb", "lbs": "lb",
    "gram": "g", "grams": "g",
    "kilogram": "kg", "kilograms": "kg",
    "milliliter": "ml", "milliliters": "ml", "millilitre": "ml", "millilitres": "ml",
    "liter": "L", "liters": "L", "litre": "L", "litres": "L",
    "pinch": "pinch", "pinches": "pinch",
    "dash": "dash", "dashes": "dash",
    "clove": "clove", "cloves": "clove",
    "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece", "pcs": "piece",
    "bunch": "bunch", "bunches": "bunch",
    "sprig": "sprig", "sprigs": "sprig",
    "can": "can", "cans": "can",
    "package": "package", "packages": "package", "pkg": "package",
    "stick": "stick", "sticks": "stick",
    "head": "head", "heads": "head",
    "handful": "handful", "handfuls": "handful",
    "whole": "whole",
    "large": "large", "medium": "medium", "small": "small",
}

_KNOWN_UNITS: set[str] = {
    "tbsp", "tsp", "cup", "oz", "lb", "g", "kg", "ml", "L",
    "pinch", "dash", "clove", "slice", "piece", "bunch", "sprig",
    "can", "package", "stick", "head", "handful", "whole",
    "large", "medium", "small",
}

# Quantity pattern: e.g. "1", "1/2", "1 1/2", "½", "1½", "1-2", "~2"
_FRAC_CHARS = r"½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞"
_QTY_ATOM = (
    r"(?:\d+\s+\d+/\d+"         # "1 1/2"
    r"|\d+\s+[" + _FRAC_CHARS + r"]"  # "1 ½"
    r"|\d+[" + _FRAC_CHARS + r"]"     # "1½"
    r"|\d+/\d+"                  # "1/2"
    r"|\d+\.?\d*"                # "2", "2.5"
    r"|[" + _FRAC_CHARS + r"]"        # "½"
    r")"
)
_QTY_RE = re.compile(
    r"^~?\s*"
    r"(" + _QTY_ATOM + r")"
    r"(\s*[-–—to]+\s*(" + _QTY_ATOM + r"))?"
)

_PARENS_RE = re.compile(r"\([^)]*\)")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")
_DESCRIPTOR_WORDS = {
    "fresh", "dried", "frozen", "chopped", "minced", "diced", "sliced",
    "grated", "shredded", "crushed", "ground", "toasted", "roasted",
    "melted", "softened", "room", "temperature", "cold", "warm", "hot",
    "ripe", "juicy", "firm", "optional", "packed", "sifted", "unsalted",
    "salted", "boneless", "skinless", "cooked", "uncooked", "raw",
    "peeled", "deveined", "trimmed", "halved", "quartered",
    "finely", "roughly", "thinly", "thickly", "lightly",
    "cut", "into", "wedges", "florets", "chunks", "cubes", "pieces",
    "strips", "rings", "segments", "drained", "rinsed", "and", "or",
    "taste", "to", "as", "needed", "for", "garnish", "garnishing",
    "serving", "decoration", "topping", "consistency",
    "about", "approximately", "divided", "separated", "reserve",
    "plus", "more", "extra", "additional", "if",
    "small", "medium", "large", "thin", "thick",
    "beaten", "whisked", "sieved", "strained", "squeezed",
    "at", "room", "preferably",
}


def _parse_qty_string(s: str) -> str | None:
    """Return a human-friendly quantity string, or None."""
    s = s.strip()
    if not s:
        return None

    # Handle unicode fractions embedded with digits: "1½" → "1 1/2"
    for uf, dec in _UNICODE_FRACS.items():
        if uf in s:
            num_part = s.replace(uf, "").strip()
            # Convert decimal to fraction string for display
            frac_map = {0.5: "1/2", 1/3: "1/3", 2/3: "2/3", 0.25: "1/4", 0.75: "3/4", 0.125: "1/8"}
            frac_str = frac_map.get(dec, str(dec))
            if num_part:
                return f"{num_part} {frac_str}"
            return frac_str

    return s


def parse_ingredient_text(raw: str) -> dict[str, str | None]:
    """Parse a raw ingredient string into quantity, unit, and name.

    Returns dict with keys: quantity, unit, name (the cleaned ingredient name).
    """
    text = raw.strip()
    if not text:
        return {"quantity": None, "unit": None, "name": None}

    # Remove parenthetical notes at the end, e.g. "(optional)", "(Note 5)"
    # but keep "(1 can)" style that's part of the quantity
    cleaned = text

    # Handle dual measurements like "395 g / 14 oz": keep the first one
    dual_match = re.match(
        r"^(\d+\.?\d*)\s*(g|kg|ml|L|oz|lb)\s*/\s*\d+\.?\d*\s*(g|kg|ml|L|oz|lb)\s+(.+)",
        cleaned, re.IGNORECASE,
    )
    if dual_match:
        cleaned = f"{dual_match.group(1)} {dual_match.group(2)} {dual_match.group(4)}"

    # Extract quantity
    qty_match = _QTY_RE.match(cleaned)
    quantity: str | None = None
    remainder = cleaned

    if qty_match:
        raw_qty = qty_match.group(0).strip()
        quantity = _parse_qty_string(raw_qty)
        remainder = cleaned[qty_match.end():].strip()

    # Extract unit
    unit: str | None = None
    if remainder:
        first_word = remainder.split()[0].rstrip(".,;:")
        lower_first = first_word.lower()
        if lower_first in _UNIT_SYNONYMS:
            unit = _UNIT_SYNONYMS[lower_first]
            remainder = remainder[len(first_word):].strip().lstrip(".,;: ")
        elif lower_first in _KNOWN_UNITS:
            unit = lower_first
            remainder = remainder[len(first_word):].strip().lstrip(".,;: ")

    # Clean the remaining ingredient name
    name = _clean_ingredient_name(remainder)

    # Build a clean display string: "2 cups heavy cream"
    display_parts = []
    if quantity:
        display_parts.append(quantity)
    if unit:
        display_parts.append(unit)
    if name:
        display_parts.append(name)
    display_text = " ".join(display_parts) if display_parts else raw.strip()

    return {"quantity": quantity, "unit": unit, "name": name, "displayText": display_text}


def _clean_ingredient_name(raw: str) -> str | None:
    """Strip parenthetical notes, descriptors, and normalize the core ingredient name."""
    if not raw:
        return None

    # Remove parenthetical content
    cleaned = _PARENS_RE.sub("", raw)
    # Remove stray closing parens
    cleaned = cleaned.replace(")", "")
    # Remove leading/trailing commas, dashes, semicolons
    cleaned = cleaned.strip().strip(",-–—;: ")
    # Collapse spaces
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned).strip()

    if not cleaned:
        return None

    # Handle slash alternatives: "heavy cream / whipping cream" → "heavy cream"
    if " / " in cleaned:
        cleaned = cleaned.split(" / ")[0].strip()

    # Strip trailing descriptor phrases after a comma (e.g. "garlic, minced" → "garlic")
    if ", " in cleaned:
        parts = cleaned.split(", ")
        core = parts[0]
        # Keep the comma part only if it's not a common descriptor
        trailing = ", ".join(parts[1:]).lower()
        trailing_words = set(trailing.split())
        if trailing_words and trailing_words.issubset(_DESCRIPTOR_WORDS):
            cleaned = core
        # else: keep as-is (might be "salt, to taste" style, but name is still useful)

    return cleaned.strip() if cleaned.strip() else None


async def map_ingredients_to_db(
    session: AsyncSession,
    ingredients: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse each ingredient's text, match against the DB, and enrich with
    ingredientId, category, and parsed quantity/unit.

    Mutates and returns the same list for convenience.
    """
    for ing in ingredients:
        text = ing.get("text", "")
        if not text:
            continue

        parsed = parse_ingredient_text(text)

        if parsed["quantity"] and not ing.get("quantity"):
            ing["quantity"] = parsed["quantity"]
        if parsed["unit"] and not ing.get("unit"):
            ing["unit"] = parsed["unit"]
        if parsed.get("displayText"):
            ing["text"] = parsed["displayText"]

        # Skip DB lookup if already mapped
        if ing.get("ingredientId"):
            continue

        name = parsed["name"]
        if not name:
            continue

        # Try exact match first
        match = await ingredient_repo.find_by_name(session, name)
        if match:
            ing["ingredientId"] = match.id
            ing["mappedIngredient"] = {
                "id": match.id,
                "name": match.name,
                "category": match.category,
            }
            continue

        # Tier 2: Search (exact + alias + fuzzy) on the full parsed name
        search_results = await ingredient_repo.search(session, name, limit=3)
        if search_results and search_results[0]["matchConfidence"] in ("exact", "alias"):
            best = search_results[0]
            ing["ingredientId"] = best["id"]
            ing["mappedIngredient"] = {
                "id": best["id"],
                "name": best["name"],
                "category": best["category"],
            }
            continue

        # Tier 3: Progressively shorter name forms for compound names
        # e.g. "sweetened condensed milk" → "condensed milk" → "milk"
        clean_name = re.sub(r"[,;:\-–—]", " ", name.lower()).strip()
        clean_name = _MULTI_SPACE_RE.sub(" ", clean_name)
        words = clean_name.split()
        found = False
        if len(words) > 1:
            for start_idx in range(1, len(words)):
                shorter = " ".join(words[start_idx:])
                match = await ingredient_repo.find_by_name(session, shorter)
                if match:
                    ing["ingredientId"] = match.id
                    ing["mappedIngredient"] = {
                        "id": match.id,
                        "name": match.name,
                        "category": match.category,
                    }
                    found = True
                    break

        if found:
            continue

        # Tier 4: Search on last meaningful word (core ingredient)
        if len(words) > 1:
            core_word = words[-1]
            if len(core_word) >= 3:
                core_results = await ingredient_repo.search(session, core_word, limit=1)
                if core_results and core_results[0]["matchConfidence"] in ("exact", "alias"):
                    best = core_results[0]
                    ing["ingredientId"] = best["id"]
                    ing["mappedIngredient"] = {
                        "id": best["id"],
                        "name": best["name"],
                        "category": best["category"],
                    }

    return ingredients
