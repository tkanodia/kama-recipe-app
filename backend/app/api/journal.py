"""Journal API — standalone routes for journal entry operations."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories import journal_repo

log = structlog.get_logger()
router = APIRouter(prefix="/journal", tags=["journal"])


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_journal_entry(
    request: Request,
    entry_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> None:
    entry = await journal_repo.get_by_id(db, entry_id)
    if entry is None or entry.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")

    recipe_id = entry.canonical_recipe_id
    await journal_repo.delete_entry(db, entry_id)
    await db.commit()

    try:
        from app.workers.journal_summary_worker import regenerate_journal_summary_send
        regenerate_journal_summary_send(recipe_id)
    except Exception:
        log.warning("journal_summary_dispatch_failed", recipe_id=recipe_id, exc_info=True)
