/** Display helper for an ingredient line */
export function formatIngredientLine(text: string, quantity?: string | null, unit?: string | null): string {
  const q = [quantity, unit].filter(Boolean).join(" ").trim();
  if (!q) return text;
  return `${q} ${text}`.trim();
}

// ---------------------------------------------------------------------------
// Serving-size scaling
// ---------------------------------------------------------------------------

const UNICODE_FRACS: Record<string, number> = {
  "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3,
  "¼": 0.25, "¾": 0.75,
  "⅕": 0.2, "⅖": 0.4, "⅗": 0.6, "⅘": 0.8,
  "⅙": 1 / 6, "⅚": 5 / 6,
  "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875,
};

type FractionEntry = [number, string];

const FRACS_COARSE: FractionEntry[] = [
  [0.25, "1/4"], [0.5, "1/2"], [0.75, "3/4"],
];

const FRACS_STANDARD: FractionEntry[] = [
  [0.25, "1/4"], [1 / 3, "1/3"], [0.5, "1/2"],
  [2 / 3, "2/3"], [0.75, "3/4"],
];

const SMALL_UNITS = new Set(["tsp", "tbsp"]);

const COUNTABLE_UNITS = new Set([
  "whole", "large", "medium", "small",
  "clove", "slice", "piece", "head", "bunch",
  "sprig", "can", "package", "stick", "handful",
]);

const NO_SCALE_UNITS = new Set(["pinch", "dash"]);

/**
 * Parse a human-written quantity string ("1", "1/2", "1 1/2", "½", "1½")
 * into a numeric value. Returns `null` for unparseable strings.
 */
