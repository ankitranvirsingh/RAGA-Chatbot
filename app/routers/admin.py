"""
app/routers/admin.py
Admin endpoints — all protected by JWT Bearer token.

POST   /admin/login          → get JWT token
POST   /admin/upload         → upload + index file
GET    /admin/files          → list indexed files
DELETE /admin/files/{file_id} → delete file + its vectors

Key fixes vs original:
  - Added /admin/login endpoint (was missing entirely)
  - SQLAlchemy 2.x uses scalars().all() not scalars().all() (same, but select() fixed)
  - FileRecord column mapping via __table__.columns (original had dict comprehension bug)
  - Physical file deletion uses stored extension from DB record
  - Proper HTTP status codes (201 for upload)
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException,
    UploadFile, status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import create_access_token, verify_admin
from app.models.database import FileRecord, get_db
from app.models.schemas import (
    DeleteResponse, FileMetadata, TokenResponse, UploadResponse,
)
from app.services.file_loader import SUPPORTED_EXTENSIONS, extract_chunks, save_upload
from app.services.vector_store import async_add_chunks, async_delete_by_file
from app.utils.logger import logger

settings = get_settings()
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Login (public — no auth required) ────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def admin_login(form_data: OAuth2PasswordRequestForm = Depends()):
    if (
        form_data.username != settings.ADMIN_USERNAME
        or form_data.password != settings.ADMIN_PASSWORD
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token = create_access_token(form_data.username)
    return TokenResponse(access_token=token)


# ── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    description: str = Form(default=""),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin),
):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > settings.max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB} MB limit",
        )

    file_id, path = save_upload(content, file.filename)

    try:
        chunks = extract_chunks(path)
    except Exception as e:
        Path(path).unlink(missing_ok=True)
        logger.exception(f"Extraction failed for {file.filename}")
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {e}")

    try:
        chunk_count = await async_add_chunks(file_id, file.filename, chunks)
    except Exception as e:
        Path(path).unlink(missing_ok=True)
        logger.exception("Vector store insert failed")
        raise HTTPException(status_code=500, detail=f"Indexing failed: {e}")

    record = FileRecord(
        file_id=file_id,
        filename=file.filename,
        file_type=ext.lstrip("."),
        size_bytes=len(content),
        chunk_count=chunk_count,
        description=description or None,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(record)
    await db.commit()

    logger.info(f"Uploaded & indexed: {file.filename} ({chunk_count} chunks)")
    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        chunks_indexed=chunk_count,
        message="File uploaded and indexed successfully.",
    )


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("/files", response_model=list[FileMetadata])
async def list_files(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin),
):
    result = await db.execute(
        select(FileRecord).order_by(FileRecord.uploaded_at.desc())
    )
    rows = result.scalars().all()
    return [
        FileMetadata(
            file_id=r.file_id,
            filename=r.filename,
            file_type=r.file_type,
            size_bytes=r.size_bytes,
            chunk_count=r.chunk_count,
            uploaded_at=r.uploaded_at,
            description=r.description,
        )
        for r in rows
    ]


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/files/{file_id}", response_model=DeleteResponse)
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(verify_admin),
):
    result = await db.execute(
        select(FileRecord).where(FileRecord.file_id == file_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")

    # 1. Delete vectors from ChromaDB
    chunks_removed = await async_delete_by_file(file_id)

    # 2. Delete physical file
    physical_path = Path(settings.UPLOAD_DIR) / f"{file_id}.{record.file_type}"
    physical_path.unlink(missing_ok=True)

    # 3. Delete metadata from SQLite
    await db.execute(delete(FileRecord).where(FileRecord.file_id == file_id))
    await db.commit()

    logger.info(f"Deleted file {record.filename} ({chunks_removed} chunks removed)")
    return DeleteResponse(
        file_id=file_id,
        deleted=True,
        chunks_removed=chunks_removed,
        message=f"'{record.filename}' and {chunks_removed} vector chunks deleted.",
    )
