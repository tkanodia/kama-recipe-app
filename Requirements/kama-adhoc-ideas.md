# Kama — Adhoc Ideas & Brain Dump

**Purpose:** Parking lot for raw ideas. Not groomed, not committed. Revisit periodically and promote worthy ideas into the PRD or backlog.

---

1. **Recipe share on social media** — Let users share a recipe as a beautiful social card/story, pulling in photos from their cook journal entries. The shared format should look polished enough for Instagram/WhatsApp/iMessage — hero image or journal photo, recipe title, key stats (cook time, servings), and a link back to Kama. Could generate an image or use Open Graph previews.

2. **Serving size adjuster with quantity scaling** — On recipe detail, let user change serving count and auto-recalculate all ingredient quantities proportionally. Requires parsed numeric quantities — could leverage the quantity string field and do best-effort parsing. Handle edge cases like "a pinch" or "to taste" by leaving them unchanged. Similar to how recipe widgets work on cooking sites.

3. **Utensils / appliances section on recipe detail** — Show what kitchen tools are needed (oven, blender, cast iron pan, baking sheet, etc.). Infer from recipe steps during extraction or review agent phase if not explicitly mentioned in source. "Simmer for 20 mins" implies a pot + stovetop. "Blend until smooth" implies a blender. Could be a lightweight LLM inference added to the review agent's checklist, stored as an optional field on the canonical recipe.

4. **Multi-image/video social media post ingestion** — Handle social posts (Instagram carousels, TikTok slideshows) where a single recipe is spread across multiple images or videos in one post. The ingestion agent would need to recognize the post is a carousel, download all slides, process each for recipe content (OCR per image, combine text across slides), and merge into one recipe candidate. Also covers posts where recipe ingredients are in slide 1, steps in slide 2, plating in slide 3, etc.

5. **Explore Provecho for UX inspiration** — https://www.provecho.co/platform — Review their platform for ideas on recipe UX patterns, feature set, and interaction design. Add relevant findings to the Mobbin reference library during Phase 1 of the design pipeline.

6. **Grocery app integration** — Connect shopping lists with grocery delivery/pickup apps (Whole Foods, Jewel-Osco, Instacart, etc.) so users can send their list directly to a store for ordering. Could use Instacart's API or deep-link into store apps with pre-filled cart items. Map Kama ingredient names to store product catalog entries.
