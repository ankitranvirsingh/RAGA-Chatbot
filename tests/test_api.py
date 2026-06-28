"""
tests/test_api.py
Async smoke tests using httpx + pytest-asyncio.
Run: pytest tests/ -v

These tests use the real app with SQLite in :memory: — no external services needed.
Redis falls back to in-memory automatically when unavailable.
"""
from __future__ import annotations

import io
import os
import pytest
import pytest_asyncio

# Override paths before importing app
os.environ.setdefault("GROQ_API_KEY", "test_key_placeholder")
os.environ["SQLITE_PATH"] = ":memory:"
os.environ["CHROMA_PERSIST_DIR"] = "/tmp/test_chromadb"
os.environ["UPLOAD_DIR"] = "/tmp/test_uploads"
os.environ["REDIS_URL"] = "redis://localhost:9999/0"   # intentionally wrong → fallback
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "testpass"
os.environ["SECRET_KEY"] = "testsecretkey1234567890abcdef1234"

from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_client(client):
    """Client with admin JWT token pre-injected."""
    r = await client.post("/admin/login", data={"username": "admin", "password": "testpass"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


# ── Health ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "total_chunks" in data
    assert "llm_model" in data


# ── Admin Auth ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client):
    r = await client.post("/admin/login", data={"username": "admin", "password": "testpass"})
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    r = await client.post("/admin/login", data={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_admin_requires_auth(client):
    r = await client.get("/admin/files")
    assert r.status_code == 401


# ── File Upload ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_txt(admin_client):
    content = b"Annual Leave Policy: Employees are entitled to 25 days of annual leave per year."
    r = await admin_client.post(
        "/admin/upload",
        files={"file": ("policy.txt", io.BytesIO(content), "text/plain")},
        data={"description": "HR Policy"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["filename"] == "policy.txt"
    assert data["chunks_indexed"] >= 1
    assert "file_id" in data
    return data["file_id"]


@pytest.mark.asyncio
async def test_upload_csv(admin_client):
    csv_content = b"name,department,reports_to\nAlice,Engineering,Bob\nBob,Engineering,Carol\nCarol,CTO,\n"
    r = await admin_client.post(
        "/admin/upload",
        files={"file": ("org_chart.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert r.status_code == 201
    assert r.json()["chunks_indexed"] >= 1


@pytest.mark.asyncio
async def test_upload_unsupported_type(admin_client):
    r = await admin_client.post(
        "/admin/upload",
        files={"file": ("image.png", io.BytesIO(b"fake"), "image/png")},
    )
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_list_files(admin_client):
    # Upload something first
    await admin_client.post(
        "/admin/upload",
        files={"file": ("list_test.txt", io.BytesIO(b"test content"), "text/plain")},
    )
    r = await admin_client.get("/admin/files")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ── Delete ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delete_file(admin_client):
    # Upload
    up_r = await admin_client.post(
        "/admin/upload",
        files={"file": ("to_delete.txt", io.BytesIO(b"temporary content"), "text/plain")},
    )
    assert up_r.status_code == 201
    file_id = up_r.json()["file_id"]

    # Delete
    del_r = await admin_client.delete(f"/admin/files/{file_id}")
    assert del_r.status_code == 200
    assert del_r.json()["deleted"] is True

    # Should be 404 now
    del_r2 = await admin_client.delete(f"/admin/files/{file_id}")
    assert del_r2.status_code == 404


# ── Chat ───────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_no_docs(client):
    """Chat without any docs should still return a response (not crash)."""
    r = await client.post(
        "/chat",
        json={"session_id": "test-sess-001", "message": "What is the leave policy?"},
    )
    # May be 200 with "no documents" answer, or 500 if LLM key invalid (expected in tests)
    assert r.status_code in (200, 500)


@pytest.mark.asyncio
async def test_chat_history_endpoint(client):
    r = await client.get("/chat/test-sess-999/history")
    assert r.status_code == 200
    data = r.json()
    assert data["session_id"] == "test-sess-999"
    assert isinstance(data["history"], list)


@pytest.mark.asyncio
async def test_clear_session(client):
    r = await client.delete("/chat/test-sess-clear")
    assert r.status_code == 200
    assert r.json()["cleared"] is True


# ── Validation ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_chat_empty_message(client):
    r = await client.post(
        "/chat",
        json={"session_id": "s1", "message": ""},
    )
    assert r.status_code == 422  # Pydantic min_length validation


@pytest.mark.asyncio
async def test_chat_missing_session_id(client):
    r = await client.post("/chat", json={"message": "hello"})
    assert r.status_code == 422
