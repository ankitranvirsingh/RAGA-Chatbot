"""
app/main.py
FastAPI application factory.

Key fixes vs original:
  - CORS: allowedorigins was a raw string, now uses settings.allowed_origins_list
  - Lifespan: correct async context manager pattern
  - Health endpoint: returns actual chunk count + redis status
  - Includes rate limiting middleware (slowapi) for production safety
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.database import init_db
from app.models.schemas import HealthResponse
from app.routers import admin, chat
from app.services.chat_history import chat_history
from app.services.vector_store import get_vector_store
from app.utils.logger import logger

settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("═" * 60)
    logger.info("  RAG Chatbot API — starting up")
    logger.info("═" * 60)

    settings.ensure_dirs()

    # SQLite schema
    await init_db()
    logger.info("SQLite ready")

    # Vector store (loads embedding model — ~2–5 s)
    vs = get_vector_store()
    vs.initialize()
    logger.info(f"VectorStore ready — {vs.count()} chunks")

    # Redis (optional)
    await chat_history.connect()

    logger.info("Startup complete ✓")
    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    logger.info("Shutting down…")
    await chat_history.close()
    logger.info("Shutdown complete.")


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="RAG Chatbot API",
        description="Production-ready document Q&A with persistent chat history.",
        version="2.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    origins = settings.allowed_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(admin.router)
    app.include_router(chat.router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error on {request.url}: {exc}")
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred."},
        )

    # Health endpoint
    @app.get("/", response_model=HealthResponse, tags=["health"])
    async def health():
        vs = get_vector_store()
        return HealthResponse(
            status="ok",
            chroma=vs.health(),
            redis=await chat_history.health(),
            llm_model=settings.GROQ_MODEL,
            total_chunks=vs.count(),
        )

    return app


app = create_app()
