"""
app/services/vector_store.py
Thread-safe singleton wrapping ChromaDB + sentence-transformers.

Key fixes vs original:
  - __new__ / __init__ singleton pattern was broken (re-initialized on every call)
  - Using asyncio.get_event_loop().run_in_executor for CPU-bound embedding
  - Correct ChromaDB 0.5.x API (PersistentClient, no allow_reset needed)
  - Batch size capped to avoid OOM on free tier
  - query() returns similarity score (1 - cosine_distance)
"""
from __future__ import annotations

import asyncio
import threading
from typing import Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config import get_settings
from app.utils.logger import logger

settings = get_settings()

_EMBED_BATCH = 128   # tune down on low-RAM hosts
_INSERT_BATCH = 256  # ChromaDB insert batch


class VectorStore:
    """
    Process-wide singleton.
    Embedding model is loaded once per worker process (heavy: ~90 MB).
    All public methods are synchronous so they can be called from threads.
    Async wrappers in this module run them via run_in_executor.
    """

    _instance: Optional["VectorStore"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "VectorStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    obj = super().__new__(cls)
                    obj._initialized = False
                    cls._instance = obj
        return cls._instance

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return
            logger.info(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
            self._embedder = SentenceTransformer(settings.EMBEDDING_MODEL)

            logger.info(f"Opening ChromaDB at: {settings.CHROMA_PERSIST_DIR}")
            self._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"},
            )
            self._initialized = True
            logger.info(f"VectorStore ready — {self._collection.count()} chunks indexed")

    # ── embedding ─────────────────────────────────────────────────────────────

    def _embed(self, texts: List[str]) -> List[List[float]]:
        vecs = self._embedder.encode(
            texts,
            show_progress_bar=False,
            normalize_embeddings=True,
            batch_size=_EMBED_BATCH,
        )
        return vecs.tolist()

    # ── write ─────────────────────────────────────────────────────────────────

    def add_chunks(self, file_id: str, filename: str, chunks: List[Dict]) -> int:
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        embeddings = self._embed(texts)
        ids = [f"{file_id}_{i}" for i in range(len(chunks))]

        metadatas: List[Dict] = []
        for i, chunk in enumerate(chunks):
            md: Dict = {"file_id": file_id, "filename": filename, "chunk_index": i}
            for k, v in chunk.items():
                if k != "text":
                    md[k] = str(v)   # ChromaDB requires string metadata values
            metadatas.append(md)

        for start in range(0, len(ids), _INSERT_BATCH):
            end = start + _INSERT_BATCH
            self._collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=texts[start:end],
                metadatas=metadatas[start:end],
            )

        logger.info(f"Indexed {len(ids)} chunks — file_id={file_id} ({filename})")
        return len(ids)

    def delete_by_file(self, file_id: str) -> int:
        results = self._collection.get(where={"file_id": file_id})
        ids = results.get("ids", [])
        if ids:
            self._collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} chunks for file_id={file_id}")
        return len(ids)

    # ── read ──────────────────────────────────────────────────────────────────

    def query(self, question: str, top_k: int | None = None) -> List[Dict]:
        top_k = top_k or settings.TOP_K
        count = self._collection.count()
        if count == 0:
            return []
        n = min(top_k, count)
        q_emb = self._embed([question])[0]
        res = self._collection.query(
            query_embeddings=[q_emb],
            n_results=n,
            include=["documents", "metadatas", "distances"],
        )

        out: List[Dict] = []
        for i, doc_id in enumerate(res["ids"][0]):
            distance = res["distances"][0][i] if res.get("distances") else 0.0
            out.append({
                "id": doc_id,
                "text": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "score": round(1.0 - distance, 4),   # cosine similarity
            })
        return out

    def count(self) -> int:
        return self._collection.count()

    def health(self) -> bool:
        try:
            self._collection.count()
            return True
        except Exception:
            return False


# ── module-level singleton accessor ──────────────────────────────────────────

def get_vector_store() -> VectorStore:
    return VectorStore()


# ── async wrappers (run sync ops in thread pool) ──────────────────────────────

async def async_add_chunks(file_id: str, filename: str, chunks: List[Dict]) -> int:
    vs = get_vector_store()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vs.add_chunks, file_id, filename, chunks)


async def async_delete_by_file(file_id: str) -> int:
    vs = get_vector_store()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vs.delete_by_file, file_id)


async def async_query(question: str, top_k: int | None = None) -> List[Dict]:
    vs = get_vector_store()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vs.query, question, top_k)
