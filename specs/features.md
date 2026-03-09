# Feature Specification

## 1. Accounts and Authentication
Users need first-party account management so the hub can support personalized actions such as starring, rating, and deployment.

### Scope
- Email/password registration
- Login/logout
- Secure cookie-backed sessions
- Role model with `user` and `admin`
- Auth guards for user-only and admin-only routes

### Acceptance Criteria
- Visitors can register with email, password, and unique username.
- Passwords are stored only as hashes; plaintext passwords are never logged or persisted.
- Login creates a valid session and logout invalidates that session immediately.
- Duplicate email and duplicate username attempts return field-level validation errors.
- Admin privileges are bootstrap-only or assigned by an existing admin; users cannot self-elevate.

## 2. Profiles and Developer Identity
Profiles should make contract authors discoverable and give users a lightweight identity layer.

### Scope
- Editable username and display name
- Optional bio, website, GitHub/Xian links, and avatar image
- Public developer profile page
- Saved playground IDs for one-click deployment

### Acceptance Criteria
- Authenticated users can update profile fields without affecting authentication state.
- Avatar uploads validate size and file type and can be replaced or removed.
- Public profiles show authored contracts, contract counts, stars received, rating aggregates, and deployment counts.
- Saved playground IDs can be added, edited, deleted, and selected as deployment targets later.

## 3. Contract Metadata Model
Each contract needs consistent metadata so the catalog is searchable, comparable, and understandable.

### Required Fields
- Stable slug
- Xian contract name
- Display name
- Short summary
- Long description
- Author reference or author label
- Semantic version for each version entry
- Primary category and optional secondary categories
- Tags
- Publish status: `draft`, `published`, `archived`, `deprecated`

### Recommended Additional Fields
- License
- Documentation URL
- Source repository URL
- Intended network or environment (`sandbox`, `testnet`, `mainnet-compatible`)
- Lint status summary
- Last updated date
- Featured flag

### Acceptance Criteria
- Admins can manage all required fields from the admin UI.
- Public contract cards and detail pages surface the most important metadata without opening an edit flow.
- Archived and draft content is excluded from public discovery unless the viewer is an admin.

## 4. Public Catalog and Discovery
The public experience should prioritize exploration and fast navigation across curated contracts.

### Scope
- Landing page with featured, recent, and trending sections
- Browse page with search, category filters, tag filters, sorting, and pagination
- Stable detail URLs for contracts and explicit URLs for individual versions

### Acceptance Criteria
- Visitors can search contracts by name, description, tag, author, and category.
- Visitors can filter by category and combine filters without losing search state.
- Sorting supports featured, newest, recently updated, most starred, top rated, and alphabetical.
- Search and filter state is reflected in the URL so result pages are shareable.
- Contract detail pages are directly linkable and load correctly from a cold visit.

## 5. Contract Detail Experience
The detail page is the product core and must balance code readability with catalog context.

### Scope
- Metadata header with author, category, version, stars, ratings, and updated date
- Syntax-highlighted Python code viewer
- Copy code and download source actions
- Lint status panel
- Ratings summary and star toggle
- Related contracts section

### Acceptance Criteria
- Published contract pages show syntax-highlighted Python source using a readable, production-grade theme.
- Users can copy the current version source code with one action.
- Contract pages surface lint pass/warn/fail status with issue counts and expandable findings.
- Logged-in users can star and rate directly from the detail page without a full reload.
- Anonymous users see clear prompts for login when attempting protected actions.

## 6. Versioning and Change History
Contracts need immutable version history so users can inspect evolution and use older releases safely.

### Scope
- Multiple versions per contract
- Latest version badge and version selector
- Changelog summary per version
- Diff view against the previous version
- Linkable version pages

### Acceptance Criteria
- Admins add a new version without overwriting existing version records.
- The latest published version is the default public view, but older versions remain accessible by URL.
- Each version stores its own source snapshot, semantic version, release notes, and lint result.
- The UI can display changes between consecutive versions in a unified diff or split diff format.
- Version pages clearly indicate whether the selected version is current, deprecated, or superseded.

## 7. Linked Contracts and Relation Mapping
Contracts that belong together should expose that relationship so developers can understand dependency context.

### Scope
- Typed relations such as `depends_on`, `companion`, `example_for`, `extends`, and `supersedes`
- Public related-contract module on detail pages
- Admin relation management UI

