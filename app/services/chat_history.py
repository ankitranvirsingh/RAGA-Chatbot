"""
app/services/chat_history.py
Redis-backed chat history with automatic in-memory fallback.

Key fixes vs original:
  - redis.asyncio.from_url (not redis.from_url)
  - aclose() → aclose() correct on newer redis-py
  - fallback dict uses asyncio.Lock (not threading.Lock) for async safety
  - MAX_TURNS was applied incorrectly (now keeps last N role-pairs = 2N messages)
  - TTL is refreshed on every write (sliding window)
"""
from __future__ import annotations

import asyncio
import json
from typing import Dict, List, Optional

from app.config import get_settings
from app.utils.logger import logger

settings = get_settings()

MAX_TURNS = 20   # store last 20 user/assistant pairs → 40 messages max


class ChatHistory:
    def __init__(self) -> None:
        self._redis: Optional[object] = None          # redis.asyncio.Redis
        self._fallback: Dict[str, List[Dict]] = {}
        self._lock = asyncio.Lock()
        self._redis_available = False

    async def connect(self) -> None:
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await client.ping()
            self._redis = client
            self._redis_available = True
            logger.info(f"Redis connected: {settings.REDIS_URL}")
        except Exception as e:
            logger.warning(f"Redis unavailable ({e}). Using in-memory fallback.")
            self._redis = None
            self._redis_available = False

    async def close(self) -> None:
        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

    # ── key ──────────────────────────────────────────────────────────────────

    @staticmethod
    def _key(session_id: str) -> str:
        return f"chat_history:{session_id}"

    # ── public API ────────────────────────────────────────────────────────────

    async def get(self, session_id: str) -> List[Dict]:
        """Return full message list for this session."""
        if self._redis_available and self._redis:
            try:
                raw = await self._redis.get(self._key(session_id))
                return json.loads(raw) if raw else []
            except Exception as e:
                logger.warning(f"Redis GET failed: {e}")
        async with self._lock:
            return list(self._fallback.get(session_id, []))

    async def append(self, session_id: str, role: str, content: str) -> None:
        """Append one message and trim to MAX_TURNS."""
        history = await self.get(session_id)
        history.append({"role": role, "content": content})
        # Keep last MAX_TURNS * 2 messages (role pairs)
        history = history[-(MAX_TURNS * 2):]

        if self._redis_available and self._redis:
            try:
                await self._redis.setex(
                    self._key(session_id),
                    settings.CHAT_HISTORY_TTL,
                    json.dumps(history),
                )
                return
            except Exception as e:
                logger.warning(f"Redis SET failed: {e}")

        async with self._lock:
            self._fallback[session_id] = history

    async def clear(self, session_id: str) -> None:
        if self._redis_available and self._redis:
            try:
                await self._redis.delete(self._key(session_id))
            except Exception as e:
                logger.warning(f"Redis DELETE failed: {e}")
        async with self._lock:
            self._fallback.pop(session_id, None)

    async def health(self) -> bool:
        if not self._redis_available or not self._redis:
            return False
        try:
            await self._redis.ping()
            return True
        except Exception:
            return False


# Module-level singleton
chat_history = ChatHistory()
