"""
app/models/schemas.py
All Pydantic request/response schemas.
Uses snake_case throughout — consistent with FastAPI conventions.
"""
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: Optional[str] = None


class SourceChunk(BaseModel):
    filename: str
    snippet: str
    score: float
    page: Optional[int] = None
    sheet: Optional[str] = None
    row: Optional[int] = None


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceChunk]
    session_id: str


class HistoryMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    history: List[HistoryMessage]


# ── Files ─────────────────────────────────────────────────────────────────────

class FileMetadata(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    chunk_count: int
    uploaded_at: datetime
    description: Optional[str] = None


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    chunks_indexed: int
    message: str


class DeleteResponse(BaseModel):
    file_id: str
    deleted: bool
    chunks_removed: int
    message: str


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    chroma: bool
    redis: bool
    llm_model: str
    total_chunks: int
