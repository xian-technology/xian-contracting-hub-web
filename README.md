# contracting-hub

Curated smart-contract repository for the Xian ecosystem. Browse, search, inspect, and deploy Xian contracts from a single interface.

## What it does

- **Browse and search** curated Xian contracts with full-text search, category/tag filters, and multiple sort options
- **Inspect contracts** with syntax-highlighted Python source, version diffs, lint reports, and related-contract navigation
- **Engage** as an authenticated developer: star contracts, submit ratings, save playground targets, and deploy versions
- **Manage** the catalog as an admin: create/edit contracts, publish versions, map relations, and curate featured content
- **Track** deployment history and developer leaderboard rankings across the catalog

## Tech stack

| Layer | Tool | Version |
|-------|------|---------|
| Runtime | Python | 3.11.11 |
| Framework | Reflex | 0.8.27 |
| ORM | SQLModel | 0.0.33 |
| Database | SQLite | 3.52.0 (with FTS5) |
| Migrations | Alembic | 1.18.4 |
| Contract linting | xian-linter | 0.2.5 |
| Xian SDK | xian-py | 0.4.8 |
| Tests | pytest + Playwright | 9.0.2 / 1.58.0 |
| Lint/format | Ruff | 0.15.1 |

## Project layout

```
contracting_hub/
  app.py              # Reflex app assembly and route registration
  config.py           # Runtime settings from env vars
  theme.py            # Design tokens, fonts, color palette
  pages/              # Route-level page components
  components/         # Reusable UI primitives (shell, cards, viewers)
  states/             # Reflex state classes for UI orchestration
  models/             # SQLModel schema definitions
  repositories/       # Data-access layer
  services/           # Domain logic (auth, search, diffs, ratings, deploy)
  integrations/       # External adapters (xian-linter, playground, storage)
  admin/              # Admin workspace pages
  utils/              # Helpers and shared metadata
tests/
  unit/               # Fast isolated tests
  integration/        # Database-backed tests
  e2e/                # Playwright browser tests
migrations/           # Alembic migration scripts
assets/               # Static CSS and public assets
```

## Getting started

```bash
# Create a Python 3.11.11 virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# Install the project with dev dependencies
pip install -e ".[dev]"

# Set up Playwright browsers
playwright install chromium

# Copy environment config
cp .env.example .env

# Initialize and migrate the database
reflex db init
reflex db migrate

# Start the dev server
reflex run
```

The app serves at `http://localhost:3000` by default.

## Testing

```bash
# Run all tests
pytest -x -q --timeout=30

# Run by category
pytest -x -q --timeout=30 tests/unit
pytest -x -q --timeout=30 tests/integration
pytest -x -q --timeout=30 tests/e2e

# Coverage report (80% minimum)
pytest --cov=contracting_hub --cov-report=term-missing --cov-fail-under=80
```

## Linting

```bash
ruff check .
ruff format --check .
```

## Production export

```bash
reflex export --no-zip
```

## Environment variables

See `.env.example` for the full list. Key settings:

- `CONTRACTING_HUB_ENV` -- `development` or `production`
- `CONTRACTING_HUB_DB_PATH` -- SQLite database file path
- `CONTRACTING_HUB_BOOTSTRAP_ADMIN_*` -- Optional admin seed credentials

## Architecture notes

- **Auth** uses custom email/password sessions with secure cookies (no Reflex Enterprise auth)
- **Contract versions** are immutable append-only snapshots; new releases create new rows
- **Search** uses SQLite FTS5 across contract names, descriptions, authors, tags, and categories
- **Playground deployment** is isolated behind an adapter so the UI stays stable across integration changes
- **Pages and states** orchestrate the UI; business logic lives in `services/` and `repositories/`
