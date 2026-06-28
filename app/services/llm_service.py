"""
app/services/llm_service.py
Groq async LLM client with retry and structured prompt.

Key fixes vs original:
  - AsyncGroq(api_key=...) not apikey
  - max_tokens not maxtokens
  - system prompt kept out of history injection (always first)
  - history slice is last N messages, not last N*2
  - tenacity retry with correct import path
"""
from __future__ import annotations

from typing import Dict, List

from groq import AsyncGroq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.utils.logger import logger

settings = get_settings()

SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions using ONLY the context retrieved from uploaded documents.

Rules:
1. Base every answer strictly on the "Context" section below.
2. If the answer is not in the context, reply: "I couldn't find that information in the uploaded documents."
3. For tabular data (CSV/Excel), reason carefully over key:value rows.
   — For "who does X report to?": look for the row where the name column equals X and read the manager/reports_to column.
   — For "who reports to Y?": find rows where the manager column equals Y and list those names.
4. Use prior conversation turns to resolve pronouns ("he", "that policy", "explain it further").
5. Be concise and factual. Mention the source filename when it adds clarity.
6. For follow-up questions like "explain more", re-use context from previous turns already in your memory.
"""


class LLMService:
    def __init__(self) -> None:
        self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    async def chat(
        self,
        question: str,
        context_chunks: List[Dict],
        history: List[Dict],
    ) -> str:
        """
        Build prompt and call Groq.
        context_chunks: list of {"text", "metadata", "score"} from vector store
        history: list of {"role", "content"} messages (alternating user/assistant)
        """
        # Build context block
        context_parts: List[str] = []
        for chunk in context_chunks:
            meta = chunk.get("metadata", {})
            src = meta.get("filename", "unknown")
            loc_parts = []
            if meta.get("page"):
                loc_parts.append(f"page {meta['page']}")
            if meta.get("sheet"):
                loc_parts.append(f"sheet '{meta['sheet']}'")
            if meta.get("row") and str(meta.get("row")) != "0":
                loc_parts.append(f"row {meta['row']}")
            loc = ", ".join(loc_parts)
            header = f"[Source: {src}{' — ' + loc if loc else ''}]"
            context_parts.append(f"{header}\n{chunk['text']}")

        context_text = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant context found."

        # Build message list
        messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Inject last 12 history messages (6 turns) for conversational memory
        messages.extend(history[-12:])

        # Current user message with context injected
        messages.append({
            "role": "user",
            "content": (
                f"Context from uploaded documents:\n\n{context_text}\n\n"
                f"---\n\nQuestion: {question}"
            ),
        })

        response = await self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()
        logger.debug(f"LLM answer ({response.usage.total_tokens} tokens): {answer[:80]}…")
        return answer

    async def health(self) -> bool:
        try:
            await self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.warning(f"LLM health check failed: {e}")
            return False


# Module-level singleton
llm_service = LLMService()
