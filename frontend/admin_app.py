"""
frontend/admin_app.py
Streamlit admin panel — JWT login, upload, list, delete files.
Run: streamlit run frontend/admin_app.py --server.port 8502
"""
from __future__ import annotations

import os
from typing import Optional

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Admin Panel — RAG Chatbot",
    page_icon="🛠️",
    layout="wide",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 1.5rem; }
.file-row {
    background: #1a1d27;
    border: 1px solid #2d3148;
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
}
.badge {
    display: inline-block;
    background: #1e2a3d;
    color: #7aa2f7;
    border: 1px solid #3d5070;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
}
.success-banner {
    background: rgba(34,197,94,.12);
    border: 1px solid rgba(34,197,94,.3);
    color: #22c55e;
    padding: 12px 16px;
    border-radius: 10px;
    margin: 8px 0;
}
.error-banner {
    background: rgba(239,68,68,.12);
    border: 1px solid rgba(239,68,68,.3);
    color: #ef4444;
    padding: 12px 16px;
    border-radius: 10px;
    margin: 8px 0;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "admin_token" not in st.session_state:
    st.session_state.admin_token = None


# ── Auth helpers ──────────────────────────────────────────────────────────────

def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.admin_token}"}


def _api(method: str, path: str, **kwargs) -> Optional[requests.Response]:
    try:
        return requests.request(
            method, f"{API_URL}{path}", timeout=120, **kwargs
        )
    except requests.exceptions.ConnectionError:
        st.error(f"Cannot connect to API at `{API_URL}`")
        return None


def _fmt_size(b: int) -> str:
    if b < 1024:
        return f"{b} B"
    if b < 1024 ** 2:
        return f"{b / 1024:.1f} KB"
    return f"{b / 1024 ** 2:.1f} MB"


def _file_icon(ext: str) -> str:
    return {
        "pdf": "📄", "csv": "📊", "xlsx": "📊", "xls": "📊",
        "docx": "📝", "doc": "📝", "pptx": "📋", "ppt": "📋",
        "txt": "📃", "md": "📃", "json": "🔧",
    }.get(ext.lower(), "📁")


# ── Login screen ──────────────────────────────────────────────────────────────

