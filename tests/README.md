# Test Suite

Install the development dependencies before running tests:

```bash
pip install -e ".[dev]"
```

Playwright-backed browser tests also need the Chromium browser binary installed locally:

```bash
playwright install chromium
```

Pytest markers are registered centrally and applied by test directory:

- `unit` for isolated module and helper tests under `tests/unit`
- `integration` for database and app-boundary tests under `tests/integration`
- `e2e` for entrypoint and browser workflow tests under `tests/e2e`
- `smoke` for startup and foundation checks
- `playwright` for browser-driven tests that use the Playwright plugin

Shared fixtures live in [`tests/conftest.py`](/home/endogen/projects/contracting-hub/tests/conftest.py), and browser defaults for future Playwright coverage live in [`tests/e2e/conftest.py`](/home/endogen/projects/contracting-hub/tests/e2e/conftest.py).
