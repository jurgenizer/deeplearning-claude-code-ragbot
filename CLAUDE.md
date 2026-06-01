# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the application
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

App serves at `http://localhost:8000` (UI) and `http://localhost:8000/docs` (OpenAPI).

Always use `uv` for all dependency management, running the server, and running Python files — never `pip` or `pip install`. Use `uv sync` to install dependencies, `uv add <pkg>` to add a package, `uv run <script>.py` to run Python files, and `uv run` to execute commands.

No test suite or linter is configured.

## Environment

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. The backend reads this via `backend/config.py` using `python-dotenv`.

## Architecture

This is a RAG chatbot that answers questions about course materials stored in `docs/`. The backend is FastAPI; the frontend is static HTML/JS served by FastAPI from `frontend/`.

**Query flow:**
1. `POST /api/query` → `backend/app.py`
2. `RAGSystem.query()` in `backend/rag_system.py` coordinates all components
3. `AIGenerator` (`backend/ai_generator.py`) calls Claude with tool-use enabled
4. Claude invokes `search_course_content` tool → `CourseSearchTool` (`backend/search_tools.py`)
5. `VectorStore.search()` (`backend/vector_store.py`) queries ChromaDB
6. Claude synthesizes the final answer; sources are returned to the frontend

**Key modules:**

| File | Role |
|------|------|
| `backend/app.py` | FastAPI app, CORS, two endpoints (`/api/query`, `/api/courses`), startup loads docs |
| `backend/rag_system.py` | Orchestrates all components; `add_course_folder()` ingests docs, `query()` is the main entry |
| `backend/ai_generator.py` | Wraps Anthropic Claude; handles the tool-call loop (single search per query) |
| `backend/vector_store.py` | ChromaDB wrapper; two collections: `course_catalog` (metadata) and `course_content` (text chunks) |
| `backend/document_processor.py` | Parses course `.txt` files, chunks text (800 chars / 100 overlap) |
| `backend/search_tools.py` | Defines the `search_course_content` tool Claude calls; tracks sources |
| `backend/session_manager.py` | In-memory per-session conversation history (max 10 messages) |
| `backend/config.py` | Central config — model name, chunk sizes, ChromaDB path, max results |
| `backend/models.py` | Pydantic models: `Lesson`, `Course`, `CourseChunk` |

**Course document format** (`docs/*.txt`):
```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 0: <title>
Lesson Link: <url>
<content>

Lesson 1: <title>
<content>
```

ChromaDB persists locally at `backend/chroma_db/`. To reset, delete that directory; courses reload automatically on next startup.

## Key configuration values (`backend/config.py`)

- Model: `claude-sonnet-4-20250514`
- Embeddings: `all-MiniLM-L6-v2`
- `CHUNK_SIZE=800`, `CHUNK_OVERLAP=100`
- `MAX_RESULTS=5`, `MAX_HISTORY=2` (stored as last 4 messages = 2 turns)
