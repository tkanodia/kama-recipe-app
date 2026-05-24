"""Ask API — conversational recipe Q&A endpoints."""

import json

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.repositories import ask_session_repo
from app.services import ask_service

log = structlog.get_logger()
router = APIRouter(prefix="/ask", tags=["ask"])


class CreateAskBody(BaseModel):
    question: str
    recipeId: str | None = None


class SendMessageBody(BaseModel):
    question: str


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def create_session(
    request: Request,
    body: CreateAskBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    log.info("ask_session_create", user_id=user_id, recipe_id=body.recipeId)
    ask_session = await ask_session_repo.create_session(
        db, user_id=user_id, recipe_id=body.recipeId,
    )

    retrieved = await ask_service.retrieve_for_ask(
        question=body.question,
        session_messages=[],
        user_id=user_id,
        recipe_id=body.recipeId,
        db=db,
    )

    answer = await ask_service.generate_answer(
        question=body.question,
        retrieved_recipes=retrieved,
        session_messages=[],
        recipe_id=body.recipeId,
    )

    retrieved_ids = [r.id for r in retrieved]

    await ask_session_repo.add_message(
        db,
        ask_session_id=ask_session.id,
        role="user",
        content=body.question,
        retrieved_recipe_ids=retrieved_ids,
    )

    assistant_msg = await ask_session_repo.add_message(
        db,
        ask_session_id=ask_session.id,
        role="assistant",
        content=answer["content"],
        retrieved_recipe_ids=retrieved_ids,
        cited_recipe_ids=answer["citedRecipeIds"],
    )

    await db.commit()

    return {
        "sessionId": ask_session.id,
        "status": ask_session.status,
        "recipeId": ask_session.recipe_id,
        "message": {
            "id": assistant_msg.id,
            "role": "assistant",
            "content": answer["content"],
            "citedRecipeIds": answer["citedRecipeIds"],
            "createdAt": assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
        },
    }


@router.post("/sessions/{session_id}/messages")
@limiter.limit("60/minute")
async def send_message(
    request: Request,
    session_id: str,
    body: SendMessageBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    ask_session = await ask_session_repo.get_session(db, session_id)
    if ask_session is None or ask_session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if ask_session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session has been closed. Start a new conversation.",
        )

    log.info("ask_message_send", session_id=session_id, user_id=user_id)
    history = await ask_session_repo.list_messages(db, session_id)

    retrieved = await ask_service.retrieve_for_ask(
        question=body.question,
        session_messages=history,
        user_id=user_id,
        recipe_id=ask_session.recipe_id,
        db=db,
    )

    answer = await ask_service.generate_answer(
        question=body.question,
        retrieved_recipes=retrieved,
        session_messages=history,
        recipe_id=ask_session.recipe_id,
    )

    retrieved_ids = [r.id for r in retrieved]

    await ask_session_repo.add_message(
        db,
        ask_session_id=session_id,
        role="user",
        content=body.question,
        retrieved_recipe_ids=retrieved_ids,
    )

    assistant_msg = await ask_session_repo.add_message(
        db,
        ask_session_id=session_id,
        role="assistant",
        content=answer["content"],
        retrieved_recipe_ids=retrieved_ids,
        cited_recipe_ids=answer["citedRecipeIds"],
    )

    await ask_session_repo.update_last_active(db, session_id)
    await db.commit()

    return {
        "message": {
            "id": assistant_msg.id,
            "role": "assistant",
            "content": answer["content"],
            "citedRecipeIds": answer["citedRecipeIds"],
            "createdAt": assistant_msg.created_at.isoformat() if assistant_msg.created_at else None,
        },
    }


@router.post("/sessions/{session_id}/messages/stream")
@limiter.limit("60/minute")
async def send_message_stream(
    request: Request,
    session_id: str,
    body: SendMessageBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """SSE endpoint that streams assistant response tokens."""
    ask_session = await ask_session_repo.get_session(db, session_id)
    if ask_session is None or ask_session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if ask_session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This session has been closed. Start a new conversation.",
        )

    log.info("ask_message_stream", session_id=session_id, user_id=user_id)
    history = await ask_session_repo.list_messages(db, session_id)

    retrieved = await ask_service.retrieve_for_ask(
        question=body.question,
        session_messages=history,
        user_id=user_id,
        recipe_id=ask_session.recipe_id,
        db=db,
    )

    retrieved_ids = [r.id for r in retrieved]
    retrieved_id_set = set(retrieved_ids)

    await ask_session_repo.add_message(
        db,
        ask_session_id=session_id,
        role="user",
        content=body.question,
        retrieved_recipe_ids=retrieved_ids,
    )
    await db.commit()

    async def event_stream():
        full_text = ""
        try:
            async for chunk in ask_service.generate_answer_stream(
                question=body.question,
                retrieved_recipes=retrieved,
                session_messages=history,
                recipe_id=ask_session.recipe_id,
            ):
                full_text += chunk
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        except Exception as exc:
            log.error("ask_stream_error", error=str(exc))
            yield f"data: {json.dumps({'type': 'error', 'text': 'Generation failed'})}\n\n"

        cited_ids = ask_service.extract_cited_ids(full_text, retrieved_id_set)

        from app.core.database import SessionLocal
        async with SessionLocal() as save_db:
            assistant_msg = await ask_session_repo.add_message(
                save_db,
                ask_session_id=session_id,
                role="assistant",
                content=full_text,
                retrieved_recipe_ids=retrieved_ids,
                cited_recipe_ids=cited_ids,
            )
            await ask_session_repo.update_last_active(save_db, session_id)
            await save_db.commit()

        yield f"data: {json.dumps({'type': 'done', 'messageId': assistant_msg.id, 'citedRecipeIds': cited_ids})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/close")
@limiter.limit("60/minute")
async def close_session(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    ask_session = await ask_session_repo.get_session(db, session_id)
    if ask_session is None or ask_session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    await ask_session_repo.close_session(db, session_id)
    await db.commit()

    return {"sessionId": session_id, "status": "closed"}


@router.get("/sessions")
@limiter.limit("60/minute")
async def list_sessions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """List all sessions for the current user with first message as preview."""
    sessions = await ask_session_repo.list_sessions_by_user(db, user_id)
    items = []
    for s in sessions:
        messages = await ask_session_repo.list_messages(db, s.id)
        first_user_msg = next((m.content for m in messages if m.role == "user"), None)
        items.append({
            "sessionId": s.id,
            "status": s.status,
            "recipeId": s.recipe_id,
            "preview": (first_user_msg or "")[:80],
            "messageCount": len(messages),
            "createdAt": s.created_at.isoformat() if s.created_at else None,
            "lastActiveAt": s.last_active_at.isoformat() if s.last_active_at else None,
        })
    return {"items": items}


@router.get("/sessions/{session_id}")
@limiter.limit("60/minute")
async def get_session(
    request: Request,
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> dict:
    ask_session = await ask_session_repo.get_session(db, session_id)
    if ask_session is None or ask_session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    messages = await ask_session_repo.list_messages(db, session_id)

    return {
        "sessionId": ask_session.id,
        "status": ask_session.status,
        "recipeId": ask_session.recipe_id,
        "createdAt": ask_session.created_at.isoformat() if ask_session.created_at else None,
        "lastActiveAt": ask_session.last_active_at.isoformat() if ask_session.last_active_at else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "retrievedRecipeIds": m.retrieved_recipe_ids,
                "citedRecipeIds": m.cited_recipe_ids,
                "createdAt": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
    }
