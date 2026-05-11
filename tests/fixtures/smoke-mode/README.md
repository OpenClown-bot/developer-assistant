# Smoke-mode test fixtures

TKT-041 v0.1.1 AUDIT-003 deterministic fixtures used by:

- `tests/test_behaviour_smoke.py` — offline AC-2..AC-6, AC-9 harness
- `tests/test_smoke_inject_endpoint.py` — `smoke_inject.py` unit tests
- `tests/test_dev_assist_cli_smoke.py` — CLI `smoke` subcommand unit tests
- `tests/test_observability_manager_smoke.py` — `/health` extended-field unit tests

All fixtures are pure JSON / plain text. They contain NO real secrets, only
the `smoke-fixture-token-<8>` shape allowed by TKT-041 § 1.4 (3) +
§ 4 AC-9 secret-shape regex set.
