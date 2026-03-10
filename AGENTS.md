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
- The checked-in [`.venv`](/home/endogen/projects/contracting-hub/.venv) currently resolves to Python `3.12.3`, so local lint/test runs may pass under that interpreter even though [`pyproject.toml`](/home/endogen/projects/contracting-hub/pyproject.toml) pins the runtime to `3.11.11`; rebuild the environment on `3.11.11` before validating `xian-contracting`-dependent behavior.
- `create_contract_version(...)` links a new release to the latest existing version row by default, including drafts; public diff rendering must walk backward to the nearest published or deprecated predecessor before comparing source so draft code never leaks on public routes.
- The admin version-manager preview should diff against the latest saved version row, including drafts, so its baseline matches the `previous_version_id` linkage that `create_contract_version(...)` will persist on save.
- Keep `xian_linter` imports lazy inside the integration boundary so package imports still succeed in partially bootstrapped environments; version creation can then surface a structured `lint_unavailable` error instead of failing at module import time.
- `xian_linter.lint_code_inline(...)` creates its own event loop; when linting runs inside a live Reflex request loop, patch `asyncio.events._get_running_loop` to `None` around that call so admin/browser version workflows can lint synchronously without tripping `Cannot run the event loop while another loop is running`.
- SQLite FTS5 virtual tables create shadow tables such as `_data`, `_idx`, `_content`, `_docsize`, and `_config`; exclude the search index family from ORM-vs-migration schema parity snapshots and validate the virtual table with a dedicated migration assertion instead.
- Renaming a category changes indexed browse/search metadata for every linked contract; after admin category updates, rebuild each linked contract's FTS document in the service layer so renamed taxonomy appears in search results immediately.
- Pytest collection will treat matching unit and integration filenames as the same top-level module under this repo layout; keep new test basenames unique across `tests/` to avoid `import file mismatch` failures during full-suite runs.
- Keep explicit `statuses=` filters intersected with public visibility when `include_unpublished=False`; otherwise browse and search queries can leak draft contracts even when the caller did not request unpublished content.
- SQLite can load persisted `DateTime` values back as naive timestamps in tests even when model defaults use `utc_now()`; coerce auth-session expiry values back to UTC before comparing them to fresh application timestamps so session resolution stays stable.
- Reflex state route-guard tests can instantiate a state with `_reflex_internal_init=True` and set `router_data` / `router` via `object.__setattr__(..., RouterData.from_router_data(...))` to simulate the current path without booting the app.
- When replacing a stored avatar, commit the new `avatar_path` before deleting the old file, and delete the freshly uploaded replacement on rollback so failed profile updates do not leave broken references or orphaned files.
- SQLModel ORM instances expire on commit inside the shared test patterns here; when assertions need persisted identifiers after the session context exits, snapshot scalar IDs before leaving the session instead of reading them from detached model instances.
- Reflex form controls tend to submit scalar values as strings; keep rating-score coercion in the service layer so `submit_contract_rating(...)` can accept trimmed numeric strings and enforce the 1-to-5 rule before any database write.
- Saved playground target management should preserve a single default target per user whenever any saved targets exist; when the default target is deleted or unset, promote another saved target in the service layer so later deployment flows can rely on a stable preselection.
- Deployment forms may submit both a saved `playground_target_id` and a blank ad hoc `playground_id`; treat blank ad hoc IDs as absent when resolving the target so valid saved-target deploys are not rejected as false conflicts.
- Running the integration suite under the checked-in Python `3.12.3` virtualenv emits non-fatal `DeprecationWarning` messages from `contracting` AST whitelist nodes (`ast.Num`, `ast.Str`, `ast.NameConstant`, `ast.Ellipsis`); they do not currently fail the tests but add log noise.
- SQLite aggregate `DateTime` queries such as `max(deployment_history.initiated_at)` can round-trip back as naive timestamps even when the source model values were UTC-aware; coerce homepage snapshot timestamps back to UTC in the service layer before comparing them in tests or rendering detached summary data.
- Reflex `0.8.27` compiles page functions ahead of request time, so URL-query-driven pages such as the browse catalog cannot read query params directly during page construction; pull `router.page.params` from state in an `on_load` handler and serialize the resulting snapshot into state fields instead.
- Reflex component `.render()` output stores `rx.cond(...)` branches under `true_value` / `false_value` nodes instead of plain `children`; render-tree smoke-test helpers need to traverse those keys if they assert conditionally rendered text.
- Reflex `0.8.27` keeps `rx.foreach(...)` object-item fields symbolic in component `.render()` output instead of expanding every literal list item; smoke tests should assert stable section chrome there, and components may need explicit literal-branch mapping (for example badge `color_scheme`) or `.to(str)` casts for internal link props when consuming object-item vars.
- When a Reflex component smoke test needs to validate per-item data rendered inside `rx.foreach(...)`, assert the stable section chrome in the component test and cover the item serialization separately in unit/state-helper tests; the `.render()` tree will not reliably expose each literal item value.
- Reflex `0.8.27` eagerly evaluates both branches passed into `rx.cond(...)` during component construction; if a non-rendered branch contains `rx.foreach(...)`, coerce the iterable to a typed `Var` first (for example with `rx.Var.create(value).to(list[dict[str, str]])`) so literal empty lists do not raise `UntypedVarError`.
- Reflex dynamic route params such as [`/contracts/[slug]`](/home/endogen/projects/contracting-hub/contracting_hub/pages/contract_detail.py) cannot reuse a `State` field name like `slug`; rename stored state fields (for example to `contract_slug`) or `app.add_page(...)` will fail with `DynamicRouteArgShadowsStateVarError` during app import and export.
- When a static public route shares a prefix with a dynamic route, register the static route first in [`contracting_hub/app.py`](/home/endogen/projects/contracting-hub/contracting_hub/app.py); the new [`/developers`](/home/endogen/projects/contracting-hub/contracting_hub/pages/developer_leaderboard.py) leaderboard should be added before [`/developers/[username]`](/home/endogen/projects/contracting-hub/contracting_hub/pages/developer_profile.py) so the index route stays reachable.
- Apply the same static-before-dynamic ordering to admin contract routes in [`contracting_hub/app.py`](/home/endogen/projects/contracting-hub/contracting_hub/app.py); register [`/admin/contracts/new`](/home/endogen/projects/contracting-hub/contracting_hub/admin/contract_editor.py) before [`/admin/contracts/[slug]/edit`](/home/endogen/projects/contracting-hub/contracting_hub/admin/contract_editor.py) or the create route will be shadowed.
- Reflex `rx.download(url=...)` only accepts app-relative URLs that start with `/`; for in-memory downloads such as contract source snapshots, pass the content through `rx.download(data=...)` and let a state var carry the `data:` URI when you need client-side source downloads.
- Reflex `rx.code_block(language="diff", ...)` renders unified diff output correctly and survives [`reflex export --no-zip`](/home/endogen/projects/contracting-hub), so the public contract diff viewer can stay within the built-in code-block primitive instead of requiring a custom frontend widget.
- Reflex regular state handlers can use generator semantics, and a bare `yield` flushes an intermediate state update before the remaining server work completes; use that pattern for visible optimistic UI on inline actions such as contract stars and ratings, then roll back local state if the service call fails.
- Full-suite pytest runs can leave Playwright-managed asyncio state behind for later synchronous `xian-linter` calls; keep collection order in [`tests/conftest.py`](/home/endogen/projects/contracting-hub/tests/conftest.py) as `unit`, then `integration`, then `e2e` so full-suite and coverage runs avoid `Cannot run the event loop while another loop is running` failures during version-creation tests.
- Reflex `0.8.27` Radix `rx.input(...)` currently types `auto_complete` as a boolean prop rather than the HTML autocomplete token string API; omit that prop on Radix inputs or switch to a plain element input if you need values such as `email` or `current-password`.
- Reflex `0.8.27` warns during export when `on_submit` handlers are annotated narrower than `dict[str, Any]`; keep form-submit state methods typed to `dict[str, Any]` even if the current form only sends string values.
- Full-suite pytest runs that include the Playwright live-server fixture should not run in parallel with [`reflex export --no-zip`](/home/endogen/projects/contracting-hub); both workflows write under [`.web/build`](/home/endogen/projects/contracting-hub/.web/build), and concurrent writes can abort the temporary Reflex app startup with `ENOENT` asset-directory errors.
- Playwright deployment flows need [`CONTRACTING_HUB_PLAYGROUND_DEEP_LINK_BASE_URL`](/home/endogen/projects/contracting-hub/tests/e2e/conftest.py) set in the live-server environment; otherwise the contract-detail deployment drawer only surfaces an `adapter_misconfigured` result instead of exercising the redirect-ready path.
- Playwright account-route tests can reach a Reflex page before controlled profile-setting inputs finish hydrating from state; wait for the expected input `value` to appear before submitting a form or the first interaction can be lost.
- The profile-settings Playwright flow can also drop a display-name edit under the slower coverage run unless the test waits for the hydrated `username` and `display_name` input values before typing over them; the session-header assertion is where that race tends to surface.
- Leaderboard Playwright assertions should wait for the canonical `/developers?...` redirect after submitting the ranking form before reading `page.url`; the filter form navigates asynchronously even when the selected values were already set locally.
- Reflex `0.8.27` emits deprecation warnings for implicit state auto-setters during component render; define explicit setter methods on new `State` fields used by `on_change` handlers if you want smoke-test and export logs to stay quiet.
- Shared [`app_shell(...)`](/home/endogen/projects/contracting-hub/contracting_hub/components/app_shell.py) session-aware header wiring still flows through `auth_state=...`; admin pages should not pass individual current-user props or render-smoke tests will fail with an unexpected-keyword error.
- The [`/admin/operations`](/home/endogen/projects/contracting-hub/contracting_hub/admin/catalog_operations.py) workspace should source featured-curation candidates through `ContractRepository.list_contracts(..., statuses=PUBLIC_VERSION_STATUSES)` and keep the `latest_published_version_id` guard in the service layer so draft-only contracts never surface in featured tooling.
