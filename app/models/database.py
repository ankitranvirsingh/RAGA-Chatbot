"""
app/models/database.py
Async SQLite via aiosqlite + SQLAlchemy 2.x.
Stores file metadata so we can list/delete files independently of ChromaDB.
"""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


class FileRecord(Base):
    __tablename__ = "files"

    file_id = Column(String(64), primary_key=True)
    filename = Column(String(512), nullable=False)
    file_type = Column(String(16), nullable=False)
    size_bytes = Column(Integer, nullable=False)
    chunk_count = Column(Integer, default=0)
    description = Column(Text, nullable=True)
    uploaded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


# Engine — created lazily so tests can override SQLITE_PATH
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        db_url = f"sqlite+aiosqlite:///{settings.SQLITE_PATH}"
        _engine = create_async_engine(db_url, echo=False, future=True)
        _SessionLocal = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine, _SessionLocal


async def init_db() -> None:
    engine, _ = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:  # type: ignore[override]
    _, SessionLocal = _get_engine()
    async with SessionLocal() as session:
        yield session
