# AGENTS.md

## Project Description
contracting-hub is a Reflex-based smart-contract repository for the Xian ecosystem. The application should let anonymous users discover curated Xian contracts, let authenticated users manage profiles, star and rate contracts, and deploy selected contract versions to a playground ID, and let administrators manage the entire catalog, metadata, version history, and contract relations from a dedicated admin workspace.

The product is code-first. Contract detail pages are the center of the experience and must combine readable Python source, metadata, lint feedback, version diffs, related-contract context, and deployment actions without feeling crowded.

## Tech Stack
- Python `3.11.11` for the runtime because `xian-contracting==1.0.2` currently requires that exact version.
- Reflex `0.8.27` for the full-stack application shell, routing, state, and UI composition.
- SQLite `3.52.0` for the primary database, with FTS5 enabled for contract search.
- `rx.Model` / SQLModel `0.0.33` for ORM-style data models.
- Alembic `1.18.4` via `reflex db` for schema migrations.
- `xian-linter==0.2.5` for contract validation and lint feedback.
- `xian-py==0.4.8` for Xian SDK integration behind a playground deployment adapter.
- Ruff `0.15.1` for linting and formatting checks.
- `pytest==9.0.2`, `pytest-cov==7.0.0`, and `pytest-timeout==2.4.0` for backend/state testing and coverage gates.
- Playwright `1.58.0` with `pytest-playwright==0.7.2` for browser workflow tests.

## Key Constraints
- Do not assume Reflex Enterprise-only auth features; build custom auth with secure cookie sessions.
- Contract versions are immutable snapshots. Never overwrite published version rows.
- Xian contract metadata and source validation must happen in the service layer, not only in the UI.
- Search state and public contract/version routes must remain shareable and stable.
- Public pages must exclude draft content unless an authorized admin is viewing an admin surface.
- Keep the project modular: pages and states should orchestrate UI, while services and repositories own business logic.

## Build, Test, and Lint Commands
Assume the virtual environment is already activated.

```bash
python -m pip install --upgrade pip
pip install -e ".[dev]"
playwright install chromium
reflex db init
reflex db makemigrations --message "<message>"
reflex db migrate
reflex run
reflex run --env prod
reflex export --no-zip
ruff check .
ruff format --check .
pytest -x -q --timeout=30
pytest --cov=contracting_hub --cov-report=term-missing --cov-fail-under=80
pytest -x -q --timeout=30 tests/e2e
```

## Planned Project Structure
```text
contracting-hub/
├── AGENTS.md
├── IMPLEMENTATION_PLAN.md
├── pyproject.toml
├── rxconfig.py
├── specs/
├── assets/
├── uploads/
├── migrations/
├── scripts/
├── contracting_hub/
│   ├── __init__.py
│   ├── app.py
│   ├── config.py
│   ├── theme.py
│   ├── pages/
│   ├── components/
│   ├── states/
│   ├── models/
│   ├── repositories/
│   ├── services/
│   ├── integrations/
│   ├── admin/
│   └── utils/
└── tests/
    ├── unit/
    ├── integration/
    └── e2e/
```

## Coding Conventions
- Keep Reflex page modules small. Move business rules, validation, and persistence into `services/` and `repositories/`.
- Keep Reflex `State` classes focused on UI orchestration. Do not embed raw SQL or multi-step domain rules directly in state handlers.
- Prefer pure, easily testable functions for rating aggregation, leaderboard scoring, diff generation, metadata validation, and search ranking.
- Add or update migrations for every schema change. Do not rely on ad hoc SQLite mutations.
- Treat `ContractVersion` as append-only. New releases must create new rows and regenerate diff/lint/search artifacts.
- Use typed relation enums instead of free-text relation labels.
- Validate Xian contract rules before publish: contract naming, publish state, and lint output should be enforced server-side.
- Keep upload handling behind a storage adapter so local filesystem storage can be swapped later.
- Reuse shared design tokens and component primitives instead of styling each page ad hoc.
- Avoid hidden side effects in page imports or module import order. App assembly should stay explicit in `app.py`.

## Testing Expectations
- Every service-level change should add or update unit tests.
- Every DB workflow change should add or update integration tests.
- Every user-facing flow change should add or update Playwright coverage if the flow is critical to browsing, auth, engagement, deployment, or admin operations.
- Coverage must remain at or above 80 percent before handoff.
- Prefer deterministic fixtures and seeded test data over brittle cross-test coupling.

## Backpressure
After each task, run the smallest relevant quality gate before moving on.

