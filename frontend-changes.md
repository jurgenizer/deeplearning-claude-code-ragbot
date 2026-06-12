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

---

# Frontend Changes

## Feature 1 — Dark/Light Mode Toggle Button

A fixed-position theme toggle button (top-right corner) that switches between dark and light mode.

### Files changed

**`frontend/index.html`**
- Added `#themeToggle` button (fixed top-right, outside `.container`) with inline SVG moon and sun icons.
- Cache-bust versions bumped to `v=11`.

**`frontend/style.css`**
- Added `[data-theme="light"]` CSS variable block (see Feature 2 for full palette).
- Added `.theme-toggle` button: 40×40px circle, `position: fixed; top: 1rem; right: 1rem; z-index: 1000`, surface background, border, hover glow, focus ring.
- `.icon-moon` / `.icon-sun` transition: each icon is `position: absolute`; opacity + transform (rotate 90°) animate over 0.25–0.3s when theme changes.
- Theme transition list on key elements (`body`, `.sidebar`, `.chat-container`, `#chatInput`, `.message-content`, etc.): `transition: background-color 0.3s, color 0.3s, border-color 0.3s, box-shadow 0.3s`.

**`frontend/script.js`**
- `getInitialTheme()` — reads `localStorage`, falls back to `prefers-color-scheme`.
- `applyTheme(theme)` — sets `data-theme` on `<html>`, persists to `localStorage`, updates button `aria-label`.
- `toggleTheme()` — flips between `'light'` and `'dark'`.
- `applyTheme(getInitialTheme())` runs before `DOMContentLoaded` to prevent flash of wrong theme.
- Button wired in `setupEventListeners()`.

---

## Feature 2 — Accessible Light Theme Palette

A complete, WCAG AA–compliant light theme driven by CSS custom properties on `[data-theme="light"]`.

### Colour decisions

| Token | Value | Rationale |
|---|---|---|
| `--background` | `#f8fafc` (Slate 50) | Warm off-white; avoids harsh pure-white glare |
| `--surface` | `#ffffff` | Sidebar and card backgrounds |
| `--surface-hover` | `#f1f5f9` (Slate 100) | Subtle hover states |
| `--text-primary` | `#0f172a` (Slate 900) | ≈19:1 on background ✓ |
| `--text-secondary` | `#475569` (Slate 600) | ≈5.9:1 on white ✓ AA |
| `--primary-color` | `#1d4ed8` (Blue 700) | ≈7.2:1 on background ✓; dark mode used Blue 600 which is only 4.5:1 |
| `--primary-hover` | `#1e40af` (Blue 800) | Darker on hover |
| `--border-color` | `#cbd5e1` (Slate 300) | Visible without dominating |
| `--user-message` | `#2563eb` (Blue 600) | White text on it: 4.6:1 ✓ AA |
| `--focus-ring` | `rgba(29,78,216,0.25)` | Matches new primary |
| `--welcome-bg` | `#eff6ff` (Blue 50) | Tinted card for welcome msg |
| `--welcome-border` | `#3b82f6` (Blue 500) | Card accent border |

### Element-specific overrides (hardcoded colours fixed)

- **Source links** — base style hardcodes `#7dd3fc` (Sky 300, only ~2.2:1 on white — **fails AA**). Light theme overrides to `#1d4ed8` / `#1e40af` on hover.
- **Assistant message bubble** — gets `border: 1px solid var(--border-color)` + soft shadow so it's distinguishable from the white surface.
- **Welcome message** — uses `--welcome-bg` / `--welcome-border` for the blue-tinted card.
- **Inline code** — `rgba(0,0,0,0.06)` background + `#be185d` (Pink 700, 5.9:1 ✓) text tint.
- **Code blocks (`<pre>`)** — `#f1f5f9` background with a Slate 300 border.

### Architecture change

Switched from `body.light-mode` class to `[data-theme="light"]` attribute on `<html>`.  
This is the industry-standard pattern: it separates theme state from component state, works with SSR/prerendering, and lets any selector query the current theme without requiring a DOM walk up to `<body>`.
