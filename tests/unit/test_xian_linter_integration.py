from __future__ import annotations

import asyncio

from contracting_hub.integrations.xian_linter import lint_contract_source


def test_lint_contract_source_succeeds_inside_running_event_loop() -> None:
    async def _lint_inside_running_loop() -> None:
        findings = lint_contract_source("@export\ndef seed():\n    return 'ok'\n")
        assert findings == ()

    asyncio.run(_lint_inside_running_loop())
