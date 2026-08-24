# AGENTS.md

Project-specific context for AI agents. See `README.md` and `CLAUDE.md` for
the full architecture, commands, and coding standards.

## Cursor Cloud specific instructions

These notes cover non-obvious setup/run caveats for this VM. Standard commands
live in `CLAUDE.md` ("Core Commands") and `README.md` ("Quick Start").

### Python

- The VM ships **Python 3.12** only (the repo pins `3.11` in `.python-version`,
  but no 3.11 interpreter is installed). All pinned dependencies install and run
  cleanly on 3.12 — use the system `python3`.
- `pip` must be run with `--break-system-packages` (the update script does this).
- pip installs console scripts to `~/.local/bin`, which is **not on `PATH`**.
  Invoke tools via the module form instead:
  - Tests: `python3 -m pytest`
  - Lint: `python3 -m black --check .` and `python3 -m flake8 backend tests`
  - Backend server: `~/.local/bin/uvicorn backend.main:app --reload --port 8000`
    (or `python3 -m uvicorn ...`).

### Secrets / external services (needed for FULL end-to-end)

- The app talks to **Supabase** (Postgres, Auth, Storage) and the **Anthropic
  API**. Full user flows (login, upload, agent pipeline, saved reports) require
  real credentials in `.env` (`ANTHROPIC_API_KEY`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`) and
  `frontend/.env.local` (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`).
- Without secrets you can still: boot the backend (`settings.py` defaults every
  key to `""`), hit `GET /health`, run the full `pytest` suite (mostly
  in-memory), and exercise the pandas + guardrail core directly.
- **Frontend gotcha:** `frontend/src/lib/supabase.ts` calls `createClient` which
  **throws `"supabaseUrl is required"` on an empty URL**, blank-screening the
  app. To render the UI locally, `frontend/.env.local` (gitignored) must contain
  non-empty `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — placeholders like
  `https://placeholder.supabase.co` are enough to render the login page (real
  values are required for actual auth). Vite auto-restarts on `.env.local`
  changes but only reads them at startup.

### Demo data

- `README.md` references `docs/demo_data/Drone Inc - *.xlsx`, but the demo data
  has been reorganized into per-company subfolders
  (`docs/demo_data/{sentinel,vandelay,harvest,helix,corebuilt,clearview}/`).
  The missing DRONE files are why 5 tests **skip** (see
  `tests/integration/conftest.py`) — this is expected, not a failure.
- `sentinel/` ships both a `february/` GL and a March GL, useful for a
  no-secrets, real-data month-over-month variance check.

### Running the services

- Both dev servers are long-running — start them in tmux (or via the root
  `npm run dev`, which uses `concurrently` to run backend + frontend together).
- Backend: port **8000** (`/health` returns `{"status":"ok"}`).
- Frontend: Vite on port **5173**.

### Lint

- `black`/`flake8` are installed and runnable, but the repo currently has
  **pre-existing** findings (black would reformat ~5 files; flake8 reports
  `E501`/`F401` in tests). These are not caused by setup — do not "fix" them
  unless that is the task.
