"""
app/config.py
Central settings — loaded once via lru_cache.
All env var names use UPPER_SNAKE_CASE; pydantic-settings maps them automatically.
"""
from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── LLM ───────────────────────────────────────────────────────────────────
    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Admin Auth ─────────────────────────────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "changeme_in_production"
    SECRET_KEY: str = "insecure_default_change_me_32chars"

    # ── Storage ────────────────────────────────────────────────────────────────
    CHROMA_PERSIST_DIR: str = "./data/chromadb"
    UPLOAD_DIR: str = "./data/uploads"
    SQLITE_PATH: str = "./data/metadata.db"

    # ── Redis ──────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CHAT_HISTORY_TTL: int = 86400  # 24 h

    # ── Embedding ──────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # ── RAG ───────────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    TOP_K: int = 5
    MAX_FILE_SIZE_MB: int = 50

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── computed properties ───────────────────────────────────────────────────
    @property
    def allowed_origins_list(self) -> List[str]:
        if self.ALLOWED_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def max_file_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    def ensure_dirs(self) -> None:
        """Create all required directories at startup."""
        for d in [self.UPLOAD_DIR, self.CHROMA_PERSIST_DIR, "logs"]:
            Path(d).mkdir(parents=True, exist_ok=True)
        Path(self.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
