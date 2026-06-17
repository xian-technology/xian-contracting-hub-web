# contracting_hub

## Purpose

This package is the Reflex application behind the contracting hub: catalog
pages, domain services, persistence, and the lint / deploy integrations.

## Contents

- `contracting_hub.py`, `app.py`, `config.py` — app assembly, routing, and
  configuration.
- `pages/` — Reflex page components (catalog, contract detail, admin, …).
- `components/` — reusable UI building blocks shared across pages.
- `states/` — Reflex state classes that back the pages.
- `services/` — domain services for catalog, ratings, deployments, and
  curation workflows.
- `repositories/` — SQLite/FTS5-backed persistence for the services layer.
- `models/` — database models; schema changes go through `../migrations/`.
- `integrations/` — adapters for `xian-linter` and chain deployment.
- `admin/`, `utils/`, `theme.py`, `database.py` — admin workflows, helpers,
  theming, and DB session plumbing.

## Notes

- Contract versions are stored append-only; do not mutate published catalog
  rows outside the service layer.
- Product-scale systems should be modeled as package -> release -> artifact
  records, with package-release artifacts linking back to immutable contract
  versions. Importers should verify pinned owner-repo manifests before writing
  those records.
- Schema changes need an Alembic migration under `../migrations/`; run
  `uv run reflex db migrate` rather than editing the database directly.

## Next

- Follow a page from `pages/` through its state in `states/` into
  `services/` and `repositories/` to see the layering.
