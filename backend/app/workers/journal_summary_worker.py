"""Journal summary worker — regenerate the LLM summary for a recipe's journal entries.

Runs as an in-process background task via ``background_runner``.
"""

from __future__ import annotations

import structlog

from app.core.database import SessionLocal
from app.services.background_runner import enqueue

log = structlog.get_logger()


def regenerate_journal_summary_send(recipe_id: str) -> None:
    enqueue(_regenerate_journal_summary, recipe_id, task_name=f"journal-summary-{recipe_id}")


async def _regenerate_journal_summary(recipe_id: str) -> None:
    from app.core.llm import llm_chat
    from app.repositories import canonical_recipe_repo, journal_repo

    async with SessionLocal() as session:
        recipe = await canonical_recipe_repo.get_by_id(session, recipe_id)
        if recipe is None:
            log.warning("journal_summary_recipe_missing", recipe_id=recipe_id)
            return

        entries = await journal_repo.list_by_recipe(session, recipe_id, limit=50)
        if not entries:
            log.info("journal_summary_no_entries", recipe_id=recipe_id)
            return

        entry_texts = []
        for entry in entries:
            date_str = entry.cooked_on or entry.created_at.strftime("%Y-%m-%d")
            entry_texts.append(f"[{date_str}] {entry.body}")

        journal_block = "\n\n".join(entry_texts)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cooking assistant. Summarize the cook journal entries "
                    "for this recipe into a concise 2-4 sentence paragraph. "
                    "Highlight recurring themes, tips the cook discovered, and any "
                    "modifications they made. Be warm and practical."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Recipe: {recipe.title}\n\n"
                    f"Journal entries ({len(entries)} total):\n\n{journal_block}"
                ),
            },
        ]

        try:
            response = await llm_chat(messages, max_tokens=512, temperature=0.3)
            summary = response.text.strip()

            await canonical_recipe_repo.update_fields(
                session, recipe_id, journal_summary=summary,
            )
            await session.commit()
            log.info(
                "journal_summary_updated",
                recipe_id=recipe_id,
                entry_count=len(entries),
                summary_len=len(summary),
            )

            try:
                from app.repositories import recipe_search_index_repo
                from app.workers.search_index_worker import index_recipe_send
                await recipe_search_index_repo.mark_stale(
                    session, recipe_id, reason="journal_summary_updated"
                )
                await session.commit()
                index_recipe_send(recipe_id)
            except Exception:
                log.warning("search_index_trigger_failed", recipe_id=recipe_id, exc_info=True)
        except Exception:
            log.error("journal_summary_llm_failed", recipe_id=recipe_id, exc_info=True)
