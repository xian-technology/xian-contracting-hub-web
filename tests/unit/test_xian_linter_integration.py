from __future__ import annotations

import asyncio

from contracting_hub.integrations.xian_linter import lint_contract_source


def test_lint_contract_source_succeeds_inside_running_event_loop() -> None:
    async def _lint_inside_running_loop() -> None:
        findings = lint_contract_source("@export\ndef seed():\n    return 'ok'\n")
        assert findings == ()

    asyncio.run(_lint_inside_running_loop())


def test_catalog_admits_v2_decimal_signatures_and_rejects_float() -> None:
    valid = "@export\ndef quote(amount: decimal):\n    return amount / 3\n"
    assert lint_contract_source(valid) == ()
    findings = lint_contract_source(valid.replace("decimal", "float"))
    assert any(finding.severity == "error" and "float" in finding.message for finding in findings)
