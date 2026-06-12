# API Testing Infrastructure

## Changes made

### `pyproject.toml`
Added `[tool.pytest.ini_options]`:
- `testpaths = ["backend/tests"]` — pytest discovers tests without manual path arguments
- `pythonpath = ["backend"]` — backend modules resolve as bare imports (`import app`, `from config import config`, etc.)
- `addopts = "-v"` — verbose output by default

### `backend/tests/conftest.py`
Added two shared fixtures used by API tests:

**`mock_rag`** — a `MagicMock` that stands in for `RAGSystem`. Pre-configures:
- `query` returns a fixed answer + sources tuple
- `get_course_analytics` returns two courses
- `session_manager.create_session` returns `"session_1"`
- `add_course_folder` returns `(2, 10)` (safe for startup event unpacking)

**`client`** — returns a `TestClient` for the real FastAPI `app`. Solves two import-time problems:
1. `rag_system = RAGSystem(config)` runs at module level — `patch("rag_system.RAGSystem", return_value=mock_rag)` applied *before* `import app` intercepts the call so no real ChromaDB or Anthropic credentials are needed.
2. `DevStaticFiles(directory="../frontend")` resolves relative to CWD — `monkeypatch.chdir(backend_dir)` makes `../frontend` point at the real `frontend/` directory so Starlette's directory-existence check passes.
`sys.modules.pop("app", None)` before and after each test ensures a fresh import per test with no cross-test state leakage.

### `backend/tests/test_api.py`
Rewrote to use the shared fixtures from `conftest.py` (removed local `mock_rag` and `client` fixture definitions). Tests cover:

| Test | Endpoint | What it checks |
|------|----------|----------------|
| `test_query_returns_200_with_answer` | `POST /api/query` | Status 200, answer/session_id/sources fields present |
| `test_query_without_session_id_creates_one` | `POST /api/query` | Session auto-created when not provided |
| `test_query_with_session_id_uses_it` | `POST /api/query` | Provided session_id is passed through to `rag_system.query` |
| `test_query_exception_returns_500` | `POST /api/query` | RAGSystem error maps to HTTP 500 |
| `test_courses_endpoint_returns_stats` | `GET /api/courses` | Returns total_courses and course_titles |
| `test_courses_endpoint_exception_returns_500` | `GET /api/courses` | Analytics error maps to HTTP 500 |
| `test_delete_session_returns_200` | `DELETE /api/session/{id}` | Returns `{"status": "cleared"}` and calls `clear_session` |
