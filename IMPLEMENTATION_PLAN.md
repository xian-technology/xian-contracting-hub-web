# IMPLEMENTATION PLAN

## Phase 1: Foundation and Project Bootstrap
- [x] 1.1 — Initialize the Reflex project skeleton, `pyproject.toml`, `rxconfig.py`, and pinned dependency set for Reflex, SQLModel, Alembic, Ruff, pytest, Playwright, Xian tooling, and coverage plugins.
- [x] 1.2 — Create the base package structure for pages, components, states, models, services, repositories, integrations, theme, and shared utilities.
- [x] 1.3 — Define global design tokens, typography, color system, spacing scale, and the primary responsive application shell used by all pages.
- [x] 1.4 — Configure SQLite connectivity, model base classes, migration workflow, and local environment settings management.
- [x] 1.5 — Define the playground integration adapter contract and document the current Xian playground ID flow, expected payload shape, and error semantics.
- [x] 1.6 — Add local file-storage plumbing for user avatars and other managed uploads with size/type validation hooks.
- [x] 1.7 — Set up pytest, pytest-cov, pytest-timeout, pytest-playwright, shared fixtures, test markers, and browser installation instructions.
- [x] 1.8 — Add smoke tests for app startup, configuration loading, database initialization, and rendering the shared layout shell.

## Phase 2: Core Contract Domain and Data Layer
- [x] 2.1 — Implement database models for users, profiles, contracts, contract versions, categories, category links, relations, stars, ratings, playground targets, deployment history, and admin audit logs.
- [x] 2.2 — Create and verify the initial migrations for the full schema, including indexes and uniqueness constraints.
- [x] 2.3 — Seed the initial category taxonomy and any required admin bootstrap data for local development.
- [x] 2.4 — Implement repository methods for contract listing, contract detail loading, published-version lookup, and relation traversal.
- [x] 2.5 — Implement metadata validation rules for contract names, slugs, semantic versions, publish states, and relation types.
- [x] 2.6 — Implement immutable version storage with changelog persistence and previous-version linkage.
- [x] 2.7 — Implement diff generation helpers for version-to-version comparisons and expose a service-level API for diff retrieval.
- [x] 2.8 — Integrate `xian-linter` into a lint service that validates source code before publish and stores structured lint results per version.
- [x] 2.9 — Add SQLite FTS5 search indexing for contract metadata and selected source text, including rebuild hooks and ranking strategy.
- [x] 2.10 — Write unit and integration tests for schema rules, metadata validation, diff generation, lint storage, and search queries.

## Phase 3: Accounts, Engagement, and Deployment Services
- [x] 3.1 — Implement password hashing, session persistence, role checks, and auth service helpers for registration, login, logout, and current-user resolution.
- [x] 3.2 — Add route and action guards so anonymous, authenticated, and admin-only flows are enforced consistently.
- [x] 3.3 — Implement profile editing services for username, display name, bio, external links, and avatar updates.
- [x] 3.4 — Implement star toggle services and persistence rules that guarantee one favorite record per user per contract.
- [x] 3.5 — Implement one-rating-per-user rules, editable rating submission, and aggregate rating recalculation.
- [x] 3.6 — Implement saved playground target CRUD and validation rules for playground IDs.
- [x] 3.7 — Implement the deployment adapter using the agreed playground integration contract, plus deployment history recording and failure capture.
- [x] 3.8 — Implement developer KPI aggregation services for contract counts, star totals, weighted rating, deployment counts, and recent activity windows.
- [x] 3.9 — Write backend tests for auth flows, profile updates, star/rating behavior, playground target management, deployments, and leaderboard aggregations.

## Phase 4: Public Discovery and Contract UX
- [x] 4.1 — Build the public home page with featured, trending, recently updated, and recently deployed sections.
- [x] 4.2 — Build the browse page with search input, category/tag filters, sorting controls, pagination, and URL-synced query state.
- [x] 4.3 — Build reusable contract card, metadata badge, and rating summary components used across lists and detail views.
- [x] 4.4 — Build the contract detail header with author information, category data, stars, ratings, and primary actions.
- [ ] 4.5 — Build the syntax-highlighted Python code viewer with copy and download actions.
- [ ] 4.6 — Build the version selector, changelog display, and version-status indicators.
- [ ] 4.7 — Build the diff viewer for comparing the selected version against the previous version.
- [ ] 4.8 — Build the lint results panel that summarizes pass/warn/fail status and exposes detailed issues.
- [ ] 4.9 — Build the related-contracts section with typed relation labels and direct navigation.
- [ ] 4.10 — Add Playwright coverage for anonymous browsing, searching, filtering, contract detail loading, version switching, and diff viewing.

## Phase 5: Authenticated User and Community Features
- [ ] 5.1 — Build registration, login, logout, and session-aware navigation flows.
- [ ] 5.2 — Build the profile settings page with avatar management, public profile fields, and saved playground target management.
- [ ] 5.3 — Build inline star and rating interactions on contract detail pages with optimistic feedback and error recovery.
- [ ] 5.4 — Build the deployment drawer or modal that selects a contract version and playground target, submits the deployment request, and shows result state.
- [ ] 5.5 — Build the authenticated deployment history view and user-level saved target shortcuts.
- [ ] 5.6 — Build public developer profile pages that list authored contracts and developer KPI summaries.
- [ ] 5.7 — Build the public developer leaderboard page with multiple KPI sorts and recent/all-time windows.
- [ ] 5.8 — Add Playwright tests for register/login/logout, profile updates, star/rate flows, deployment attempts, deployment history, and leaderboard navigation.

## Phase 6: Admin Workspace and Content Operations
- [ ] 6.1 — Build the admin contract index with filters, status tabs, and quick actions for create, edit, publish, archive, and delete.
- [ ] 6.2 — Build the admin contract editor for metadata, taxonomy, tags, featured state, and author assignment.
- [ ] 6.3 — Build the admin version manager for source input, changelog entry, lint preview, diff preview, and publish controls.
- [ ] 6.4 — Build the admin relation manager for adding, editing, and removing typed links between contracts.
- [ ] 6.5 — Build admin views for category management, basic featured-content curation, and audit-log inspection.
- [ ] 6.6 — Add integration and Playwright tests for admin CRUD, publish/archive rules, version creation, relation editing, and access control.

## Phase 7: Hardening, Coverage, and Release Readiness
- [ ] 7.1 — Add comprehensive loading, empty, validation, and failure states across public, authenticated, and admin screens.
- [ ] 7.2 — Improve accessibility semantics, keyboard navigation, focus management, and responsive behavior on key layouts.
- [ ] 7.3 — Add seed/demo data and repeatable local reset scripts for productive development and QA.
- [ ] 7.4 — Close remaining unit, integration, and Playwright coverage gaps until total coverage is at least 80 percent.
- [ ] 7.5 — Run the full lint, format-check, test, coverage, and production export pipeline and fix the last release blockers.