```bash
ruff check .
ruff format --check .
pytest -x -q --timeout=30 tests/unit
pytest -x -q --timeout=30 tests/integration
pytest -x -q --timeout=30 tests/e2e
```

Before handoff, always run the full project gates.

```bash
ruff check .
ruff format --check .
pytest -x -q --timeout=30
pytest --cov=contracting_hub --cov-report=term-missing --cov-fail-under=80
reflex export --no-zip
```

## Operational Learnings
- The task runner shell may start without an activated virtual environment, `python`, or project tools on `PATH`; use `python3 -m venv .venv` and `source .venv/bin/activate` first so the documented `python`, `pip`, `ruff`, `pytest`, and `reflex` commands resolve normally.
- The current smoke tests execute [`contracting_hub/app.py`](/home/endogen/projects/contracting-hub/contracting_hub/app.py) with `runpy.run_path(...)`; keep the entrypoint importable in that mode by ensuring the project root is on `sys.path` before package-style imports.
- When the shell is not activated but the local virtualenv already exists, invoking tools directly from [`.venv/bin`](/home/endogen/projects/contracting-hub/.venv/bin) is a reliable fallback for `pip`, `ruff`, `pytest`, and `reflex`.
- Early integration boundary modules should stay pure Python and avoid importing `xian-py` directly; the workspace may be bootstrapped before pinned SDK dependencies are installed, and unit tests still need those modules to import cleanly.
- Reflex `0.8.27` resolves the production app module as `[app_name]/[app_name].py`; if the real entrypoint lives elsewhere, keep a thin shim at [`contracting_hub/contracting_hub.py`](/home/endogen/projects/contracting-hub/contracting_hub/contracting_hub.py) so `reflex export --no-zip` can compile successfully.
- Reflex `0.8.27` scaffolds database migrations into an `alembic/` directory when you run `reflex db init`; if the repo standard is [`migrations/`](/home/endogen/projects/contracting-hub/migrations), rename the folder and update [`alembic.ini`](/home/endogen/projects/contracting-hub/alembic.ini) `script_location` immediately so later `reflex db` commands keep working.
- Reflex only loads `rx.Config(env_file=...)` values when `python-dotenv` is installed; without that extra package, keep `.env` parsing in the app settings layer or add the dependency explicitly before relying on `env_file`.
- Keep new tests under [`tests/unit`](/home/endogen/projects/contracting-hub/tests/unit), [`tests/integration`](/home/endogen/projects/contracting-hub/tests/integration), or [`tests/e2e`](/home/endogen/projects/contracting-hub/tests/e2e) so the shared `tests/conftest.py` marker hook applies the expected `unit`, `integration`, or `e2e` marker automatically.
- Reflex `0.8.27` emits a `SitemapPlugin` warning during [`reflex export --no-zip`](/home/endogen/projects/contracting-hub); add `reflex.plugins.sitemap.SitemapPlugin` explicitly to `plugins` or disable it in [`rxconfig.py`](/home/endogen/projects/contracting-hub/rxconfig.py) if you want clean export logs.
- Reflex `0.8.27` currently prints the default `SitemapPlugin` export warning twice during one [`reflex export --no-zip`](/home/endogen/projects/contracting-hub) run; both warnings are non-fatal if the build completes afterward.
- Smoke tests can validate Reflex layout output without booting a server by calling component `.render()` and traversing the serialized `name` / `props` / `children` tree for expected shell text and test IDs.
- Reflex `0.8.27` already tracks SQLModel tables through the shared `rx.Model` metadata; decorating every table with `@rx.ModelRegistry.register` is redundant here and causes duplicate-table warnings when `ModelRegistry.get_metadata()` merges metadata for migrations or tests.
- Alembic autogeneration warns about a cycle between [`contracts`](/home/endogen/projects/contracting-hub/contracting_hub/models/schema.py) and [`contract_versions`](/home/endogen/projects/contracting-hub/contracting_hub/models/schema.py) because they reference each other, but the generated initial SQLite migration still upgrades cleanly; verify it by comparing an `alembic upgrade head` database to `ModelRegistry.get_metadata().create_all(...)` in an integration test.
- Local bootstrap seeding should no-op with a warning until the schema is migrated; once [`users`](/home/endogen/projects/contracting-hub/contracting_hub/models/schema.py), [`profiles`](/home/endogen/projects/contracting-hub/contracting_hub/models/schema.py), and [`categories`](/home/endogen/projects/contracting-hub/contracting_hub/models/schema.py) exist, run `python -m contracting_hub.services.bootstrap` to populate the default taxonomy and bootstrap admin record for development.
