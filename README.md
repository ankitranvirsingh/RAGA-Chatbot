# 🤖 RAGA Chatbot — Retrieval-Augmented Generation Assistant

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Groq-LLaMA_3.3_70B-FF6B35?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/ChromaDB-0.5.15-orange?style=for-the-badge"/>
  <img src="https://img.shields.io/badge/Streamlit-1.39-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white"/>
  <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge"/>
</p>

<p align="center">
  A <strong>production-ready</strong> document Q&A chatbot that lets you upload any files via an admin panel and instantly answer natural language questions — grounded strictly in your documents, with full conversation memory and support for <strong>1000+ concurrent users</strong>.
</p>

---

## 🧠 How It Works — RAG Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        INGESTION PIPELINE                       │
│                                                                 │
│  Upload File → File Dispatcher → Format-Specific Loader         │
│                                (PDF / CSV / Excel /             │
│                                 DOCX / PPTX / TXT / JSON)       │
│                                         ↓                       │
│                              Smart Text Chunker                 │
│                          (800 words, 100 word overlap)          │
│                                         ↓                       │
│                    all-MiniLM-L6-v2 (Local Embeddings)          │
│                         (384-dim, zero API cost)                │
│                                         ↓                       │
│                        ChromaDB Vector Store                    │
│                          (persisted to disk)                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                         QUERY PIPELINE                          │
│                                                                 │
│  User Question → History-Aware Retrieval Query                  │
│                                ↓                                │
│              ChromaDB Cosine Similarity Search                  │
│                Top-K Relevant Chunks Retrieved                  │
│                                ↓                                │
│         System Prompt + Redis Chat History + Context            │
│                                ↓                                │
│              Groq API — LLaMA 3.3 70B (Free Tier)               │
│                                ↓                                │
│              Grounded Answer + Source Citations                 │
└─────────────────────────────────────────────────────────────────┘
```

### Why RAG?

Standard LLMs answer from general training data — they know nothing about *your* company's leave policy, org structure, or internal data. RAGA solves this by:

1. **Retrieving** the most semantically relevant sections from *your* uploaded documents
2. **Augmenting** the LLM prompt with that specific context
3. **Generating** an answer grounded only in what was retrieved — never hallucinated

---

## ✨ Features

- 📄 **Multi-Format Ingestion** — PDF, Excel (multi-sheet), CSV, Word (.docx), PowerPoint (.pptx), TXT, JSON
- 🏢 **Org Hierarchy Detection** — auto-detects `reports_to` / `manager` columns in Excel/CSV and builds searchable hierarchy text
- 💬 **Persistent Chat Memory** — Redis-backed conversation history with TTL; falls back to in-memory automatically
- 🔐 **JWT Admin Authentication** — secure token-based login for the admin panel (8-hour expiry)
- 🗑️ **Full Vector Cleanup** — delete any file and all its vector chunks recursively in one click
- 📍 **Source Citations** — every answer shows the source filename, page number, and relevance score
- ⚡ **1000+ Concurrent Users** — FastAPI async + 4 uvicorn workers + thread-pool for CPU-bound tasks
- 🐳 **Docker Ready** — one command brings up API + Redis + Chat UI + Admin UI
- ☁️ **Free Cloud Deploy** — Render.com blueprint included (`render.yaml`)
- 🧪 **Test Suite** — pytest-asyncio smoke tests covering all endpoints

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **LLM** | Groq API — `llama-3.3-70b-versatile` | Answer generation (~500 tok/s, free tier) |
| **Embeddings** | `all-MiniLM-L6-v2` via sentence-transformers | Local 384-dim embeddings, zero API cost |
| **Vector DB** | ChromaDB 0.5.15 | Cosine similarity search, per-file deletion |
| **Chat History** | Redis 7 + in-memory fallback | Session memory with sliding TTL |
| **Backend** | FastAPI 0.115 + uvicorn | Async REST API, 1000+ concurrent connections |
| **Auth** | JWT (python-jose) + bcrypt | Secure admin token authentication |
| **File Metadata** | SQLite + SQLAlchemy async | Lightweight file registry |
| **PDF Parsing** | pypdf | Page-level text extraction |
| **Tabular Data** | pandas + openpyxl + xlrd | CSV and Excel row-level parsing |
| **Word Docs** | python-docx | Paragraph extraction |
| **Presentations** | python-pptx | Slide-level text extraction |
| **Frontend** | Streamlit 1.39 | Chat UI + Admin Panel |
| **Logging** | Loguru | Structured JSON logs with rotation |
| **Resilience** | tenacity | Auto-retry on Groq API errors |

---

## 📁 Project Structure

```
raga-chatbot/
├── app/
│   ├── main.py                  # FastAPI app factory + lifespan hooks
│   ├── config.py                # Centralised settings (pydantic-settings)
│   ├── dependencies.py          # JWT auth dependency + token creation
│   ├── routers/
│   │   ├── admin.py             # /admin/login, /admin/upload, /admin/files
│   │   └── chat.py              # /chat, /chat/{session}/history
│   ├── services/
│   │   ├── file_loader.py       # Format dispatchers + hierarchy detection
│   │   ├── vector_store.py      # ChromaDB singleton (thread-safe)
│   │   ├── chat_history.py      # Redis + in-memory fallback
│   │   ├── llm_service.py       # Groq async client with retry
│   │   └── rag_pipeline.py      # Retrieval + generation orchestration
│   ├── models/
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   └── database.py          # SQLAlchemy async SQLite
│   └── utils/
│       └── logger.py            # Loguru structured logging
├── frontend/
│   ├── user_app.py              # Streamlit chat UI
│   └── admin_app.py             # Streamlit admin panel
├── tests/
│   └── test_api.py              # pytest-asyncio smoke tests
├── data/
│   ├── uploads/                 # Raw uploaded files
│   └── chromadb/                # Persisted vector store
├── .env.example                 # Environment variable template
├── requirements.txt
├── Dockerfile                   # Multi-stage, pre-downloads model
├── docker-compose.yml           # API + Redis + 2 Streamlit UIs
├── render.yaml                  # One-click Render.com blueprint
└── Procfile                     # Heroku / single-dyno Render
```

---

## 🚀 Quick Start

---

### Option 1 — Run Locally (Python)

#### Prerequisites

- **Python 3.11** — [Download here](https://www.python.org/downloads/release/python-3119/)
  - ⚠️ Python 3.12+ may have package compatibility issues — use 3.11 exactly
- **Git** — [Download here](https://git-scm.com/downloads)
- **Groq API Key** — [Get free key](https://console.groq.com) (no credit card needed)

---

#### Step 1 — Clone the Repository

```bash
git clone https://github.com/ankitranvirsingh/RAGA-Chatbot
cd raga-chatbot
```

---

#### Step 2 — Create Virtual Environment

**Windows:**
```powershell
py -3.11 -m venv .venv --without-pip
.venv\Scripts\activate
python -m ensurepip --upgrade
```

**macOS / Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Your terminal prompt should now show `(.venv)` — this confirms the environment is active.

---

#### Step 3 — Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> ⏳ First install takes **5–10 minutes** — it downloads PyTorch, ChromaDB, and other ML libraries.

---

#### Step 4 — Configure Environment

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` in any text editor and fill in these required fields:

