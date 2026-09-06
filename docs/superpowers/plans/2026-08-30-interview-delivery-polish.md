# Interview Delivery Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the interview demo repeatable for another developer by adding CI quality gates, explicit Docker environment configuration, and a concrete pre-demo deployment checklist.

**Architecture:** Keep the existing FastAPI, static frontend, and Docker Compose architecture unchanged. CI will mirror the repository's Python, frontend syntax, and Compose configuration checks without introducing a second build system. A root `.env.example` will document the variables consumed by Compose, while the README and checklist will distinguish verified local operation from deployment work that still needs external infrastructure.

**Tech Stack:** GitHub Actions, Python 3.11, pytest, Ruff, Node.js syntax checks, Docker Compose, Markdown.

**Spec:** `docs/superpowers/specs/2026-08-27-interview-ready-mvp-design.md`

## Global Constraints

- Keep the current Python 3.11, pinned application dependencies, FastAPI API, static ECharts frontend, and Docker Compose entrypoints.
- Do not commit generated sales data, model weights, secrets, access tokens, or Docker runtime state.
- CI must fail on backend tests, Ruff violations, frontend JavaScript syntax errors, or invalid Compose configuration.
- Documentation must state that the current dataset is synthetic and that public deployment is not verified in this workspace.
- Keep local demo defaults working with `docker compose up --build -d` and `http://localhost:3000`.

---

### Task 1: Make Docker Environment Configuration Explicit

**Files:**
- Create: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Test: `docker compose config --quiet`

**Interfaces:**
- Consumes: the existing `Settings` variables in `backend/app/core/config.py`.
- Produces: a documented root-level Compose configuration that passes optional environment variables into the backend without committing secrets.

- [x] **Step 1: Add a safe root environment template**

Create `.env.example` containing non-secret demo defaults for `ENV`, `DEBUG`, `LOG_LEVEL`, `CORS_ORIGINS`, `API_TOKEN`, `API_TOKEN_HEADER`, `FORECAST_DAYS`, and `FORECAST_WORKERS`. Keep `API_TOKEN` empty so copying the file does not unexpectedly lock the frontend out.

- [x] **Step 2: Wire Compose variables to the backend**

Replace hard-coded environment values in `docker-compose.yml` with `${NAME:-default}` expressions for the variables documented in `.env.example`. Preserve the current defaults and keep `API_TOKEN` optional.

- [x] **Step 3: Clarify startup instructions**

Update the Docker quickstart in `README.md` to instruct users to copy `.env.example` to `.env` when they need configuration overrides, and clarify that Compose reads the root `.env` while local FastAPI reads `backend/.env`.

- [x] **Step 4: Verify the Compose contract**

Run:

```powershell
docker compose config --quiet
```

Expected: exit code `0` with no configuration error.

### Task 2: Add Repository CI Quality Gates

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: `backend/requirements-dev.txt`, `pyproject.toml`, and all JavaScript files under `frontend/js`.
- Produces: a GitHub Actions workflow named `CI` that runs on pushes and pull requests.

- [x] **Step 1: Define the CI workflow**

Create a workflow with a `quality` job on `ubuntu-latest` that checks out the repository, installs Python 3.11 dependencies from `backend/requirements-dev.txt`, runs `python scripts/init_data.py` and `python scripts/train_models.py` to recreate ignored test artifacts, runs `python -m pytest backend/tests -q`, runs `python -m ruff check backend scripts`, installs Node.js 20, runs `node --check` for every tracked `frontend/js/**/*.js` file, and runs `docker compose config --quiet`.

- [x] **Step 2: Keep CI dependency installation cacheable**

Use `actions/setup-python` with pip caching and `actions/setup-node` with npm caching disabled unless a lockfile exists. Do not add a Node package manifest solely for syntax checking.

- [x] **Step 3: Document the CI gate**

Add a short README section explaining that pull requests are expected to pass backend tests, Ruff, frontend syntax validation, and Compose config validation. Do not claim a remote run is green until GitHub provides that run result.

- [x] **Step 4: Verify workflow syntax locally**

Run the same commands used by the workflow from the repository root:

```powershell
C:\Users\MR\miniconda3\envs\salesdash\python.exe -m pytest backend/tests -q
C:\Users\MR\miniconda3\envs\salesdash\python.exe -m ruff check backend scripts
Get-ChildItem frontend/js -Recurse -Filter *.js | ForEach-Object { node --check $_.FullName }
docker compose config --quiet
```

Expected: all commands exit successfully.

### Task 3: Add a Repeatable Interview/Deployment Checklist

**Files:**
- Create: `docs/deployment-checklist.md`
- Modify: `docs/interview-demo.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: the existing Docker Compose ports, `/health`, `/api/model-info`, `/api/data-quality`, and `scripts/verify_deployment.sh`.
- Produces: a concise checklist covering local startup, API checks, browser checks, failure fallback, and explicit production limitations.

- [x] **Step 1: Write the local verification checklist**

Document the exact startup commands, URLs, expected health/model/data-quality states, scoped API example, and the command to stop services.

- [x] **Step 2: Add a browser demo checklist**

Document the user-visible sequence: load the dashboard, confirm the status badge, change product/store scope, refresh, inspect KPI/top-product/inventory changes, and recover from an API error or empty state.

- [x] **Step 3: State deployment boundaries**

Document that a public URL, TLS, domain, secrets, monitoring, and remote CI run require external infrastructure and are not verified by local Docker checks. Keep synthetic-data and offline-training limitations visible.

- [x] **Step 4: Link the checklist from the README and demo script**

Add links so a reviewer can find the checklist from both the quickstart and the 5-minute interview script.

### Task 4: Browser Smoke Verification and Final Quality Gate

**Files:**
- No source changes required unless the browser check exposes a reproducible defect.
- Artifact: `output/playwright/interview-dashboard.png` (local verification artifact, do not commit unless explicitly requested).

**Interfaces:**
- Consumes: the running Compose frontend at `http://localhost:3000` and backend at `http://localhost:8000`.
- Produces: browser evidence that the page loads and the main scope interaction works.

- [x] **Step 1: Start or confirm Compose services**

Run `docker compose up --build -d` and wait until `docker compose ps` reports the backend as healthy.

- [x] **Step 2: Inspect the page in a real browser**

Open `http://localhost:3000`, capture a screenshot, and confirm the dashboard renders without a visible error banner.

- [x] **Step 3: Exercise the main scope interaction**

Use the latest browser snapshot to select a product and a store, trigger refresh, and confirm the status/metric area updates rather than showing a fetch error.

- [x] **Step 4: Run the final repository checks**

Run the backend tests, Ruff, every frontend JS syntax check, `docker compose config --quiet`, `docker compose ps`, and `git status --short`. Expected: all checks pass, both services remain running, and the repository contains only intentional changes.

---

## Self-Review

- Scope covered: repeatable local setup, CI quality gates, interview execution, and explicit deployment boundaries.
- Intentionally not included: public hosting, because no hosting account, domain, or deployment credentials are available in the workspace.
- Generated data/model files and Docker Desktop runtime backups remain outside version control.
