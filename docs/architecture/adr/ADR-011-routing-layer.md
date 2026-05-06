---
id: ADR-011
version: 0.1.0
status: draft
---

# ADR-011: Routing Layer — OmniRoute primary + Fireworks backend + OpenRouter backup

## Status

Draft, pending Founder approval. Supersedes the routing-layer portion of `ADR-009-model-assignment-and-fallback.md` (specifically Options A/F in ADR-009 § Considered Options, which referenced the v0.1.0 catalog's `OmniRoute primary + OpenRouter backup` topology against placeholder models). Related: ADR-009 (per-role assignment), `MODEL-CATALOG.md` v0.2.0 (catalog content).

## Context

`MODEL-CATALOG.md` v0.2.0 narrows the v0.1 catalog to five Fireworks-hosted models (`deepseek-v4-pro`, `kimi-k2.6`, `minimax-m2.7`, `glm-5.1`, `qwen3.6-plus`) per Founder ADDENDUM-001 (2026-05-06). This raises a discrete architectural question: *how do specialist runtimes reach the Fireworks-hosted models* — through a routing-layer abstraction, or through Fireworks's API directly?

The Founder issued a routing-layer mandate (ADDENDUM-001 § 4 patch, 2026-05-06): *"all specialist-runtime model calls go through OmniRoute (primary, with Fireworks as its configured backend); OpenRouter remains backup; no runtime imports a Fireworks SDK or hits api.fireworks.ai directly."*

This ADR records WHY OmniRoute-primary was chosen (per Founder mandate), captures the OmniRoute-supports-Fireworks verification gate that must pass before merging, evaluates the rejected alternatives so future revisions have grounding, and defines the deployment shape (OmniRoute as a sixth systemd-supervised service on the same VPS).

## Decision

Adopt **Option B** from ADDENDUM-001 § 4: **OmniRoute (primary) + OpenRouter (backup)**, with Fireworks configured as the upstream provider inside OmniRoute. Specifically:

1. Specialist runtimes' model client points to `http://localhost:20128/v1` (OmniRoute's local endpoint). They authenticate to OmniRoute with `OMNIROUTE_API_KEY` and pass the catalog identifier (e.g., `glm-5.1`) as the model name.
2. OmniRoute resolves the catalog identifier to the Fireworks slug (e.g., `accounts/fireworks/models/glm-5p1`) using its built-in alias system (Issue [#265](https://github.com/diegosouzapw/OmniRoute/issues/265): *"send the Fireworks path as model ID and OmniRoute auto-resolves it"*).
3. OmniRoute calls Fireworks (`https://api.fireworks.ai/inference/v1`) using the `FIREWORKS_API_KEY` configured into OmniRoute's own state DB (not into specialist runtimes).
4. When OmniRoute is unreachable, specialist runtimes fall over to OpenRouter directly (`https://openrouter.ai/api/v1`) using `OPENROUTER_API_KEY`. OpenRouter's catalog includes all five models with identical Fireworks-routed slugs.
5. **Specialist runtimes never import a Fireworks SDK and never hit `api.fireworks.ai` directly.** They never import a Moonshot/MiniMax/Z.ai/Alibaba SDK either. The only direct provider connection allowed is to OmniRoute (localhost) and OpenRouter.
6. OmniRoute runs as a sixth systemd unit on the same Ubuntu VPS as the five Hermes runtimes (`omniroute.service`); see `SELF-DEPLOYMENT-CONTRACT.md` § 5.2.

**Verification gate — binding precondition for merging this ADR**:

Before the install script (TKT-026) reports success, it MUST execute a connectivity probe against each of the five catalog models through OmniRoute's `/v1/chat/completions` endpoint with the model name set to the catalog identifier. The probe sends a minimum-cost request (1 token max output) and confirms a non-error response. If any of the five fails to resolve through OmniRoute → Fireworks, the install fails fast and an escalation is raised under `paid:third_party_external_service_not_yet_supported` (`ESCALATION-POLICY.md` § 4 deterministic rules table). Silent fallback to direct Fireworks is forbidden.

The verification gate was first executed during this Architect pass (2026-05-06): OmniRoute's provider registry was confirmed to support Fireworks (Issue #265 + v3.7.x feature surface), and the five catalog models were confirmed to exist on Fireworks under the slugs in `MODEL-CATALOG.md` § 4.3. Result: **PASS**. The install-time probe re-verifies on every install / upgrade.

## Considered Options

> **Ordering note (RV-SPEC-014 N-002 fix)**: Options are listed CHOSEN-first below — Option B (chosen) precedes Options A/C/D/E (rejected). The labeling preserves the historical letter assignment from `ADDENDUM-001` § 4 and § 4-patch (where the Founder named the chosen routing topology "Option B"); reordering would force a relabel that breaks the addendum cross-reference. The Decision section above already states the choice explicitly, so no reader who reaches this section is misled by the ordering.

### Option B — OmniRoute primary + Fireworks backend + OpenRouter backup (CHOSEN)

How it works: as in the Decision section.

Trade-offs:

- + Preserves the pre-existing Hermes routing convention (the v0.1.0 catalog already specified OmniRoute primary + OpenRouter backup with placeholder models; this is the smallest-delta substitution given the catalog change).
- + Future provider swaps require no specialist-runtime changes — a sixth model on a different upstream just adds a new alias inside OmniRoute.
- + OmniRoute provides built-in observability (request logs, token tracking, cost analytics on its dashboard) that complements `OBSERVABILITY-CONTRACT.md`.
- + OmniRoute is open-source (MIT) self-hosted on the same VPS — no paid third-party service introduced.
- + OmniRoute's auto-fallback within itself (Subscription → API Key → Cheap → Free per its README) is independent of the specialist-runtime fallback chain — adds resilience.
- + OmniRoute's compression (RTK+Caveman) is optional and may yield free token savings without specialist changes.
- − Adds a service dependency on the VPS; OmniRoute must be installed, maintained, and supervised. Mitigated by `SELF-DEPLOYMENT-CONTRACT.md` (one-command install + systemd) and OmniRoute's mature install path (npm install -g + Docker option).
- − OmniRoute version drift risk: the install script pins a specific OmniRoute release tag; upgrades go through the same RV-SPEC + Founder loop as any architecture artifact.
- − OmniRoute's own state DB is one more thing to back up. Mitigated by adding OmniRoute's data dir to the install-script-managed backup pattern (TKT-026).
- − Verification gate must pass at install/upgrade time to confirm Fireworks support is intact. Mitigated by automating the probe in TKT-026.

### Option A — Fireworks primary + OpenRouter backup (no OmniRoute) (REJECTED)

How it works: specialist runtimes call `https://api.fireworks.ai/inference/v1` directly using the per-model `accounts/fireworks/models/...` slugs; OpenRouter is the backup if Fireworks is unreachable.

Trade-offs:

- + Simplest possible (one fewer service on the VPS).
- + Lowest possible latency (no extra hop through OmniRoute on localhost; though localhost adds <1ms in practice).
- + One provider for the whole catalog (Fireworks).
- − Removes a layer of provider abstraction; if a sixth model is added later from a non-Fireworks-hosted provider, every specialist runtime's config must change in lockstep.
- − No central log of all model calls (each runtime's journald log is the only record); OmniRoute's dashboard would have given a single pane.
- − No central rate-limit / quota / multi-account management; if Fireworks rate-limits the API key, the OpenRouter fallback fires immediately rather than smoothing the spike across multiple Fireworks accounts.
- − Conflicts with the v0.1.0 catalog's "OmniRoute primary" architectural intuition; switching to direct-Fireworks now and back to OmniRoute later doubles migration cost.

Rejected per Founder mandate (ADDENDUM-001 § 4 patch). Engineering arguments above are weaker than the simplicity gain; the Founder's architectural preference is the binding signal.

### Option C — Fireworks primary, OmniRoute optional pass-through, OpenRouter backup (REJECTED)

How it works: specialist runtimes can call Fireworks direct OR through OmniRoute, configured per-runtime.

Trade-offs:

- + Maximum flexibility.
- − Two routing paths to maintain, more configuration, more failure modes.
- − Diagnostic confusion: an issue might surface only on the direct path or only on the OmniRoute path; the on-call surface (the Founder, via `RECOVERY-PLAYBOOK.md`) is doubled.
- − Defeats both the "central observability" benefit of OmniRoute and the "simplest possible" benefit of direct Fireworks.

Rejected: flexibility for the sake of flexibility. v0.1 picks one routing topology and moves on.

### Option D — Direct provider SDKs (no central routing layer at all) (REJECTED)

How it works: each specialist runtime imports a different SDK per model (Fireworks SDK for some, Moonshot SDK for Kimi, etc.).

Trade-offs:

- + Maximum native feature access per provider.
- − Five SDKs in five runtimes; per-call retry, rate-limit, region failover must be implemented per-runtime per-SDK.
- − Catalog identifier abstraction is lost; switching `glm-5.1` to a successor model requires touching every runtime that uses it.
- − Multiplies the secret surface in `SELF-DEPLOY.env`.

Rejected: routing layer indirection is the right level for the catalog identifier abstraction.

### Option E — Hermes built-in routing only (no external routing layer) (REJECTED)

How it works: Hermes Agent's per-runtime `agent.model` and `agent.fallback_models` are the only routing layer. Each entry is a `provider:model` identifier.

Trade-offs:

- + No external routing layer.
- − Hermes still needs provider credentials per provider it speaks. Multiplies the secret surface in `SELF-DEPLOY.env`.
- − Provider API shape changes require Hermes runtime updates.
- − Composes poorly with the catalog identifier abstraction.

Rejected: routing layer indirection is the right level for the catalog identifier abstraction.

## Decision Criteria And Mapping

| Criterion | Option B (CHOSEN) | Option A (direct Fireworks) | Option C (both paths) | Option D (per-provider SDKs) | Option E (Hermes only) |
| --- | --- | --- | --- | --- | --- |
| Founder mandate | Yes | No | No | No | No |
| Catalog-identifier abstraction | Yes | Weak (via local config map) | Yes (where used) | No | No |
| Single observability pane | Yes (OmniRoute dashboard) | No | Partial | No | No |
| Provider swap without runtime change | Yes (OmniRoute alias) | No | Yes (OmniRoute path only) | No | No |
| Latency overhead | <1ms (localhost hop) | 0 | 0 or <1ms | 0 | 0 |
| Operational complexity | +1 daemon (omniroute.service) | 0 | 2 paths | 5 SDKs | Hermes-only config |
| Compatible with v0.1 budget | Yes (free, self-hosted) | Yes | Yes | Yes | Yes |
| Compatible with PRD § 13.1 | Yes | Yes | Yes | Yes | Yes |
| Implementation cost | Low (config + 1 systemd unit) | Low | Medium | High | Low |
| Verification-gate cost | Low (one connectivity probe) | None | High (two paths) | Per-SDK | Per-provider |

Option B carries the Founder mandate plus every other criterion that matters; the 1ms localhost hop and one extra daemon are negligible costs.

## Consequences

- **`SELF-DEPLOYMENT-CONTRACT.md` § 5.2** lists OmniRoute among the systemd-supervised services. The install script (`SELF-DEPLOYMENT-CONTRACT.md` § 5) installs OmniRoute (`npm install -g omniroute@<pinned>` or Docker), generates `OMNIROUTE_API_KEY` for the dev-assist runtimes to call OmniRoute, configures OmniRoute with `FIREWORKS_API_KEY` as the upstream Fireworks credential and `OPENROUTER_API_KEY` as the secondary upstream, and starts `omniroute.service`.
- **`SELF-DEPLOY.env`** carries three required env vars: `OMNIROUTE_API_KEY` (used by specialist runtimes to authenticate to OmniRoute), `FIREWORKS_API_KEY` (configured into OmniRoute), `OPENROUTER_API_KEY` (used both by OmniRoute as a secondary upstream and by specialist runtimes when OmniRoute is unreachable as a direct backup).
- **Specialist-runtime config**: per-runtime `agent.model` is the catalog identifier; the model client base URL is `http://localhost:20128/v1`; the model client API key is `OMNIROUTE_API_KEY`; the fallback path for OmniRoute connectivity error is OpenRouter at `https://openrouter.ai/api/v1` with `OPENROUTER_API_KEY` (`MULTI-HERMES-CONTRACT.md` § 4).
- **Verification gate** (TKT-026): the install script's verify step probes each of the five catalog models through OmniRoute. Result is reported in the install summary; failure raises `paid:third_party_external_service_not_yet_supported` per `ESCALATION-POLICY.md` § 4 deterministic-rule table.
- **Observability**: `OBSERVABILITY-CONTRACT.md` FR-OBS-07 (`llm_calls` table) records the routing path of each LLM call (`omniroute_endpoint` vs `openrouter_endpoint`) so the Founder can see at-a-glance which routing arm carried the call.
- **OmniRoute pinning**: TKT-026 pins a specific OmniRoute release. Version bumps go through the standard PR + RV-SPEC + Founder loop. The pinned version baseline is whatever release is current at install time; subsequent install/upgrade runs validate that the pinned version still supports Fireworks.
- **Failure modes**:
  1. OmniRoute down (e.g., systemd unit crashed): runtime detects connect error to `localhost:20128`, falls over to OpenRouter directly. The supervisor restarts OmniRoute per `MULTI-HERMES-CONTRACT.md` § 9.4 backoff pattern.
  2. Fireworks down (OmniRoute returns upstream error): runtime advances through its declared fallback chain inside OmniRoute (OmniRoute's own auto-fallback fires); if the entire chain fails, runtime falls over to OpenRouter directly.
  3. OpenRouter down + OmniRoute down: the work-item attempt fails per `MULTI-HERMES-CONTRACT.md` § 9.2.
  4. Both reachable but rate-limited: OmniRoute's multi-account / quota-rotation fires (a built-in feature) per its README; if exhausted, work item attempt fails.
- **No direct provider SDK in v0.1**: the Architect MUST NOT add a Fireworks / Moonshot / MiniMax / Z.ai / Alibaba SDK to any specialist runtime in v0.1. If a future requirement makes direct provider access necessary, that's a routing-layer revision (escalates).

## Cross-References

- `PRD-001.md` v0.2.1 § 13.1 (autonomy default)
- `ARCH-001.md` v0.3.0 § 16 (catalog), § 23 (observability), § 22 (open items)
- `MODEL-CATALOG.md` v0.2.0 § 5 (routing topology), § 11 (back-ref to this ADR)
- `ESCALATION-POLICY.md` § 4 deterministic rules (`paid:third_party_external_service_not_yet_supported`, `paid:llm_provider_outside_catalog`)
- `OBSERVABILITY-CONTRACT.md` FR-OBS-07 (`llm_calls` table records routing path)
- `SELF-DEPLOYMENT-CONTRACT.md` § 5.2 (`omniroute.service` systemd unit), § 6 (verify step's connectivity probe)
- `MULTI-HERMES-CONTRACT.md` § 4 (per-runtime model client config), § 9.2 (fallback on outage), § 9.4 (backoff)
- `RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 5.4, § 6.7 (routing-layer findings, including OmniRoute Issue #265 evidence), § 8 (bibliography)
- `docs/orchestration/SESSION-STATE.md` § Current Tooling Decisions (Founder approval timestamp for v0.2.0 / ADDENDUM-001)
- ADR-009 (per-role assignment + fallback rationale; this ADR-011 supersedes its routing-layer rationale)
- Implementation: TKT-026 (model-catalog enforcement + connectivity probe), TKT-021 (specialist-runtime model-client config), TKT-027..031 (observability)
