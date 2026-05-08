---
id: ADR-014
version: 1.0.0
status: accepted
---

# ADR-014: Live Deployment Corrections from TKT-032

## Status

Accepted. This ADR records corrections discovered during the TKT-032 VPS smoke test (2026-05-08), where the self-deployment pipeline was exercised against a real Ubuntu VPS with live OmniRoute and Telegram credentials. Each correction amends one or more prior architecture artifacts that assumed an incorrect topology or config format.

## Context

TKT-032 dispatched the Executor to run `install-self.sh` on a real VPS and the Reviewer to audit the resulting PR (#119). The live deployment exposed **eight discrepancies** between the architecture documents (as drafted on paper) and the operational reality of Hermes Agent v2026.4.30, OmniRoute as deployed, and Ubuntu 22.04 LTS systemd behavior.

No amount of Windows-based unit testing would have caught these discrepancies — they are integration-level truths about how external software actually behaves when configured per our documentation.

This ADR exists so that future agents and human operators can trust the architecture docs to match reality, rather than discovering the same mismatches through another round of live debugging.

## Decision

Accept all eight corrections listed below. Each correction includes: what was assumed, what reality is, which artifacts are amended, and the reconciliation action.

### Correction 1: OmniRoute Is Remote, Not Local

| Field | Value |
| --- | --- |
| Prior assumption | ADR-011 § Decision point 1: "Specialist runtimes' model client points to `http://localhost:20128/v1` (OmniRoute's local endpoint)." ADR-011 § Consequences: "OmniRoute runs as a sixth systemd unit on the same VPS." SELF-DEPLOYMENT-CONTRACT.md § 5.3: `omniroute.service` on localhost. |
| Live reality | OmniRoute runs on a separate host (`omniroute.infinitycore.space:8443`). It is NOT installed on the VPS and NOT supervised by a local systemd unit. Specialist runtimes point to the remote OmniRoute endpoint, not to localhost. |
| Root cause | ADR-011 was drafted before the VPS was provisioned. The OmniRoute instance was already running on a separate infrastructure, managed independently. |
| Amended artifacts | ADR-011 (add amendment note), SELF-DEPLOYMENT-CONTRACT.md § 5.3 (replace local omniroute.service with remote-endpoint configuration), MODEL-CATALOG.md § 5.1 (endpoint is remote, not localhost), MULTI-HERMES-CONTRACT.md § 4 (model client base URL is remote) |
| Reconciliation | The install script makes the OmniRoute base URL configurable via `OMNIROUTE_BASE_URL` env var (default `http://127.0.0.1:20128` for future local deployment). No `omniroute.service` systemd unit is rendered when `OMNIROUTE_BASE_URL` points to a remote host. The `omniroute` Linux user and `/opt/omniroute/` install are skipped. `FIREWORKS_API_KEY` is loaded by Hermes runtimes directly (not by a local OmniRoute) when OmniRoute is remote. |

### Correction 2: Hermes Config Format Uses `model.default`, Not `agent.model`

| Field | Value |
| --- | --- |
| Prior assumption | MULTI-HERMES-CONTRACT.md § 4: "agent.model: the runtime's main model", "agent.fallback_models: ordered list of fallbacks". MODEL-CATALOG.md § 4.1: "Specialist runtimes pass these strings verbatim as `agent.model` / `agent.fallback_models` in their per-runtime Hermes config." |
| Live reality | Hermes Agent v2026.4.30 uses a `model:` top-level section in `config.yaml` with keys `default` (main model), `provider` (set to `custom` for OmniRoute), `api_key` (the auth key for the provider), and `base_url` (the provider endpoint). The legacy `agent.model` / `agent.fallback_models` keys are either ignored or deprecated in this version. |
| Root cause | The architecture docs were written against Hermes documentation that described the older config format. The actual Hermes Agent release uses a different schema. |
| Amended artifacts | MULTI-HERMES-CONTRACT.md § 4 (config layout), MODEL-CATALOG.md § 4.1 (how identifiers are passed), SELF-DEPLOYMENT-CONTRACT.md § 5.2 (config template references), ADR-011 § Consequences (specialist-runtime config reference) |
| Reconciliation | Config templates use the `model:` section format. The install script's `render_runtime_configs()` function substitutes `{{omniroute_base_url}}`, `{{api_key}}`, and `{{model_id}}` into the new-format template. `model_catalog.py:verify_runtime_config()` is updated to read `model.default` instead of `agent.model`. |

The correct Hermes `config.yaml` model section for a specialist runtime targeting OmniRoute:

```yaml
model:
  default: "deepseek-v3p2"
  provider: custom
  api_key: "${FIREWORKS_API_KEY}"
  base_url: "https://omniroute.infinitycore.space:8443/v1"
```

### Correction 3: `FIREWORKS_API_KEY` Is the OmniRoute Auth Key

| Field | Value |
| --- | --- |
| Prior assumption | ADR-011 § Consequences: "`OMNIROUTE_API_KEY` (used by specialist runtimes to authenticate to OmniRoute)". MODEL-CATALOG.md § 5.2: "`OMNIROUTE_API_KEY` — required (used by the OmniRoute systemd unit to authenticate to the Fireworks backend)." SELF-DEPLOYMENT-CONTRACT.md § 10: `OMNIROUTE_API_KEY` in env var table. |
| Live reality | The deployed OmniRoute instance authenticates callers using the Fireworks API key (`FIREWORKS_API_KEY`) directly. There is no separate `OMNIROUTE_API_KEY`. When `model.provider: custom` and `model.api_key` is set to `FIREWORKS_API_KEY`, Hermes passes this key in the `Authorization: Bearer` header, and OmniRoute accepts it. |
| Root cause | The architecture assumed OmniRoute had its own API key layer separate from the upstream provider key. The deployed OmniRoute instance proxies the Fireworks API key through. |
| Amended artifacts | ADR-011 § Consequences, MODEL-CATALOG.md § 5.2, SELF-DEPLOYMENT-CONTRACT.md § 10 (env var table) |
| Reconciliation | `SELF-DEPLOY.env` lists `FIREWORKS_API_KEY` instead of `OMNIROUTE_API_KEY`. The install script's config templates set `model.api_key` to `${FIREWORKS_API_KEY}`. The `omniroute.service` unit (if ever deployed locally) would still use `FIREWORKS_API_KEY` as its upstream credential, but this is now the same key Hermes runtimes use for their own auth. |

### Correction 4: Model ID `deepseek-v3p2` Works on Deployed OmniRoute; `deepseek-v4-pro` Unverified

| Field | Value |
| --- | --- |
| Prior assumption | MODEL-CATALOG.md § 4.1: `accounts/fireworks/models/deepseek-v4-pro` is the Architect main model and universal fallback. All five catalog entries use the `accounts/fireworks/models/<slug>` format. |
| Live reality | On the deployed OmniRoute instance, the model ID `deepseek-v3p2` resolves and produces completions. The model ID `deepseek-v4-pro` was not successfully tested through the deployed OmniRoute during TKT-032. The deployed OmniRoute's model registry may use different alias conventions than the `accounts/fireworks/models/` format assumed in the catalog. |
| Root cause | MODEL-CATALOG.md § 4.1 identifiers were derived from the Fireworks model page URLs and OmniRoute issue #265 (which described the auto-resolve behavior), but the actual deployed OmniRoute instance has its own alias map that may differ from the assumed convention. |
| Amended artifacts | MODEL-CATALOG.md § 4.1 (add reconciliation note), MODEL-CATALOG.md § 9 (known caveat: model identifier drift already flagged but needs stronger wording) |
| Reconciliation | The install script's `MODEL_IDENTIFIERS` list uses `deepseek-v3p2` (verified working). A follow-up action item is created: verify `deepseek-v4-pro` (and the `accounts/fireworks/models/<slug>` format) against the deployed OmniRoute's `/v1/models` endpoint, and update the catalog accordingly. Until verified, the working short-form identifiers (`deepseek-v3p2`, etc.) are the operational defaults. |

### Correction 5: `devassist` User Needs a Home Directory

| Field | Value |
| --- | --- |
| Prior assumption | SELF-DEPLOYMENT-CONTRACT.md § 5.2: `User=devassist`, `Group=devassist`. The install script creates the user; no mention of home directory. |
| Live reality | If `devassist` is created with `--no-create-home` (or if the system creates it as a system user without a home dir), Hermes Agent crashes with `PermissionError: [Errno 13] Permission denied: '/home/devassist/.git'`. Hermes' git operations require a writable `HOME`. |
| Root cause | The contract specified the user but not the home-directory requirement. Hermes internally uses `os.path.expanduser('~')` for git config and other operations. |
| Amended artifacts | SELF-DEPLOYMENT-CONTRACT.md § 5.2 (systemd unit template), § 6.1 (install gate step 2) |
| Reconciliation | The install script creates `devassist` with `--create-home` (or sets `HOME=/srv/devassist` in the systemd unit's `Environment=` directive, which is the more correct approach since the runtime should not write to `/home/devassist`). The systemd unit template includes `Environment=HOME=/srv/devassist/runtimes/<role>` so that Hermes' `expanduser('~')` resolves to the runtime's working directory, not to a nonexistent `/home/devassist`. |

### Correction 6: `StartLimitIntervalSec` Belongs in `[Unit]`, Not `[Service]`

| Field | Value |
| --- | --- |
| Prior assumption | SELF-DEPLOYMENT-CONTRACT.md § 5.2 per-runtime template: `StartLimitIntervalSec=300` and `StartLimitBurst=5` under the `[Service]` section. Same in § 5.3 OmniRoute unit. |
| Live reality | In systemd, `StartLimitIntervalSec` and `StartLimitBurst` are `[Unit]` directives, not `[Service]` directives. Placing them under `[Service]` causes systemd to silently ignore them, and the journal logs noise from the default burst limit being hit. |
| Root cause | The contract was written from memory of systemd syntax without live validation. This is a common mistake — `RestartSec` and `Restart` are `[Service]` directives, but the start-limit directives are `[Unit]`-level. |
| Amended artifacts | SELF-DEPLOYMENT-CONTRACT.md § 5.2, § 5.3, § 5.4 (all systemd unit templates) |
| Reconciliation | Move `StartLimitIntervalSec` and `StartLimitBurst` to the `[Unit]` section in all unit templates. |

### Correction 7: `TELEGRAM_ALLOWED_USERS` Must Contain a Real Telegram User ID

| Field | Value |
| --- | --- |
| Prior assumption | SELF-DEPLOYMENT-CONTRACT.md § 10 env var table: `TELEGRAM_ALLOWED_USERS` — "Founder". The install script templates set this to a placeholder value. |
| Live reality | Hermes' Telegram gateway checks `TELEGRAM_ALLOWED_USERS` as a comma-separated list of numeric Telegram user IDs. If the Founder's numeric ID is not present, the bot receives messages but responds "Unauthorized user" and discards them. The placeholder value (e.g., `YOUR_TELEGRAM_USER_ID`) does not work. |
| Root cause | The env var was documented as "Founder" without specifying the required format (numeric user ID). The install script used a placeholder that was never meant to work but had no validation or clear guidance. |
| Amended artifacts | SELF-DEPLOYMENT-CONTRACT.md § 10 (env var table: add format specification and required-value note), § 6.1 (install gate: add preflight check that TELEGRAM_ALLOWED_USERS is set to a non-placeholder numeric value) |
| Reconciliation | `SELF-DEPLOY.env` template includes the comment `# TELEGRAM_ALLOWED_USERS — comma-separated numeric Telegram user IDs (required; placeholder values will cause the bot to reject all messages)`. The install script's preflight validates that the value is not a placeholder pattern (e.g., not matching `YOUR_*` or `CHANGE_ME`). |

### Correction 8: Config Templates Must Be Rendered, Not Copied

| Field | Value |
| --- | --- |
| Prior assumption | The install script copies `.tmpl` / `.j2` files to the runtime directories. No explicit rendering step was specified in the contract. |
| Live reality | If template files containing `{{omniroute_base_url}}`, `{{api_key}}`, `{{model_id}}` placeholders are copied as-is, Hermes receives literal `{{omniroute_base_url}}` strings instead of real values, causing HTTP 401 errors and connection failures. The install script must include a `render_runtime_configs()` function that substitutes environment variable values into the templates before writing them to disk. |
| Root cause | The contract assumed that env var substitution would happen at Hermes runtime (via `${VAR}` syntax in YAML), but the template format used `{{var}}` Jinja2-style placeholders that require a rendering step. Additionally, some values (like the OmniRoute base URL) cannot be expressed as Hermes-native env var expansion because they appear inside nested YAML structures that Hermes does not perform shell expansion on. |
| Amended artifacts | SELF-DEPLOYMENT-CONTRACT.md § 6.1 (install gate: add render step between template copy and systemd unit start) |
| Reconciliation | The install script includes `render_runtime_configs()` which: (1) reads each `config.yaml.tmpl`, (2) substitutes `{{key}}` placeholders with values from the environment (`OMNIROUTE_BASE_URL`, `FIREWORKS_API_KEY`, role-specific model IDs), (3) writes the rendered `config.yaml` to the runtime's `.hermes/` directory. The `{{key}}` format is intentionally NOT `${key}` because Hermes performs its own env var expansion on `${key}` patterns, which would double-expand values and break escaping. The `{{key}}` format is a render-time-only substitution that the install script owns. |

## Considered Options

### Option A — Accept all corrections and update all referenced artifacts (CHOSEN)

Trade-offs:
- + Single source of truth: architecture docs match reality.
- + Future agents trust the docs without re-discovering discrepancies.
- + Each correction has a clear reconciliation action.
- − Eight artifacts need updates (ADR-011, SELF-DEPLOYMENT-CONTRACT, MODEL-CATALOG, MULTI-HERMES-CONTRACT, model_catalog.py, config templates, systemd unit templates, SELF-DEPLOY.env).
- − Some corrections change architectural commitments (e.g., remote OmniRoute changes the isolation story).

### Option B — Accept corrections but defer artifact updates to follow-up tickets

Trade-offs:
- + Less work in this PR.
- − Architecture docs remain wrong until tickets are picked up. Future agents who read the docs will be misled.
- − Risk: tickets may be deprioritized and corrections never land.

Rejected: the whole point of TKT-032 was to validate the architecture against reality. Leaving the docs wrong defeats the purpose.

### Option C — Minimal: only update ADR-014, leave other artifacts as-is with "see ADR-014" notes

Trade-offs:
- + Fastest to merge.
- − Readers of SELF-DEPLOYMENT-CONTRACT.md or MODEL-CATALOG.md who don't read ADR-014 will follow incorrect instructions.
- − The contracts are operational documents read during install; they must be self-consistent.

Rejected: contracts are hands-on documents used during deployment. They must be correct in situ, not correct-by-reference.

## Decision Criteria And Mapping

| Criterion | Option A (update all) | Option B (defer) | Option C (ADR only) |
| --- | --- | --- | --- |
| Docs match reality | Yes | No | Partial |
| Future agents not misled | Yes | No | Partial |
| Operational safety | High | Low | Medium |
| Merge cost | Medium | Low | Low |
| Follow-up risk | None | High | Medium |

Option A is the only one that achieves the purpose of live-validation-driven correction.

## Consequences

- **ADR-011** receives an amendment note: "§ Decision point 1 and Consequences amended per ADR-014 Correction 1 — OmniRoute is remote, not local. The install script makes the endpoint configurable."
- **SELF-DEPLOYMENT-CONTRACT.md** v0.3.0:
  - § 5.2: `Environment=HOME=/srv/devassist/runtimes/<role>` added; `StartLimitIntervalSec` / `StartLimitBurst` moved to `[Unit]`; `model.api_key` references `FIREWORKS_API_KEY` instead of `OMNIROUTE_API_KEY`.
  - § 5.3: Replaced with remote-endpoint configuration. No local `omniroute.service` when OmniRoute is remote. `OMNIROUTE_BASE_URL` env var controls local vs remote.
  - § 6.1: Install gate step 2 creates `devassist` with home directory or sets `HOME` in unit. Step 6a renders config templates (new step). Step preflight validates `TELEGRAM_ALLOWED_USERS` is not a placeholder.
  - § 10: `OMNIROUTE_API_KEY` replaced by `FIREWORKS_API_KEY` in env var table. `TELEGRAM_ALLOWED_USERS` format specified.
- **MODEL-CATALOG.md** v0.3.0:
  - § 4.1: Model identifiers note that the deployed OmniRoute uses short-form aliases; `accounts/fireworks/models/` format is the Fireworks-native slug but may not match OmniRoute's alias map. Operational identifiers are verified per deployment.
  - § 5.1: Endpoint is configurable (remote by default for the current deployment).
  - § 5.2: `FIREWORKS_API_KEY` replaces `OMNIROUTE_API_KEY`.
- **MULTI-HERMES-CONTRACT.md** v0.2.0:
  - § 4: Config layout uses `model.default`, `model.provider: custom`, `model.api_key`, `model.base_url` instead of `agent.model` / `agent.fallback_models`.
- **Implementation artifacts** (on the `exe/tkt-032-vps-smoke-test` branch, PR #119):
  - `model_catalog.py:verify_runtime_config()` reads `model.default` instead of `agent.model`.
  - Config templates use the `model:` section format.
  - Systemd unit templates have `HOME` env var and `StartLimitIntervalSec` in `[Unit]`.
  - `render_runtime_configs()` is called during install.
  - `OMNIROUTE_BASE_URL` env var with remote default.

### Security consequence

Correction 3 (`FIREWORKS_API_KEY` is the OmniRoute auth key) means specialist runtimes now hold the same key that OmniRoute uses as its upstream credential. This is less isolated than the prior assumption (where runtimes would have had a separate `OMNIROUTE_API_KEY`). Mitigated by:
- The `FIREWORKS_API_KEY` is scoped to Fireworks API access; a compromised runtime cannot use it for anything beyond Fireworks API calls.
- The deployed OmniRoute is the only routing path; the key is needed to reach LLM endpoints.
- A future local-OmniRoute deployment would reintroduce the `OMNIROUTE_API_KEY` isolation boundary.

### Credential rotation

The `FIREWORKS_API_KEY` was inadvertently exposed in chat during TKT-032 live debugging. It MUST be rotated on the Fireworks dashboard and updated in `SELF-DEPLOY.env` on the VPS before the system enters production use. This ADR records the exposure as a known incident; the rotation itself is an operational action outside the architecture docs.

## Cross-References

- ADR-011 (routing layer — amended by Correction 1)
- ADR-009 (model assignment — model IDs affected by Correction 4)
- ADR-012 (PR-Agent fallback — uses same OmniRoute path, affected by Correction 1)
- `SELF-DEPLOYMENT-CONTRACT.md` (amended by Corrections 1, 2, 3, 5, 6, 7, 8)
- `MODEL-CATALOG.md` (amended by Corrections 1, 2, 3, 4)
- `MULTI-HERMES-CONTRACT.md` (amended by Correction 2)
- `docs/tickets/TKT-032.md` (the ticket that produced these findings)
- PR #119 (Executor implementation branch with corrected artifacts)
- PR #120 (Reviewer verdict: pass-with-notes, flagged several of these issues)
