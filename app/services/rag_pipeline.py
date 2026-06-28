"""
app/services/rag_pipeline.py
Orchestrates: history retrieval → context retrieval → LLM → history update.

Key improvement:
  For short follow-up questions ("explain more", "who else?"), we prepend the
  last user message to the retrieval query so ChromaDB finds relevant chunks
  even when the follow-up has no standalone meaning.
"""
from __future__ import annotations

from app.models.schemas import ChatResponse, SourceChunk
from app.services.chat_history import chat_history
from app.services.llm_service import llm_service
from app.services.vector_store import async_query
from app.utils.logger import logger

# If the question is shorter than this many words, treat as follow-up
_FOLLOWUP_WORD_THRESHOLD = 8


async def answer_question(session_id: str, question: str) -> ChatResponse:
    # 1. Load conversation history
    history = await chat_history.get(session_id)

    # 2. Build retrieval query (history-aware for follow-ups)
    retrieval_query = question
    if history and len(question.split()) < _FOLLOWUP_WORD_THRESHOLD:
        last_user_msg = next(
            (m["content"] for m in reversed(history) if m["role"] == "user"),
            "",
        )
        if last_user_msg:
            retrieval_query = f"{last_user_msg} {question}"
            logger.debug(f"Follow-up detected — expanded query: {retrieval_query[:80]}")

    # 3. Retrieve context
    chunks = await async_query(retrieval_query)
    logger.info(f"Retrieved {len(chunks)} chunks for session={session_id[:8]}")

    # 4. Call LLM
    answer = await llm_service.chat(question, chunks, history)

    # 5. Persist history
    await chat_history.append(session_id, "user", question)
    await chat_history.append(session_id, "assistant", answer)

    # 6. Build source citations
    sources = [
        SourceChunk(
            filename=c["metadata"].get("filename", "unknown"),
            snippet=(c["text"][:200] + "…") if len(c["text"]) > 200 else c["text"],
            score=c["score"],
            page=int(c["metadata"]["page"]) if c["metadata"].get("page") else None,
            sheet=c["metadata"].get("sheet"),
            row=int(c["metadata"]["row"]) if c["metadata"].get("row") and c["metadata"]["row"] != "0" else None,
        )
        for c in chunks
    ]

    return ChatResponse(answer=answer, sources=sources, session_id=session_id)