export function parseQuantity(raw: string): number | null {
  let s = raw.trim();
  if (!s) return null;

  // Strip leading "~"
  s = s.replace(/^~\s*/, "");

  // Unicode fraction possibly preceded by a whole number: "1½"
  for (const [char, val] of Object.entries(UNICODE_FRACS)) {
    if (s.includes(char)) {
      const whole = s.replace(char, "").trim();
      return (whole ? Number(whole) : 0) + val;
    }
  }

  // Mixed fraction: "1 1/2"
  const mixedMatch = s.match(/^(\d+)\s+(\d+)\/(\d+)$/);
  if (mixedMatch) {
    return Number(mixedMatch[1]) + Number(mixedMatch[2]) / Number(mixedMatch[3]);
  }

  // Simple fraction: "1/2"
  const fracMatch = s.match(/^(\d+)\/(\d+)$/);
  if (fracMatch) {
    return Number(fracMatch[1]) / Number(fracMatch[2]);
  }

  // Plain number: "2", "2.5"
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

/**
 * Format a numeric quantity back into a human-friendly kitchen string.
 *
 * - Countable items (eggs, cloves): round to nearest whole number.
 * - Small measures (tsp, tbsp): snap to 1/4, 1/2, 3/4 only.
 * - Cups and other volume/weight: snap to 1/4, 1/3, 1/2, 2/3, 3/4.
 */
export function formatQuantity(value: number, isCountable: boolean, unit?: string): string {
  if (value <= 0) return "0";

  if (isCountable) {
    return String(Math.round(value) || 1);
  }

  const whole = Math.floor(value);
  const frac = value - whole;

  if (frac < 0.05) return String(whole || 1);
  if (frac > 0.95) return String(whole + 1);

  const table = SMALL_UNITS.has(unit ?? "") ? FRACS_COARSE : FRACS_STANDARD;

  let bestStr = "";
  let bestDist = Infinity;
  for (const [val, str] of table) {
    const dist = Math.abs(frac - val);
    if (dist < bestDist) {
      bestDist = dist;
      bestStr = str;
    }
  }

  return whole > 0 ? `${whole} ${bestStr}` : bestStr;
}

export type ScalableIngredient = {
  text: string;
  quantity?: string | number | null;
  unit?: string | null;
  section?: string | null;
  mappedIngredient?: { id: string; name: string; category: string } | null;
};

/**
 * Build a complete display line from structured ingredient fields.
 * If the text already starts with the quantity, returns it as-is.
 */
function buildDisplayText(text: string, qtyStr: string, unit?: string | null): string {
  const trimmed = text.trim();
  if (trimmed.startsWith(qtyStr)) return trimmed;

  const parts = [qtyStr, unit, trimmed].filter(Boolean);
  return parts.join(" ");
}

/**
 * Scale ingredient quantities for a new serving count.
 *
 * Returns a new array with updated `text` and `quantity` fields.
 * The original objects are not mutated.
 */
export function scaleIngredients<T extends ScalableIngredient>(
  ingredients: T[],
  baseServings: number,
  newServings: number,
): T[] {
  if (baseServings <= 0 || newServings <= 0) {
    return ingredients.map((ing) => ensureDisplayText(ing));
  }

  if (baseServings === newServings) {
    return ingredients.map((ing) => ensureDisplayText(ing));
  }

  const ratio = newServings / baseServings;

  return ingredients.map((ing) => {
    const qtyRaw = ing.quantity;
    if (qtyRaw == null || qtyRaw === "") return ensureDisplayText(ing);

    const unit = ing.unit?.toLowerCase() ?? "";

    if (NO_SCALE_UNITS.has(unit)) return ensureDisplayText(ing);

    const qtyStr = String(qtyRaw);
    const parsed = typeof qtyRaw === "number" ? qtyRaw : parseQuantity(qtyStr);
    if (parsed === null) return ensureDisplayText(ing);

    const scaled = parsed * ratio;
    const countable = !unit || COUNTABLE_UNITS.has(unit);
    const newQty = formatQuantity(scaled, countable, unit);

    const newText = rebuildIngredientText(ing.text, qtyStr, newQty, ing.unit);

    return { ...ing, quantity: newQty, text: newText };
  });
}

/**
 * Ensure an ingredient's text includes quantity and unit when they
 * are stored as separate fields (e.g. from image extraction).
 */
function ensureDisplayText<T extends ScalableIngredient>(ing: T): T {
  const qtyRaw = ing.quantity;
  if (qtyRaw == null || qtyRaw === "") return ing;

  const qtyStr = typeof qtyRaw === "number"
    ? formatQuantity(qtyRaw, false)
    : String(qtyRaw);

  const trimmedText = ing.text.trim();
  if (trimmedText.startsWith(qtyStr)) return ing;

  const newText = buildDisplayText(trimmedText, qtyStr, ing.unit);
  return { ...ing, text: newText };
}

/**
 * Replace the quantity portion at the start of an ingredient's display text.
 * When the text doesn't contain the old quantity (structured fields), builds
 * a new display string from the parts.
 */
function rebuildIngredientText(
  originalText: string,
  oldQty: string,
  newQty: string,
  unit?: string | null,
): string {
  if (!originalText || !oldQty) return originalText;

  const trimmedOld = oldQty.trim();
  const trimmedText = originalText.trim();

  // Text starts with the quantity — direct prefix replacement
  if (trimmedText.startsWith(trimmedOld)) {
    return newQty + trimmedText.slice(trimmedOld.length);
  }

  // Quantity found near the beginning (first 20 chars)
  const idx = trimmedText.indexOf(trimmedOld);
  if (idx !== -1 && idx < 20) {
    return trimmedText.slice(0, idx) + newQty + trimmedText.slice(idx + trimmedOld.length);
  }

  // Text is just the ingredient name (structured fields) — build full line
  return buildDisplayText(trimmedText, newQty, unit);
}

// ---------------------------------------------------------------------------
// Section / category grouping
// ---------------------------------------------------------------------------

export type IngredientGroup<T extends ScalableIngredient = ScalableIngredient> = {
  label: string;
  items: T[];
};

const CATEGORY_LABELS: Record<string, string> = {
  produce: "Produce",
  meat_seafood: "Meat & Seafood",
  dairy: "Dairy",
  grains_bread: "Grains & Bread",
  spices_seasoning: "Spices & Seasoning",
  oils_vinegars: "Oils & Vinegars",
  canned_jarred: "Canned & Jarred",
  frozen: "Frozen",
  baking: "Baking",
  nuts_seeds: "Nuts & Seeds",
  beverages: "Beverages",
  other: "Other",
};

/**
 * Group ingredients for display.
 *
 * - "category" mode: groups by mapped ingredient category (Dairy, Spices, etc.)
 *   Ideal for the recipe view — lets the user see all spices, all produce, etc.
 *   in one place for easy shopping / collection.
 *
 * - "section" mode: groups by recipe section (Biryani Masala, Rice, Layering).
 *   Ideal for editing — preserves the chef's recipe structure.
 *
 * Falls back to a flat list when no grouping data is available.
 */
export function groupIngredients<T extends ScalableIngredient>(
  ingredients: T[],
  mode: "category" | "section" = "category",
): IngredientGroup<T>[] {
  if (mode === "category") {
    return groupByCategory(ingredients);
  }
  return groupBySection(ingredients);
}

function groupByCategory<T extends ScalableIngredient>(
  ingredients: T[],
): IngredientGroup<T>[] {
  const hasCategories = ingredients.some((i) => i.mappedIngredient?.category);
  if (!hasCategories) return [{ label: "", items: ingredients }];

  const catMap = new Map<string, T[]>();
  for (const ing of ingredients) {
    const key = ing.mappedIngredient?.category ?? "other";
    const list = catMap.get(key) ?? [];
    list.push(ing);
    catMap.set(key, list);
  }

  const categoryOrder = Object.keys(CATEGORY_LABELS);
  const sorted = Array.from(catMap.entries()).sort(
    (a, b) => categoryOrder.indexOf(a[0]) - categoryOrder.indexOf(b[0]),
  );

  return sorted.map(([cat, items]) => ({
    label: CATEGORY_LABELS[cat] ?? cat,
    items,
  }));
}

function groupBySection<T extends ScalableIngredient>(
  ingredients: T[],
): IngredientGroup<T>[] {
  const hasSections = ingredients.some((i) => i.section);
  if (!hasSections) return [{ label: "", items: ingredients }];

  const sectionMap = new Map<string, T[]>();
  for (const ing of ingredients) {
    const key = ing.section ?? "Other";
    const list = sectionMap.get(key) ?? [];
    list.push(ing);
    sectionMap.set(key, list);
  }
  return Array.from(sectionMap.entries()).map(([label, items]) => ({
    label,
    items,
  }));
}