```env
GROQ_API_KEY=gsk_your_actual_key_here     # from console.groq.com
ADMIN_PASSWORD=your_secure_password        # for admin panel login
SECRET_KEY=any_random_32_character_string  # for JWT token signing
```

---

#### Step 5 — Start the Application

You need **3 separate terminal windows/tabs**. In each one, navigate to the project folder and activate the venv first.

**Terminal 1 — FastAPI Backend:**
```bash
# activate venv first (if not already active)
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

uvicorn app.main:app --reload --port 8000
```

Wait until you see:
```
INFO  Startup complete ✓
```

**Terminal 2 — Chat UI:**
```bash
streamlit run frontend/user_app.py
```

**Terminal 3 — Admin UI:**
```bash
streamlit run frontend/admin_app.py --server.port 8502
```

---

#### Step 6 — Open in Browser

| Service | URL | Description |
|---|---|---|
| 💬 Chat UI | http://localhost:8501 | Ask questions about your documents |
| 🛠️ Admin UI | http://localhost:8502 | Upload and manage files |
| 📖 API Docs | http://localhost:8000/docs | Interactive Swagger documentation |

---

#### Step 7 — Upload Your First Document

1. Go to **http://localhost:8502** → login with your `ADMIN_USERNAME` and `ADMIN_PASSWORD` from `.env`
2. Click the **Upload Documents** tab
3. Drag and drop any file (PDF, Excel, CSV, Word, etc.)
4. Click **Upload & Index** — wait for the green success message
5. Go to **http://localhost:8501** and start asking questions!

