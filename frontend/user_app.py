"""
frontend/user_app.py
Streamlit chat UI — connects to FastAPI backend.
Run: streamlit run frontend/user_app.py
"""
from __future__ import annotations

import os
import uuid

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 60  # seconds — LLM can be slow on free tier

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Document Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── General ── */
.block-container { padding-top: 1.5rem; }

/* ── Chat bubbles ── */
.user-bubble {
    background: #1e3a5f;
    color: #cfe2ff;
    padding: 12px 16px;
    border-radius: 18px 18px 4px 18px;
    margin: 6px 0 6px auto;
    max-width: 80%;
    font-size: 0.92rem;
    line-height: 1.6;
}
.bot-bubble {
    background: #1e2433;
    color: #e2e8f0;
    border: 1px solid #2d3650;
    padding: 12px 16px;
    border-radius: 18px 18px 18px 4px;
    margin: 6px auto 6px 0;
    max-width: 80%;
    font-size: 0.92rem;
    line-height: 1.6;
}

/* ── Source chips ── */
.source-chip {
    display: inline-block;
    background: #1e2433;
    border: 1px solid #3d4f6b;
    color: #7aa2f7;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    margin: 2px 3px;
}

/* ── Status indicator ── */
.online-dot { color: #22c55e; font-size: 0.7rem; }

/* ── Sidebar ── */
section[data-testid="stSidebar"] > div { padding-top: 1rem; }
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


# ── Helpers ───────────────────────────────────────────────────────────────────
def _api_post(path: str, **kwargs):
    try:
        return requests.post(f"{API_URL}{path}", timeout=REQUEST_TIMEOUT, **kwargs)
    except requests.exceptions.ConnectionError:
        st.error(f"⚠️ Cannot connect to API at `{API_URL}`")
        return None


def _api_get(path: str, **kwargs):
    try:
        return requests.get(f"{API_URL}{path}", timeout=10, **kwargs)
    except requests.exceptions.ConnectionError:
        return None


def _api_delete(path: str, **kwargs):
    try:
        return requests.delete(f"{API_URL}{path}", timeout=10, **kwargs)
    except requests.exceptions.ConnectionError:
        return None


def _fmt_sources(sources: list) -> str:
    chips = []
    for s in sources[:5]:
        label = s["filename"]
        if s.get("page"):
            label += f" p.{s['page']}"
        elif s.get("sheet"):
            label += f" · {s['sheet']}"
        score = int(s["score"] * 100)
        chips.append(f'<span class="source-chip">📎 {label} ({score}%)</span>')
    return "".join(chips)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 💬 Document Assistant")

    # Health check
    health_r = _api_get("/")
    if health_r and health_r.ok:
        h = health_r.json()
        st.markdown(f'<span class="online-dot">●</span> Online — {h.get("total_chunks", 0)} chunks indexed', unsafe_allow_html=True)
        st.caption(f"Model: `{h.get('llm_model', '—')}`")
    else:
        st.error("⚠️ API offline")

    st.divider()

    # Session management
    st.markdown("### 🗂️ Session")
    st.code(f"ID: {st.session_state.session_id[:12]}…", language=None)

    if st.button("🔄 New Conversation", use_container_width=True):
        _api_delete(f"/chat/{st.session_state.session_id}")
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    # Show history count
    if st.session_state.messages:
        turns = len([m for m in st.session_state.messages if m["role"] == "user"])
        st.caption(f"{turns} question{'s' if turns != 1 else ''} in this session")

    st.divider()
    st.markdown("### 💡 Example questions")
    suggestions = [
        "What is the leave policy?",
        "Who does Alice report to?",
        "Summarize the uploaded documents",
        "Who are Bob's direct reports?",
        "What are the working hours?",
    ]
    for q in suggestions:
        if st.button(q, use_container_width=True, key=f"sug_{q}"):
            st.session_state._prefill = q

    st.divider()
    st.markdown("[Admin Panel →](http://localhost:8502)", unsafe_allow_html=True)
    st.caption("© DG Assistant")


# ── Main chat area ────────────────────────────────────────────────────────────
st.markdown("## 💬 Ask about your documents")

# Welcome message when empty
if not st.session_state.messages:
    st.info(
        "👋 Welcome! Upload documents via the **Admin Panel**, then ask anything here.\n\n"
        "Examples: *'What is the leave policy?'*, *'Who does Alice report to?'*, *'Summarize the data'*"
    )

# Render conversation
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(
            f'<div class="user-bubble">👤 {msg["content"]}</div>',
            unsafe_allow_html=True,
        )
    else:
        content_html = msg["content"].replace("\n", "<br>")
        st.markdown(
            f'<div class="bot-bubble">🤖 {content_html}</div>',
            unsafe_allow_html=True,
        )
        if msg.get("sources"):
            st.markdown(_fmt_sources(msg["sources"]), unsafe_allow_html=True)

# Handle suggestion click
prefill = st.session_state.pop("_prefill", None)

# Chat input
user_input = st.chat_input("Ask a question about your documents…")
question = user_input or prefill

if question:
    st.session_state.messages.append({"role": "user", "content": question})

    with st.spinner("Thinking…"):
        r = _api_post(
            "/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": question,
            },
        )

    if r is None:
        st.session_state.messages.append({
            "role": "assistant",
            "content": "⚠️ Could not reach the API. Please try again.",
            "sources": [],
        })
    elif not r.ok:
        st.session_state.messages.append({
            "role": "assistant",
            "content": f"⚠️ Error {r.status_code}: {r.text[:200]}",
            "sources": [],
        })
    else:
        data = r.json()
        st.session_state.messages.append({
            "role": "assistant",
            "content": data["answer"],
            "sources": data.get("sources", []),
        })

    st.rerun()
