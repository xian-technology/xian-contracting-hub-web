# contracting-hub

## Product Summary
contracting-hub is a curated smart-contract repository for the Xian ecosystem. It lets visitors discover and inspect Xian contracts, lets authenticated developers save favorites, rate contracts, and deploy selected versions to a Xian playground target, and lets administrators manage the catalog, metadata, relations, and version history from a dedicated admin workspace.

## Goals
- Make high-quality Xian contracts easy to discover, understand, compare, and reuse.
- Present Python smart-contract code with strong readability: syntax highlighting, lint feedback, metadata, version diffs, and related-contract navigation.
- Give logged-in developers lightweight account features: registration, login/logout, profile management, saved playground targets, stars, ratings, and deployment history.
- Give admins comfortable catalog-management tools for contract CRUD, metadata editing, version publishing, relation mapping, and lint preview.
- Keep the first release operationally simple: Reflex app, SQLite storage, local file uploads in development, and pytest/Playwright coverage of critical workflows.

## User Roles
- Visitor: browse, search, filter, inspect contracts, versions, diffs, related contracts, and leaderboard data.
- Authenticated developer: manage profile and avatar, star contracts, submit ratings, save playground IDs, deploy a selected version, and review deployment history.
- Administrator: manage taxonomy, contracts, versions, relations, featured content, publish state, and quality checks.

## Domain Constraints
- Xian contracts are pure Python modules executed inside Contracting, a restricted Python subset.
- Contract names must follow Xian naming rules, typically `con_...`, lowercase, letters/numbers/underscores only, with a maximum length of 64 characters.
- Contract code must be linted with `xian-linter` before publish and surfaced to end users as a quality signal.
- Local contract validation and simulation may require `xian-contracting`, whose current PyPI release requires Python `3.11.11`; this pins the project runtime even though newer Python releases exist.
- Playground deployment depends on an external Xian playground integration contract. The hub should isolate this behind an adapter so the UI can stay stable whether the playground currently supports deep links, an HTTP API, or both.

## Recommended Tech Stack
| Layer | Choice | Notes |
| --- | --- | --- |
| Runtime | Python `3.11.11` | Required by `xian-contracting==1.0.2` |
| App framework | Reflex `0.8.27` | Full-stack Python UI, routing, state, and server actions |
| Data layer | `rx.Model` / SQLModel `0.0.33` + SQLite `3.52.0` | SQLite-first, low-ops, FTS5-enabled search |
| Migrations | Alembic `1.18.4` via `reflex db` | Repeatable schema evolution |
| Auth | Custom email/password auth with secure cookie sessions | Open-source Reflex auth should not be assumed |
| Contract linting | `xian-linter==0.2.5` | Publish-time and view-time lint summaries |
| Xian integration | `xian-py==0.4.8` | Adapter for playground deployment and future SDK work |
| Test runner | `pytest==9.0.2` | Matches the required project test command |
| Coverage | `pytest-cov==7.0.0` | Enforce `--cov-fail-under=80` |
| Timeout control | `pytest-timeout==2.4.0` | Keep CI and local loops bounded |
| Browser E2E | Playwright `1.58.0` + `pytest-playwright==0.7.2` | End-to-end workflow and responsive UI checks |
| Lint / format | Ruff `0.15.1` | Fast linting and formatting gate |

## Architecture
- Reflex UI layer: pages, reusable components, shared layout shell, design tokens, and route-aware navigation.
- Reflex state layer: thin state classes coordinate validation, optimistic updates, service calls, and transient UI states such as toasts, modals, and loading flags.
- Domain services: pure Python services for auth, contracts, search, version diffs, ratings, leaderboard KPIs, playground deployment, and admin actions.
- Persistence: SQLite tables for users, contracts, versions, relations, and engagement plus an FTS5 virtual table for fast discovery queries.
- Integrations: adapters for `xian-linter`, `xian-py` or playground deep links, avatar file storage, and optional background reindex hooks.
- Testing: unit tests for pure business rules, integration tests for DB/state flows, and Playwright E2E coverage for browse/auth/admin/deploy workflows.