---

### Option 2 — Run with Docker

Docker runs everything automatically — API, Redis, Chat UI and Admin UI — in isolated containers with a single command.

#### Prerequisites

- **Docker Desktop** — [Download here](https://www.docker.com/products/docker-desktop)
  - After installing, open Docker Desktop and wait for the **green "Engine running"** status
- **Groq API Key** — [Get free key](https://console.groq.com)

---

#### Step 1 — Clone the Repository

```bash
git clone https://github.com/yourname/raga-chatbot.git
cd raga-chatbot
```

---

#### Step 2 — Configure Environment

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in:

```env
GROQ_API_KEY=gsk_your_actual_key_here
ADMIN_PASSWORD=your_secure_password
SECRET_KEY=any_random_32_character_string
```

---

#### Step 3 — Build and Start

```bash
docker-compose up --build
```

> ⏳ First build takes **10–15 minutes** — it builds the image, installs packages, and pre-downloads the AI embedding model (90 MB). Subsequent starts take ~30 seconds.

Wait until you see all four services ready:
```
rag_redis    | Ready to accept connections
rag_api      | Startup complete ✓
rag_user_ui  | You can now view your Streamlit app in your browser.
rag_admin_ui | You can now view your Streamlit app in your browser.
```

---

#### Step 4 — Open in Browser

| Service | URL | Description |
|---|---|---|
| 💬 Chat UI | http://localhost:8501 | Ask questions about your documents |
| 🛠️ Admin UI | http://localhost:8502 | Upload and manage files |
| 📖 API Docs | http://localhost:8000/docs | Interactive Swagger documentation |

---

#### Docker Management Commands

```bash
# Stop all containers
docker-compose down

# Start again (no rebuild needed)
docker-compose up

# Rebuild after code changes
docker-compose up --build

# View logs for a specific service
docker logs rag_api
docker logs rag_user_ui
docker logs rag_admin_ui

# Check running containers
docker ps

# View persistent data volumes
docker volume ls

# Delete all data and start fresh
docker-compose down -v
```

> 💾 Your uploaded files and vector data are stored in Docker volumes (`app_data`, `redis_data`) and survive container restarts. Only `docker-compose down -v` deletes them.

---

## 💡 Usage

### Step 1 — Login to Admin Panel
Go to **http://localhost:8502** → enter your admin credentials from `.env`

### Step 2 — Upload Documents
- Drag and drop any supported file
- Add an optional description
- Click **Upload & Index** — wait for the chunk count confirmation

### Step 3 — Start Chatting
Go to **http://localhost:8501** and ask questions naturally:

```
❓ What is the annual leave entitlement?
❓ Who does Alice report to?
❓ Who are Bob's direct reports?
❓ Summarise the Q3 sales data
❓ What is the notice period for resignation?
❓ Explain that in more detail   ← follow-up questions work!
```

Every answer shows the source file, page/row, and a relevance score.

---

## ⚙️ Configuration

```env
# ── LLM (free at https://console.groq.com) ──────────────────────
GROQ_API_KEY=gsk_your_key_here
GROQ_MODEL=llama-3.3-70b-versatile

# ── Admin Credentials ────────────────────────────────────────────
ADMIN_USERNAME=admin
ADMIN_PASSWORD=change_this_in_production
SECRET_KEY=generate_a_random_32_char_string

# ── Storage ──────────────────────────────────────────────────────
CHROMA_PERSIST_DIR=./data/chromadb
UPLOAD_DIR=./data/uploads
SQLITE_PATH=./data/metadata.db

# ── Redis (falls back to in-memory if unavailable) ───────────────
REDIS_URL=redis://localhost:6379/0
CHAT_HISTORY_TTL=86400

# ── Embedding Model (local, no API cost) ─────────────────────────
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ── RAG Parameters ───────────────────────────────────────────────
CHUNK_SIZE=800
CHUNK_OVERLAP=100
TOP_K=5
MAX_FILE_SIZE_MB=50

# ── CORS ─────────────────────────────────────────────────────────
ALLOWED_ORIGINS=*
```

---

## 🔌 API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/` | None | Health check + system status |
| `POST` | `/admin/login` | None | Get JWT Bearer token |
| `POST` | `/admin/upload` | JWT | Upload + index a file |
| `GET` | `/admin/files` | JWT | List all indexed files |
| `DELETE` | `/admin/files/{id}` | JWT | Delete file + all vector chunks |
| `POST` | `/chat` | None | Ask a question, get an answer |
| `GET` | `/chat/{session_id}/history` | None | Get conversation history |
| `DELETE` | `/chat/{session_id}` | None | Clear session history |

### Chat Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "user-abc123",
    "message": "Who does Alice report to?"
  }'
```

```json
{
  "answer": "According to the org chart, Alice reports to Bob (Engineering Manager).",
  "sources": [
    {
      "filename": "org_chart.xlsx",
      "sheet": "Employees",
      "row": 4,
      "score": 0.94
    }
  ],
  "session_id": "user-abc123"
}
```

### Upload Example

```bash
# Get admin token
TOKEN=$(curl -s -X POST http://localhost:8000/admin/login \
  -d "username=admin&password=yourpassword" | jq -r .access_token)

# Upload file
curl -X POST http://localhost:8000/admin/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@org_chart.xlsx" \
  -F "description=Employee hierarchy Q1 2025"
```

---

## 📊 Supported File Types

| Extension | Parser | Chunking Strategy |
|---|---|---|
| `.pdf` | pypdf | One chunk per page section |
| `.csv` | pandas + chardet | One chunk per row (key:value format) |
| `.xlsx` / `.xls` / `.xlsm` | pandas + openpyxl | One chunk per row per sheet + hierarchy block |
| `.docx` / `.doc` | python-docx | Paragraph buffers, 800-word chunks |
| `.pptx` / `.ppt` | python-pptx | One chunk per slide |
| `.txt` / `.md` | built-in + chardet | 800-word sliding window |
| `.json` | built-in | Formatted dump, 800-word chunks |

### Org Hierarchy Detection

For Excel/CSV files with columns like `reports_to`, `manager`, `line manager`, `supervisor` — RAGA automatically:
1. Detects the reporting relationship column
2. Builds an explicit `"Alice reports to Bob"` text block
3. Indexes it separately so hierarchy questions are answered precisely

---

## ⚙️ Concurrency Design

```
1000+ Concurrent Users
          │
          ▼
  Uvicorn (2–4 workers × asyncio event loop)
          │
          ├── FastAPI async handlers (non-blocking I/O)
          │         │
          │         ├── Redis chat history  → async redis-py
          │         ├── Groq LLM call       → async httpx (non-blocking)
          │         └── ChromaDB query      → run_in_executor (thread pool)
          │
          └── Embedding model loaded ONCE per worker (singleton pattern)
```

- **Async I/O** — network calls (Groq, Redis) never block the event loop
- **Thread pool** — CPU-bound embedding and ChromaDB run in `run_in_executor`
- **Singleton embedder** — the 90 MB model loads once per worker, not per request
- **Redis TTL** — chat history auto-expires, preventing memory growth

---

## ☁️ Free Deployment

### Render.com — Full Stack (Recommended)

1. Push to GitHub
2. Go to **render.com → New → Blueprint** → connect your repo
3. Render reads `render.yaml` automatically and creates:
   - FastAPI API service (with 1 GB persistent disk)
   - Streamlit Chat UI
   - Streamlit Admin UI
   - Redis instance
4. Set environment variables in the Render dashboard:
   - `GROQ_API_KEY` → your Groq key
   - `ADMIN_PASSWORD` → your secure password
5. Deploy → get public `*.onrender.com` URLs

> ⚠️ Free tier: services sleep after 15 min inactivity. First request after sleep = ~30s cold start.

---

### Streamlit Community Cloud — Frontend Only

If you want a polished public URL for the Chat UI:

1. Deploy the API to Render (above)
2. Go to **share.streamlit.io** → connect your GitHub repo
3. Main file: `frontend/user_app.py`
4. Add secret: `API_URL = "https://your-api.onrender.com"`
5. Deploy → get a free `*.streamlit.app` URL to share

---

### Upstash — Free Persistent Redis

For chat history that survives container restarts on free tier:

1. Create a free account at **upstash.com**
2. Create a Redis database → copy the `rediss://` connection string
3. Set `REDIS_URL=rediss://...` in your deployment environment variables

---

## 🧪 Running Tests

```bash
# Activate venv first
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # macOS/Linux

# Run all tests
pytest tests/ -v
```

Tests cover: health check, admin login, file upload (TXT, CSV), unsupported type rejection, file listing, delete + 404 verification, chat history, session clear, and input validation.

No external services needed — SQLite runs in-memory and Redis falls back automatically.

---

## 🔑 Getting a Free Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up — **no credit card required**
3. Click **API Keys → Create API Key**
4. Copy the key (starts with `gsk_...`) → paste into `.env`

**Free tier limits:** 14,400 requests/day, 30 requests/minute — sufficient for hundreds of daily active users.

**Available models** (set via `GROQ_MODEL` in `.env`):

| Model | Speed | Best for |
|---|---|---|
| `llama-3.3-70b-versatile` | Fast | General Q&A (default) |
| `mixtral-8x7b-32768` | Medium | Longer documents |
| `llama3-8b-8192` | Fastest | High-volume / demos |

---

## 🔒 Security

- **JWT Bearer tokens** — admin endpoints protected with 8-hour expiring tokens
- **bcrypt password hashing** — credentials never stored in plain text
- **File extension whitelist** — only known safe formats accepted
- **File size cap** — 50 MB default (configurable via `MAX_FILE_SIZE_MB`)
- **CORS control** — restrict `ALLOWED_ORIGINS` to your frontend domain in production
- **Input validation** — Pydantic schemas enforce message length limits (max 4000 chars)
- **Loguru structured logs** — all admin actions and errors logged with timestamps

---

## 🐛 Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Child process died` in Docker | `uvloop` not supported on Windows containers | Remove `--loop uvloop` from Dockerfile CMD |
| `pydantic-core` build fails | Python 3.14 not yet supported | Use Python 3.11 exactly |
| `Redis unavailable` warning | No Redis running | Safe to ignore — uses in-memory fallback |
| Admin login returns 401 | Wrong password | Check `ADMIN_PASSWORD` in `.env` matches what you type |
| `No documents found` in chat | Nothing uploaded yet | Upload at least one file via Admin UI first |
| Slow first response | Embedding model loading (~5s cold start) | Normal — subsequent requests are fast |
| `GROQ_API_KEY not set` | Missing from `.env` | Get free key at console.groq.com |
| Port 8000 already in use | Previous server still running | Run `netstat -ano \| findstr :8000` and kill the PID |

---

## 🗺️ Roadmap

- [ ] Streaming token-by-token responses (WebSocket)
- [ ] Azure AD / SSO authentication
- [ ] Role-based document access control
- [ ] Per-user document isolation
- [ ] Postgres support for multi-replica deployment
- [ ] S3 / Azure Blob storage for uploads
- [ ] OpenAI / Azure OpenAI as LLM alternative
- [ ] Webhook notifications on upload completion
- [ ] Usage analytics dashboard

---

## 👨‍💻 Author

**Ankit Kumar** — Data Analyst & AI/Automation Developer

---

## 📄 License

MIT License — free to use, modify, and distribute.

---

<p align="center">
  Built with ❤️ using FastAPI, Groq, ChromaDB, sentence-transformers, Redis, and Streamlit.<br/>
  <strong>Production-ready. Docker-native. Free to deploy.</strong>
</p>