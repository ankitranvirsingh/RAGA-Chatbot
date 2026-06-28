"""
app/routers/chat.py
Public chat endpoints — no authentication required.

POST   /chat              → answer a question
DELETE /chat/{session_id} → clear chat history for a session
GET    /chat/{session_id}/history → view history
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.schemas import ChatRequest, ChatResponse, HistoryMessage, HistoryResponse
from app.services.chat_history import chat_history
from app.services.rag_pipeline import answer_question
from app.utils.logger import logger

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        return await answer_question(req.session_id, req.message)
    except Exception as e:
        logger.exception(f"Chat error for session={req.session_id}")
        raise HTTPException(status_code=500, detail=f"Chat error: {e}")


@router.delete("/{session_id}")
async def clear_session(session_id: str):
    await chat_history.clear(session_id)
    return {"session_id": session_id, "cleared": True}


@router.get("/{session_id}/history", response_model=HistoryResponse)
async def get_history(session_id: str):
    raw = await chat_history.get(session_id)
    messages = [HistoryMessage(role=m["role"], content=m["content"]) for m in raw]
    return HistoryResponse(session_id=session_id, history=messages)