### Acceptance Criteria
- Admins can add and remove relations between contracts from the admin workspace.
- Public contract pages show both outgoing and incoming relations where relevant.
- Relation entries include the relation type and a direct link to the related contract.
- Deleting or archiving a contract does not leave broken relation links in the public UI.

## 8. Stars, Ratings, and Social Proof
Users need lightweight engagement tools so the catalog can surface useful contracts and credible authors.

### Scope
- Binary star/favorite action
- One editable 1-to-5 rating per user per contract
- Aggregate star counts and rating averages
- Recently starred / top rated list logic

### Acceptance Criteria
- Logged-in users can toggle a star on any published contract.
- Logged-in users can create or update exactly one rating per contract.
- Aggregate star counts and rating averages update after a successful user action.
- Rating summaries show average score and rating count; empty states are handled cleanly.
- Users cannot inflate counts through duplicate stars or duplicate ratings.

## 9. Deployment to Xian Playground
The hub should let logged-in users take a curated contract version and send it to a target playground environment.

### Scope
- Deployment action from the contract detail page
- Select saved playground ID or enter an ad hoc target ID
- Deployment adapter backed by the current Xian playground integration contract
- Deployment history and status feedback

### Acceptance Criteria
- Only authenticated users can initiate deployment.
- A deployment always targets a specific contract version and a specific playground ID.
- The UI shows in-progress, success, and failure states, with actionable error messaging when the adapter rejects a request.
- Successful and failed deployment attempts are recorded in deployment history.
- If the playground integration is deep-link based rather than API based, the adapter still records the initiated deployment and redirects or pre-fills the playground consistently.

## 10. Developer Leaderboard
The product should reward authorship quality and help users find productive Xian developers.

### Scope
- Public leaderboard page
- Developer KPIs built from published contracts only
- Sorts and filters for all time and recent activity windows

### KPI Set
- Published contract count
- Total stars received across published contracts
- Weighted average rating across published contracts
- Total rating count
- Total recorded playground deployments
- Recent publish activity

### Acceptance Criteria
- The leaderboard is publicly visible and links each row to a developer profile.
- KPI calculations exclude draft and archived contracts unless explicitly configured otherwise for admins.
- Ties are broken deterministically, for example by star count, then contract count, then username.
- KPI values match the underlying aggregate queries in automated tests.

## 11. Admin Workspace
Admins need a comfortable operational surface for managing a curated repository without editing raw database records.

### Scope
- Contract list with filters and status badges
- Create/edit/archive contract workflow
- Version manager with source editor, changelog, and lint preview
- Category, tag, and relation management
- Audit trail for admin actions

### Acceptance Criteria
- Admins can create a draft contract, add metadata, and publish it only after validation passes.
- Admins can add a new version, review lint feedback, inspect a generated diff, and publish it.
- Admins can archive a contract without deleting its historical records.
- Admin actions generate audit records for create, update, publish, archive, and delete events.
- Non-admin users cannot access admin routes or call admin actions successfully.

## 12. Additional Experience Features
These features are not optional polish; they materially improve usability for a curated contract hub.

### Required Additions
- Featured collections on the homepage
- Responsive layouts for desktop and mobile
- Skeleton, empty, and error states for every major page
- Contract quality badges for lint status, relation count, and version count
- Shareable URLs and metadata for public pages
- Recently updated contracts and recently deployed contracts sections

### Acceptance Criteria
- The homepage highlights featured, trending, and recently updated contracts.
- Empty-state messaging helps users recover from zero results, missing ratings, or missing saved playground IDs.
- Mobile layouts keep search, filters, code view, and deploy actions usable without horizontal overflow.
- Key public pages have screenshot-tested layouts at at least one desktop and one mobile viewport.

## 13. Testing and Quality Gates
The project must ship with strong automated coverage, not just manual QA.

### Scope
- Unit tests for domain services and pure helpers
- Integration tests for DB flows, auth guards, admin actions, and deployment records
- Playwright workflow tests for anonymous, authenticated, and admin journeys
- Coverage gate of at least 80%

### Acceptance Criteria
- `pytest -x -q --timeout=30` passes locally and in CI.
- Coverage fails the build if it drops below 80%.
- Playwright workflows cover browse/search/detail, login/logout, profile updates, star/rate actions, deployment, and admin CRUD.
- UI regressions on critical pages are guarded by screenshot or layout assertions.
