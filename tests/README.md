# Test Suite

Install the development dependencies before running tests:

```bash
uv sync --extra dev
```

Playwright-backed browser tests also need the Chromium browser binary installed locally:

```bash
uv run playwright install chromium
```

Pytest markers are registered centrally and applied by test directory:

- `unit` for isolated module and helper tests under `tests/unit`
- `integration` for database and app-boundary tests under `tests/integration`
- `e2e` for entrypoint and browser workflow tests under `tests/e2e`
- `smoke` for startup and foundation checks
- `playwright` for browser-driven tests that use the Playwright plugin

Shared fixtures live in [`conftest.py`](conftest.py), and browser defaults
for Playwright coverage live in [`e2e/conftest.py`](e2e/conftest.py).