if not st.session_state.admin_token:
    st.markdown("## 🛠️ Admin Panel")
    st.markdown("Sign in with your admin credentials.")

    col1, col2, col3 = st.columns([1, 1.4, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", value="admin")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In →", use_container_width=True)

        if submitted:
            r = _api("POST", "/admin/login", data={"username": username, "password": password})
            if r and r.ok:
                st.session_state.admin_token = r.json()["access_token"]
                st.success("✅ Logged in successfully!")
                st.rerun()
            elif r:
                st.error(f"❌ {r.json().get('detail', 'Login failed')}")

    st.stop()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🛠️ Admin Panel")

    # Health
    hr = _api("GET", "/")
    if hr and hr.ok:
        h = hr.json()
        st.success("● API Online")
        st.metric("Total Chunks", h.get("total_chunks", 0))
        st.metric("Redis", "✅" if h.get("redis") else "⚠️ fallback")
        st.caption(f"LLM: `{h.get('llm_model', '—')}`")
    else:
        st.error("⚠️ API Offline")

    st.divider()
    st.markdown("[💬 Open Chat UI →](http://localhost:8501)")

    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.admin_token = None
        st.rerun()


# ── Main content ──────────────────────────────────────────────────────────────
st.markdown("## 🛠️ Document Admin Panel")

tab_upload, tab_files = st.tabs(["⬆️ Upload Documents", "📁 Manage Files"])


# ── Upload tab ────────────────────────────────────────────────────────────────
with tab_upload:
    st.markdown("### Upload & Index New Document")
    st.caption("Supported: PDF, CSV, Excel (.xlsx/.xls), Word (.docx), PowerPoint (.pptx), TXT, MD, JSON — max 50 MB each")

    uploaded_files = st.file_uploader(
        "Choose files",
        type=["pdf", "csv", "xlsx", "xls", "docx", "doc", "pptx", "ppt", "txt", "md", "json"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    description = st.text_input(
        "Description (optional)",
        placeholder="e.g. HR Policy 2025, Employee Org Chart Q1",
    )

    if uploaded_files:
        st.markdown(f"**{len(uploaded_files)} file(s) selected**")
        for f in uploaded_files:
            size = _fmt_size(len(f.getvalue()))
            ext = f.name.rsplit(".", 1)[-1] if "." in f.name else "?"
            st.caption(f"{_file_icon(ext)} {f.name} — {size}")

    col_a, col_b = st.columns([2, 5])
    upload_clicked = col_a.button(
        "⬆️ Upload & Index",
        use_container_width=True,
        disabled=not uploaded_files,
    )

    if upload_clicked and uploaded_files:
        progress = st.progress(0, text="Starting upload…")
        results_placeholder = st.empty()
        results_html = []

        for i, f in enumerate(uploaded_files):
            progress.progress((i) / len(uploaded_files), text=f"Uploading {f.name}…")
            r = _api(
                "POST",
                "/admin/upload",
                headers=_auth_headers(),
                files={"file": (f.name, f.getvalue(), f.type or "application/octet-stream")},
                data={"description": description},
            )
            if r and r.ok:
                d = r.json()
                results_html.append(
                    f'<div class="success-banner">✅ <b>{f.name}</b> — {d["chunks_indexed"]} chunks indexed</div>'
                )
            else:
                err = r.json().get("detail", r.text) if r else "Connection error"
                results_html.append(
                    f'<div class="error-banner">❌ <b>{f.name}</b>: {err}</div>'
                )

        progress.progress(1.0, text="Done!")
        results_placeholder.markdown("\n".join(results_html), unsafe_allow_html=True)


# ── Manage files tab ──────────────────────────────────────────────────────────
with tab_files:
    st.markdown("### Indexed Documents")

    col_r, col_s = st.columns([1, 4])
    if col_r.button("↻ Refresh", use_container_width=True):
        st.rerun()

    search_q = col_s.text_input("🔍 Filter by filename", placeholder="Type to filter…", label_visibility="collapsed")

    r = _api("GET", "/admin/files", headers=_auth_headers())
    if r is None:
        st.stop()

    if not r.ok:
        st.error(f"Error loading files: {r.text}")
        st.stop()

    files = r.json()
    if search_q:
        files = [f for f in files if search_q.lower() in f["filename"].lower()]

    if not files:
        st.info("📭 No documents indexed yet. Use the **Upload** tab to add some.")
    else:
        st.caption(f"Showing {len(files)} document(s)")

        # Table header
        hc = st.columns([3.5, 1, 1, 1.5, 1.5, 1])
        for col, label in zip(hc, ["Filename", "Type", "Chunks", "Size", "Uploaded", "Action"]):
            col.markdown(f"**{label}**")
        st.divider()

        for doc in files:
            ext = doc["file_type"]
            icon = _file_icon(ext)
            uploaded = doc["uploaded_at"][:10]
            size = _fmt_size(doc["size_bytes"])

            cols = st.columns([3.5, 1, 1, 1.5, 1.5, 1])
            cols[0].markdown(f"{icon} **{doc['filename']}**")
            cols[1].markdown(f'<span class="badge">{ext.upper()}</span>', unsafe_allow_html=True)
            cols[2].write(doc["chunk_count"])
            cols[3].write(size)
            cols[4].write(uploaded)

            if cols[5].button("🗑️", key=f"del_{doc['file_id']}", help=f"Delete {doc['filename']}"):
                dr = _api(
                    "DELETE",
                    f"/admin/files/{doc['file_id']}",
                    headers=_auth_headers(),
                )
                if dr and dr.ok:
                    d = dr.json()
                    st.success(d["message"])
                    st.rerun()
                elif dr:
                    st.error(f"Delete failed: {dr.json().get('detail', dr.text)}")

            # Optional description
            if doc.get("description"):
                st.caption(f"  ↳ {doc['description']}")