## Core Data Model
- `User`: email, password hash, role, status, created timestamps.
- `Profile`: username, display name, bio, avatar path, links, preferred playground IDs.
- `Contract`: stable slug, canonical contract name, author reference, status, featured flag, latest published version pointer.
- `ContractVersion`: immutable source snapshot, semantic version, changelog, diff metadata, lint summary, publish timestamps.
- `Category` and `ContractCategoryLink`: primary browse taxonomy plus multi-category support.
- `ContractRelation`: links between contracts with typed relations such as `depends_on`, `companion`, `example_for`, and `supersedes`.
- `Star`: one user-to-contract favorite record.
- `Rating`: one user-to-contract rating record with score and optional short note.
- `PlaygroundTarget`: saved playground IDs per user.
- `DeploymentHistory`: target ID, contract version, payload summary, status, timestamps, and error details.
- `AdminAuditLog`: admin actions for create/update/publish/archive/delete workflows.

## Search and Discovery Strategy
- Use SQLite FTS5 over contract name, summary, long description, author name, tags, category names, and selected source-code text.
- Support filters for category, tags, author, publish status, relation presence, rating band, and featured state.
- Support sorts for featured, newest, recently updated, most starred, top rated, most deployed, and alphabetical.
- Expose stable public URLs for contract slugs and explicit version URLs so older versions remain linkable.

## UX Principles
- Fresh, professional visual language with strong hierarchy, generous spacing, and responsive layouts.
- Browsing-first IA: search and category entry points are always available.
- Code-first detail pages: metadata, lint summary, version selector, diff view, and deploy action should be visible without hunting through the UI.
- Fast trust signals: surface stars, rating average, lint status, relation context, latest update date, and author identity near the fold.

## Success Criteria
- Visitors can browse, search, filter, and open stable contract/version URLs without authentication.
- Contract detail pages show metadata, syntax-highlighted code, lint summary, version navigation, change diff, related contracts, and shareable links.
- Authenticated users can register, log in/out, edit their profile, upload an avatar, star contracts, rate contracts, save playground IDs, and deploy the chosen version.
- Admins can create, edit, publish, archive, and version contracts; manage categories and relations; and preview lint results before publishing.
- The developer leaderboard correctly aggregates published contract count, total stars, weighted average rating, deployment count, and recent activity.
- Test coverage reaches at least 80% across backend/state logic and Playwright user flows, and all tests pass.
- The UI is responsive and accessible on desktop and mobile screen sizes.

## Non-Goals
- Open public submissions of new contracts in v1.
- Wallet custody, private-key management, or mainnet transaction signing inside the hub.
- Full blockchain explorer functionality, transaction indexing, or governance features.
- Automated formal verification or deep security auditing beyond lint integration and curated metadata.
- Complex RBAC beyond anonymous user, authenticated user, and admin.
- Real-time collaborative editing of contract source.

## Reference Baselines
- Reflex insights: https://github.com/xian-technology/xian-technology-web/blob/main/reflex-guide.md
- Reflex release baseline: https://pypi.org/project/reflex/
- Reflex docs: https://reflex.dev/docs/getting-started/introduction/
- SQLite release baseline: https://sqlite.org/download.html
- Playwright Python release baseline: https://pypi.org/project/playwright/
- pytest release baseline: https://pypi.org/project/pytest/
- pytest-playwright release baseline: https://pypi.org/project/pytest-playwright/
- pytest-cov release baseline: https://pypi.org/project/pytest-cov/
- pytest-timeout release baseline: https://pypi.org/project/pytest-timeout/
- SQLModel release baseline: https://pypi.org/project/sqlmodel/
- Alembic release baseline: https://pypi.org/project/alembic/
- Ruff release baseline: https://pypi.org/project/ruff/
- Xian lint tool: https://pypi.org/project/xian-linter/
- Xian Python SDK: https://pypi.org/project/xian-py/
- Xian Contracting runtime constraint: https://pypi.org/project/xian-contracting/
- Xian contract naming guidance: https://docs.xian.org/category/smart-contracts
