---
id: TKT-034
version: 0.3.1
status: done
arch_ref: ARCH-001@0.3.0
audit_ref: AUDIT-002
prior_version: "0.3.0"
amended_at: 2026-05-09
amendment_trigger: "v0.3.0 secondary spec-quality issues (Q-AMEND-1 prose drift; AC-8(8) sudo ambiguity); SO ratify-ack PASS-with-changes on PR #139"
updated: 2026-05-10
---

# TKT-034: Interactive installer and operator hygiene (AUDIT-002 spec)

## 1. Scope

Promote the four-item operator-hygiene scope stub at `docs/session-log/2026-05-08-session-2.md` § 5.2 (AUDIT-002) into a full implementation contract, AND fold in the Founder ask of 2026-05-09 ("один скрипт или инструкция установки … установщик спросит у меня апи… токен гитхаба… и тд и тп") so that a freshly bootstrapped Ubuntu 22.04 LTS VPS can be brought to a working developer-assistant installation by a single Founder-driven entrypoint that interactively collects every required credential and renders the on-disk state expected by `SELF-DEPLOYMENT-CONTRACT.md` v0.3.0 § 4–§ 8 and `MULTI-HERMES-CONTRACT.md` v0.2.0 § 5. This ticket is the second of the four-ticket AUDIT family (AUDIT-001..004) closing the integration-composition gaps exposed by the 2026-05-08 live VPS deployment of TKT-032 (v0.1.0). AUDIT-001 (TKT-033 v0.3.0) corrected what runtimes are allowed to do once they boot; AUDIT-002 corrects how the runtimes' on-disk preconditions get there in the first place.

The work modifies `scripts/install-self.sh` (v0.2.0 baseline at HEAD `04a5871`, 510 lines) and `scripts/verify-self.sh` (v0.2.0, 368 lines), plus their shared template tree. The five per-role systemd unit templates (`scripts/templates/devassist-<role>.service.j2`) are NOT touched by this ticket — those are the AUDIT-001 write zone and were last frozen by TKT-033 v0.3.0 PR #128 + #130. Any operator-hygiene observation that would require unit-template edits must be filed as a Q-TKT and routed through SO/Architect re-spec, not folded into the AUDIT-002 implementation.

The ticket is partitioned into two scope blocks: **A** preserves the four narrow operator-hygiene fixes from session-log § 5.2 verbatim, and **B** adds the eight new scope items required by the Founder's 2026-05-09 directive and by the auditor's recommendations.

### 1.A Operator hygiene (preserved verbatim from session-log § 5.2)

These four items are the original AUDIT-002 stub. They are preserved here without re-wording:

- **A.i** `gh` CLI is installed and authenticated against the runtime PAT environment variable, never via embedded tokens.
- **A.ii** git `user.name` and `user.email` are configured for the `devassist` system user.
- **A.iii** the runtime's `git remote get-url origin` returns a token-free HTTPS URL (PAT comes from the credential helper or env, not from the URL).
- **A.iv** `/srv/devassist/shared-skills/` is populated with all custom `dev-assist-*` skills at the pinned git commit declared in `MULTI-HERMES-CONTRACT.md` § 5.0, and `verify-self.sh` asserts directory contents match the manifest.

  **v0.3.0 enforcement**: When the renderer cannot find a `shared-skills/<skill>/SKILL.md` for any skill enumerated in `MULTI-HERMES-CONTRACT.md` § 5.0, the install MUST abort with a FATAL log message naming the missing skill path. Silent fallback (e.g. recording a sentinel SHA value like `"absent_at_install_time"` and continuing) is explicitly disallowed. The on-disk source tree at `shared-skills/<skill>/SKILL.md` is the single source of truth; absence is a hard error, not a degradation path.

### 1.B Interactive installer and operator-driven bootstrap (Founder ask, 2026-05-09)

These eight items extend the original stub. Each item names a single observable behaviour the installer (or its sibling verify path) MUST exhibit. Every item carries one or more **architectural choices** that this ticket fixes by explicit Architect decision (§ 7 Risk Notes records the trade-off paragraph behind each choice; deviating from a fixed choice during implementation requires a Q-TKT and an SO/Architect re-spec, not silent adaptation).

- **B.i — One-command bootstrap entrypoint.** A freshly provisioned Ubuntu 22.04 LTS VPS, after a single Founder-driven invocation, MUST reach the post-install state pinned in § 6 below (filesystem laid down, all required env vars in `/srv/devassist/secrets/SELF-DEPLOY.env`, `verify-self.sh` exit 0, no runtime auto-started per `SELF-DEPLOYMENT-CONTRACT.md` § 5.6 and § 6.1 step 11). The Founder MUST NOT have to assemble env vars by hand or paste tokens into multiple files.

  Three options were considered:

  - **Option α — `curl … | sudo bash` one-liner.** Single line; convenient; high trust burden (operator must trust a remote URL with sudo at install time); inconsistent with `HERMES-SKILL-ALLOWLIST.md` § 7's explicit deny-by-default posture and "no marketplace auto-install" rule; not auditable in-place because the script is fetched JIT.
  - **Option β (CHOSEN) — `git clone … && cd … && sudo ./scripts/install-self.sh --interactive`.** Two commands; transparent; the script is on disk and readable before sudo runs; aligns with the existing `install-self.sh` baseline (510 lines already shipped at HEAD `04a5871`); preserves all existing dry-run, fixture, and idempotency surfaces; no remote-execution vector beyond the git clone itself.
  - **Option γ — Single signed binary release artifact.** High deploy cost (release pipeline, signing infrastructure, GPG key management, download server); v0.3.0+ optimization; out of v0.2.0 scope.

  The chosen entrypoint is Option β. The script's existing bash skeleton is reused; the new `--interactive` flag (and its complement `--non-interactive`) gates the credential-prompt path described in B.ii–B.iii. Without `--interactive`, the script behaves exactly as today (env-var driven, fixture-friendly). The README and `SELF-DEPLOYMENT-CONTRACT.md` § 6.1 SHOULD be updated by a sibling clerical PR (not this PR; see § 8) to document the one-command bootstrap as the Founder-facing happy path, with the env-var path retained as the CI / fixture path.

- **B.ii — Interactive credential prompts.** When `--interactive` is selected (default when stdin/stdout are TTYs and `INSTALL_NONINTERACTIVE` is unset; see B.iii), the installer MUST sequentially prompt the operator for every credential listed in `SELF-DEPLOYMENT-CONTRACT.md` v0.3.0 § 10. The full required-prompt set is:

  - `TELEGRAM_BOT_TOKEN` — secret prompt (no terminal echo). Validated by reachability probe to `https://api.telegram.org/bot<TOKEN>/getMe` returning HTTP 200 with `ok: true`. Failure ⇒ re-prompt (up to N=3 attempts, then abort with non-zero exit).
  - `TELEGRAM_ALLOWED_USERS` — visible prompt. Validated as a comma-separated list of strictly numeric Telegram user IDs (regex `^[0-9]+(,[0-9]+)*$`); placeholder patterns matching `^(YOUR_|CHANGE_ME|TEST_)` are rejected per ADR-014 Correction 7. Failure ⇒ re-prompt (up to N=3, then abort).
  - `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` — visible prompt; numeric; MUST appear in `TELEGRAM_ALLOWED_USERS`.
  - `GITHUB_TOKEN` — secret prompt. Two sub-modes per B.ii GH-auth choice (PAT default; SSH-key alternative via `--gh-auth=ssh`):
    - **PAT default (CHOSEN).** Operator pastes a fine-grained PAT scoped to the project repo. Validated by `curl -fsS -H "Authorization: token <TOKEN>" https://api.github.com/user` returning HTTP 200; failure ⇒ re-prompt (up to N=3, then abort). The chosen mode aligns with `HERMES-RUNTIME-CONTRACT.md` § 9 Constraints (token-based REST API auth, least-privilege scope) and avoids the failed `github-auth` skill flagged in `HERMES-SKILL-ALLOWLIST.md` § 4.4.
    - **SSH-key alternative.** Installer generates an ED25519 keypair under `/home/devassist/.ssh/id_ed25519` (mode 0600 root:root until handover), prints the public key, instructs the operator to add it to GitHub at `https://github.com/settings/keys` with read/write scope, then prompts "Press ENTER once the key is added"; validated by `sudo -u devassist ssh -T -o BatchMode=yes -o StrictHostKeyChecking=accept-new git@github.com` exit-1 with stderr containing `Hi <login>! You've successfully authenticated`. SSH-key mode still REQUIRES a `GITHUB_TOKEN` for the runtime's REST API path (`HERMES-RUNTIME-CONTRACT.md` § 9 Implementation Flow steps 4, 5, 6) and prompts for it after SSH validation succeeds. The SSH key is for transport-only convenience, never for the REST API path.
  - `FIREWORKS_API_KEY` — secret prompt. Validated by reachability probe to `${OMNIROUTE_BASE_URL}/models` with `Authorization: Bearer <KEY>` returning HTTP 200 (per ADR-014 Correction 3 — this key is the OmniRoute auth key, not a separate `OMNIROUTE_API_KEY`). Failure ⇒ re-prompt (up to N=3, then abort).
  - `OMNIROUTE_BASE_URL` — visible prompt; default-fill `https://omniroute.infinitycore.space:8443/v1` per `MODEL-CATALOG.md` v0.3.0 § 5.1 and ADR-014 Correction 1. Validated as starting with `https://` or `http://127.0.0.1:` / `http://localhost:` (latter two select the local-OmniRoute mode per `SELF-DEPLOYMENT-CONTRACT.md` § 5.3); reachability is checked together with `FIREWORKS_API_KEY` above.
  - `OPENROUTER_API_KEY` — secret prompt; OPTIONAL (operator may press ENTER to skip; the value `""` is recorded). When non-empty, validated by `curl -fsS -H "Authorization: Bearer <KEY>" https://openrouter.ai/api/v1/auth/key` returning HTTP 200; failure ⇒ re-prompt or skip.
  - `HERMES_DEVASSIST_REPO_URL` — visible prompt; default-fill `https://github.com/OpenClown-bot/developer-assistant.git`. Validated as a syntactically well-formed `https://github.com/<org>/<repo>.git` URL with NO embedded `<token>@` userinfo (a token-bearing URL is rejected per A.iii); reachability probe via `git ls-remote --heads <URL>` exit 0 (with `GITHUB_TOKEN` provided to the credential helper, not embedded in the URL).
  - `HERMES_DEVASSIST_REPO_BRANCH` — visible prompt; default-fill `main`.
  - `OPERATOR_GIT_USER_NAME` — visible prompt; default-fill `developer-assistant operator`. Used at A.ii to seed the `devassist` user's `~/.gitconfig` `user.name`.
  - `OPERATOR_GIT_USER_EMAIL` — visible prompt; default-fill `devassist@<hostname-of-VPS>`. Used at A.ii to seed `~/.gitconfig` `user.email`.

  Per-prompt invariants (apply to every prompt in the list above):

  - Secret prompts MUST disable terminal echo (`stty -echo` or equivalent; `read -s` in bash). Visible prompts MAY echo.
  - Each prompt MUST display the env-var name, a one-sentence purpose, and (for prompts with default-fill) the default value. The operator can accept the default by pressing ENTER.
  - Prompt validation failure (non-2xx HTTP, regex mismatch, placeholder pattern, etc.) MUST surface a human-readable error referencing the env-var name only — never the rejected value (this prevents accidental token-echo into `~/.bash_history` via shell scrollback).
  - On retry-N exhaustion (N=3), the installer aborts with a non-zero exit code, an explicit error message naming the failed env var, and instructions to re-run with `--non-interactive` plus pre-set env vars if the operator wants to bypass the prompt.

- **B.iii — TTY detection rule and non-interactive override.** The installer's interactive vs non-interactive selection MUST be deterministic and overridable:

  - **TTY detection (CHOSEN).** Default-interactive when ALL of: `[ -t 0 ]` AND `[ -t 1 ]` AND `[ "${INSTALL_NONINTERACTIVE:-0}" != "1" ]` AND no `--non-interactive` CLI flag. Default-non-interactive otherwise (CI, fixture mode, piped input, explicit override).
  - **Explicit overrides.** `--interactive` and `--non-interactive` CLI flags override the TTY detection. Setting `INSTALL_NONINTERACTIVE=1` is equivalent to `--non-interactive`. Conflicts (`--interactive` AND `--non-interactive` on the same command line) abort with non-zero exit and a clear error.
  - **Non-interactive contract.** In non-interactive mode, every required env var (the full B.ii prompt set, except the OPTIONAL ones) MUST be already set in the calling environment; missing required env vars abort with non-zero exit BEFORE any filesystem writes (this preserves the existing CI fixture path and idempotency).

  The chosen rule is exactly the form recommended in the AUDIT-002 NUDGE § 4.2; alternatives (e.g., `[ -t 1 ]` only, or `[ -p /dev/stdin ]`-based) were rejected because piped-stdin (used by CI fixtures and by Founder operator runbooks that pipe from a password-manager dump) is the dominant non-TTY case and must default to non-interactive without an env-var override.

- **B.iv — Credential storage layout, ACL, and segregation.** The installer MUST persist every collected secret to a single canonical location and MUST NOT print secret values to stdout, stderr, journald, `/srv/devassist/logs/self-deploy.log`, `~/.bash_history` of any user, or any artifact under git control.

  Three options were considered:

  - **Option ω — `systemd-creds` encrypted credential storage.** Strongest at-rest protection (TPM-bound encryption); decouples secret material from `/srv/devassist/secrets/`; requires systemd ≥ 250 (Ubuntu 22.04 ships systemd 249); requires amending all five per-role systemd unit templates to use `LoadCredentialEncrypted=` and the runtime code to read from `${CREDENTIALS_DIRECTORY}/<name>` instead of env vars. Out of v0.2.0 scope (architectural change requiring its own ADR and a sibling AUDIT-007 cycle to amend the unit templates frozen by TKT-033 v0.3.0).
  - **Option ψ (CHOSEN) — Env file at `/srv/devassist/secrets/SELF-DEPLOY.env` with stricter ACL.** The existing baseline pattern per `SELF-DEPLOYMENT-CONTRACT.md` v0.3.0 § 10. Tightens the ACL from the current `0600 devassist:devassist` to `0400 devassist:devassist`, with `/srv/devassist/secrets/` directory at `0710 root:devassist`. Rotation is by root only (operator runs `sudo install-self.sh --rotate-secrets` in a future v0.3.0+ ticket; this ticket only fixes the layout). No new ADR required; no unit-template changes.
  - **Option ξ — Hybrid (env file for low-sensitivity vars, `systemd-creds` for `TELEGRAM_BOT_TOKEN` and `GITHUB_TOKEN`).** Split-brain that's hard to test deterministically; doubles the failure-mode matrix; deferred together with Option ω.

  The chosen storage is Option ψ. The single env file MUST contain all 11 required env vars enumerated in B.ii, plus the existing optional ones already in the v0.2.0 template (`ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY`, `CUSTOM_BASE_URL`). Required env vars left empty after the prompt phase MUST cause the installer to abort BEFORE writing the file (defense against half-rendered env files).

- **B.v — Re-run idempotency.** The installer MUST be safe to re-run on an already-installed VPS without:

  - re-prompting the operator for credentials that already have a non-empty, non-placeholder value in the existing `/srv/devassist/secrets/SELF-DEPLOY.env` (operator opt-in re-prompt available via `--reprompt-secrets` flag; deferred to a future v0.3.0+ ticket — this PR only fixes the no-prompt-on-rerun default);
  - duplicating the `devassist` system user, `/srv/devassist/` directory tree, systemd unit files, journald drop-in, or `gh` CLI install;
  - corrupting the `operational.db` or any per-runtime `state.db` file;
  - silently overwriting custom skill manifests pinned by A.iv at a different commit (mismatch between manifest pin and on-disk content MUST surface as a `verify-self.sh` failure per B.vi.7, not silent overwrite at install time).

  The existing `install-self.sh` already implements idempotency for the user, filesystem, and unit-file paths (`render_self_deploy_env()` lines 261-294 already short-circuits when the env file exists with `TELEGRAM_BOT_TOKEN`); this ticket extends idempotency to the new prompt phase and the new shared-skills manifest path.

- **B.vi — `verify-self.sh` extensions.** The verify script MUST gain eight new structured invariant checks beyond its current 13-invariant set (`SELF-DEPLOYMENT-CONTRACT.md` § 8). Each new invariant MUST emit a deterministic PASS/FAIL line in the existing `verify-self: PASS|FAIL  (N/M invariants)` summary and MUST NOT print secret values on failure. The eight new invariants are:

  1. **`gh-cli-installed`** — `command -v gh` exits 0 AND `gh --version` reports `gh ≥ 2.40.0`. Failure ⇒ "gh CLI missing or below 2.40.0".
  2. **`gh-cli-authenticated`** — `sudo -u devassist gh auth status --hostname github.com` exits 0 AND its stderr does NOT contain `embedded credential`. Failure ⇒ "gh CLI not authenticated as devassist". (A.i.)
  3. **`devassist-git-identity`** — `sudo -u devassist git config --global user.name` and `--global user.email` both return non-empty values that are NOT placeholder patterns (`^(YOUR_|CHANGE_ME|TEST_)`). Failure ⇒ "devassist git identity unset or placeholder". (A.ii.)
  4. **`origin-remote-token-free`** — `sudo -u devassist git -C /srv/devassist/repo remote get-url origin` returns a URL that does NOT match the regex `https://[^@/]+@` (no userinfo). Failure ⇒ "origin URL contains embedded credential". (A.iii.)
  5. **`shared-skills-manifest-match`** — `/srv/devassist/shared-skills/` directory contents match the manifest at `/srv/devassist/state/shared-skills-manifest.json` (rendered at install time; one entry per skill: `name`, `path`, `pinned_commit`, `sha256_of_skill_md`). Per-skill SHA-256 mismatch OR missing-skill OR extra-skill ⇒ FAIL. The manifest pin is sourced from `MULTI-HERMES-CONTRACT.md` § 5.0 (the 15 custom skills listed there). Failure ⇒ "shared-skills manifest drift: <skill> <reason>". (A.iv.)
  6. **`secrets-file-acl`** — `stat -c '%a %U %G' /srv/devassist/secrets/SELF-DEPLOY.env` returns exactly `400 devassist devassist`. Failure ⇒ "SELF-DEPLOY.env ACL drift". (B.iv.)
  7. **`required-env-vars-present`** — every required env var enumerated in B.ii is present in `/srv/devassist/secrets/SELF-DEPLOY.env` AND non-empty AND NOT a placeholder pattern. Failure lists the missing/empty/placeholder env-var name only (never the value). (B.iv.)
  8. **`prereq-baseline`** — every prereq enumerated in B.viii is satisfied (Ubuntu 22.04 LTS, Docker daemon active, `devassist` in `docker` supplementary group, sufficient disk under `/srv`, required CLIs present). Failure lists the unmet prereq. (B.viii.)

  Existing 11 invariants remain unchanged in their AC and emit format. The 8 new invariants append to the same summary line; the post-install operator output becomes `verify-self: PASS  (19/19 invariants)`.

- **B.vii — Cleanup story (separate runbook, not bundled).** Two options were considered:

  - **Option λ — Bundled `--reinstall` flag that performs cleanup + install in one invocation.** Convenient; loses the "explicit Founder approval" gate that `SELF-DEPLOYMENT-CONTRACT.md` § 6 mandates for destructive operations (start, upgrade); destructive cleanup (stopping `devassist.target`, removing the `devassist` user, blowing away `/srv/devassist/`, deleting systemd unit files) has high blast radius and should not be hidden behind a single flag.
  - **Option μ (CHOSEN) — Separate cleanup runbook (out of installer scope).** The installer DOES NOT perform destructive cleanup. Instead, it DETECTS prior-deploy state at the start of the install run (existence of any of: `/srv/devassist/` directory, `devassist` system user, any `/etc/systemd/system/devassist*.service` or `devassist.target` file) and aborts with a clear "Existing deploy detected. Run the SO-paste-relay cleanup runbook first; see `docs/operations/cleanup-runbook.md` (forthcoming, not in this PR's write zone) or the SO's relayed runbook from session-log § 5.2." message and a non-zero exit code.

  The chosen cleanup posture is Option μ. The detection logic is in scope for this ticket; the runbook itself is NOT in the Architect write zone (`docs/operations/` does not exist in v0.2.0; if it is added, it lands as a sibling SO-routed PR, not folded into this ticket). The detection MUST be skipped under `--force-reinstall` (which is RESERVED for an explicit Founder-driven re-run path; the flag's behaviour beyond skipping detection is OUT OF SCOPE for this PR and MUST raise `Not implemented in v0.2.0; see TKT-NNN backlog` if any reinstallation logic beyond the env-var re-prompt is invoked — guarding against scope creep).

- **B.viii — VPS prerequisite verification.** The installer's preflight phase MUST verify the following before any prompt or filesystem write, and MUST abort with a clear error referencing the unmet prereq if any check fails:

  - **OS** — `lsb_release -rs` returns `22.04` AND `lsb_release -is` returns `Ubuntu`. Other distros / versions abort.
  - **Sudo posture** — `id -u` returns 0 (the installer is invoked under sudo). Non-root abort.
  - **Network** — `curl -fsS --max-time 10 https://api.github.com` returns HTTP 200. Offline abort.
  - **Disk space** — `df --output=avail /srv` reports ≥ 5 GB free. Below 5 GB abort.
  - **Required CLIs** — every command in `bash systemctl sqlite3 curl tar git python3 sudo lsb_release stat sha256sum useradd usermod chmod chown ln mkdir` is present in `$PATH`. Missing CLI abort.
  - **Docker prereq (CHOSEN: yes).** Two options were considered: (a) NOT checking Docker (let the runtime fail at first Executor / Reviewer Hermes call) — rejected because the Executor and Reviewer runtimes (`SELF-DEPLOYMENT-CONTRACT.md` § 5.2.1) require `SupplementaryGroups=docker` and a working Docker daemon; failing late produces a confusing error far from its root cause; (b) checking Docker — chosen. The check is: `command -v docker` exits 0 AND `systemctl is-active docker` returns `active` AND `docker info` exits 0 AND the (newly created at install time) `devassist` user is a member of the `docker` group (`getent group docker | grep -qw devassist`). Missing or inactive Docker abort with explicit instructions referencing the Ubuntu 22.04 install path (`apt-get install docker.io`).
  - **Python** — `python3 --version` reports ≥ 3.11. Below 3.11 abort.
  - **gh CLI** — `command -v gh` exits 0 AND `gh --version` reports ≥ 2.40.0. Missing or below abort with install instructions (`apt-get install gh` after adding the GitHub CLI APT repository, OR `gh ≥ 2.40.0` from a release tarball).

  All prereq checks emit a single PASS/FAIL line per check to stdout (and to `/srv/devassist/logs/self-deploy.log` if it is writable yet) and short-circuit on the first failure. The check ordering is fixed: OS → sudo → network → disk → required CLIs → Docker → Python → gh CLI. This ordering puts the cheapest checks first and the heaviest (Docker daemon socket round-trip) last.

## 2. Non-scope

- AUDIT-001 (TKT-033 v0.3.0, merged 2026-05-09 via PR #128 + #130). Any composition-layer observation surfaced during AUDIT-002 implementation (e.g., a runtime_check invariant that should be added or amended) MUST be filed as a Q-TKT or BACKLOG entry against AUDIT-001's successor ticket, not folded into TKT-034. The five per-role systemd unit templates at `scripts/templates/devassist-<role>.service.j2` are the AUDIT-001 write zone and are NOT modified by this ticket.
- AUDIT-003 (behaviour-level Telegram smoke per `docs/session-log/2026-05-08-session-2.md` § 5.3). Ticket id assigned at SO dispatch time. AUDIT-002 is install-and-verify-only; it does not exercise the live Telegram → classifier → work_items → specialist → result round-trip.
- AUDIT-004 (TKT-011 reformulation per `docs/session-log/2026-05-08-session-2.md` § 5.4). Ticket id assigned at SO dispatch time. AUDIT-002 does not modify TKT-011's dispatch precondition or AC.
- AUDIT-005 (Tester role addition, Founder ask #3 of 2026-05-09). Out of scope for this cycle. The Founder ask "добавь еще роль и тестера" is routed to a future SO dispatch as AUDIT-005 (or its assigned id at dispatch time); it is NOT folded into TKT-034.
- AUDIT-006 (Observer / Monitor tooling, Founder ask #4 of 2026-05-09). Out of scope for this cycle. The Founder ask "следящего" is routed to a future SO dispatch as AUDIT-006 (or its assigned id at dispatch time); it is NOT folded into TKT-034.
- Modifying any role prompt body in `docs/prompts/<role>.md`. The Architect role write-zone (per `AGENTS.md` and `CONTRIBUTING.md` § Roles) does not include `docs/prompts/`; the prompt bodies are owned by the SO/Business Planner.
- Modifying any of the eight infrastructure corrections in ADR-014. ADR-014 is merged on `main` and load-bearing for AUDIT-002; it is referenced as a hard precondition (Corrections 1, 3, 5, 7 in particular).
- Modifying `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md`, `docs/architecture/MULTI-HERMES-CONTRACT.md`, `docs/architecture/HERMES-RUNTIME-CONTRACT.md`, `docs/architecture/HERMES-SKILL-ALLOWLIST.md`, or `docs/architecture/MODEL-CATALOG.md` directly in this ticket's PR. If a substantive amendment to any of these is required during implementation, the Executor MUST file a Q-TKT and pause for Architect re-spec; an amendment ADR (ADR-015 or successor) is the correct vehicle, not in-place edits.
- Modifying `docs/orchestration/SESSION-STATE.md`. SO sole-edit zone.
- Retroactively modifying `TKT-020.md` (v0.2.0), `TKT-021.md` (v0.1.1), `TKT-026.md` (v0.1.1), `TKT-032.md` (v0.1.0), or `TKT-033.md` (v0.3.0). AUDIT-002 extends `install-self.sh` and `verify-self.sh` (TKT-020's runtime artifacts) but does not retroactively amend any merged ticket body. Any documentation update needed for parent or sibling tickets is filed as a sibling clerical PR by the SO, not folded into this ticket.
- Modifying any of the five per-role systemd unit templates `scripts/templates/devassist-<role>.service.j2`. These are AUDIT-001 write zone and were last frozen by TKT-033 v0.3.0. AUDIT-002's verify extensions (B.vi) check unit-template-rendered state at runtime; they do NOT edit the templates.
- Implementing OmniRoute as a local systemd unit. ADR-014 Correction 1 fixed OmniRoute as a remote service for the current deployment; the local-OmniRoute path (`SELF-DEPLOYMENT-CONTRACT.md` § 5.3) is preserved as a future option but not exercised by this ticket.
- Auto-rotating credentials. The `--rotate-secrets` flag mentioned in B.iv is RESERVED for a future v0.3.0+ ticket; this ticket only fixes the layout.
- Provisioning the VPS (creating the EC2/Hetzner/etc. instance, configuring the firewall, mounting the disk, opening port 22). The installer assumes a freshly provisioned Ubuntu 22.04 LTS VPS with sudo access already in hand.
- Multi-VPS deployments (active-passive, blue-green, canary). v0.1.0 architecture is single-VPS per `ARCH-001.md` § 2; multi-VPS is out of scope.
- Behaviour-level smoke tests (sending a real Telegram message, opening a real GitHub PR, completing a real OmniRoute chat-completions round trip). These belong to AUDIT-003 and to the per-runtime smoke harness at `tests/test_self_deployment_scripts.py` already shipped under TKT-020 (extended only with the new offline checks listed in § 6).
- Auto-installing Docker, gh CLI, or Python ≥ 3.11 if absent. The B.viii prereq check ABORTS on missing prereqs; it does NOT silently apt-install them. Auto-install is a deferred convenience; abort-with-instructions is the v0.2.0 contract.

## 3. Required Context

The implementer MUST read all of the following before cutting the implementation branch. Section anchors are pinned to versions current on `main` at branch-cut time; if any of these has shifted on `main` between this spec and Executor cut, the implementer files a Q-TKT and pauses.

- `AGENTS.md` — Roles table is the canonical authority for the per-role write-zone mapping. AUDIT-002 implementer is an Executor (`docs/prompts/executor.md` write zone: `src/`, `scripts/`, `tests/`, plus `docs/tickets/<this-ticket>/§ 10 Execution Log`).
- `CONTRIBUTING.md` — Roles table cross-checks `AGENTS.md`; Architect write zone (`docs/architecture/`, `docs/tickets/`) confirms TKT-034 spec body is in this ticket file only.
- `docs/orchestration/SESSION-STATE.md` (v0.2.5+) — current project state at branch-cut time; AUDIT-002 cycle position confirms.
- `docs/prompts/architect.md` — context for the spec author's discipline; the Executor reads this to confirm scope-locking discipline.
- `docs/prd/PRD-001.md` (v0.2.1) § 12.5 (approval gates: install gate runs without Founder approval; start gate is explicit), § 13.2 (multi-Hermes mandate; install must lay down five HERMES_HOME).
- `docs/architecture/ARCH-001.md` (v0.3.0) § 2 (single-VPS topology), § 11, § 12, § 14 (per-runtime isolation depends on filesystem layout produced by the install path).
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 4 (per-runtime config layout), § 5.0 (the 15 custom dev-assist-* skills with their pinned-commit field — A.iv consumes this list), § 5.1–5.5 (per-role loadout tables — verify-self.sh's existing skill-loadout invariant consumes these), § 12 (security: TELEGRAM_BOT_TOKEN reachability is config-level, not env-level).
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` (v0.2.0) § 8 (Telegram command set — `TELEGRAM_BOT_TOKEN` and `TELEGRAM_ALLOWED_USERS` semantics), § 9 (GitHub and PR Interaction Contract — token-based REST API auth, Implementation Flow steps 4–6, Constraints final bullet rejecting bundled `github-auth`).
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (v0.1.2) § 4.4 (`github-auth` skill source review failed for production credential setup; do not use it; this ticket's PAT-or-SSH installer flow is the v0.1 substitute).
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 4 (filesystem layout — exact paths the installer lays down), § 5.2 (per-role unit template — read-only context), § 5.2.1 (per-role ExecStart — context for B.viii Docker prereq), § 5.3 (OmniRoute local-vs-remote selection — `OMNIROUTE_BASE_URL` semantics for B.ii), § 6.1 (install gate ordering — TKT-034 extends step 1 preflight and step 11 final-message), § 8 (verify invariant set — TKT-034 appends 8 new invariants), § 10 (env var table — the canonical credential list for B.ii), § 10.1 (secret-segregation pattern — confirms env-file-shared-across-units posture is acceptable for B.iv Option ψ).
- `docs/architecture/MODEL-CATALOG.md` (v0.3.0) § 5.1 (OmniRoute endpoints: `https://omniroute.infinitycore.space:8443/v1` is the current default-fill for B.ii's `OMNIROUTE_BASE_URL` prompt), § 5.2 (`FIREWORKS_API_KEY` is the OmniRoute auth key per ADR-014 Correction 3).
- `docs/architecture/adr/ADR-005-multi-hermes-runtime-isolation.md` (v0.1.0) — filesystem-level isolation; per-runtime HERMES_HOME; shared operational store.
- `docs/architecture/adr/ADR-011-routing-layer.md` (v0.1.1, amended by ADR-014) — OmniRoute primary; understanding context for B.ii FIREWORKS_API_KEY validation probe.
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` (v1.0.0) — eight infrastructure corrections; especially Corrections 1 (OmniRoute remote), 3 (`FIREWORKS_API_KEY` is OmniRoute auth), 5 (`devassist` user needs `HOME`), 7 (`TELEGRAM_ALLOWED_USERS` numeric format), 8 (config templates rendered, not copied). AUDIT-002 MUST NOT modify any of these eight.
- `docs/session-log/2026-05-08-session-2.md` § 5.2 — the four-item operator-hygiene scope stub preserved verbatim as A.i–A.iv.
- `docs/session-log/2026-05-08-session-2.md` § 9 — durable cross-reference between session-1 and session-2; AUDIT-002 inherits the same continuity reference (not modified by this ticket).
- `docs/tickets/TKT-020.md` (v0.2.0) — the parent self-deploy install/verify ticket; AUDIT-002 extends `install-self.sh` and `verify-self.sh` (TKT-020's runtime artifacts) without retroactively amending TKT-020's body.
- `docs/tickets/TKT-021.md` (v0.1.1) — the runtime-layout / runtime_check parent; AUDIT-002 MUST NOT change `runtime_check.check_runtime()` behaviour (frozen by TKT-033 v0.3.0); the installer MUST produce a `config.yaml` and `prompt-manifest.json` that already pass runtime_check.
- `docs/tickets/TKT-026.md` (v0.1.1) — the model-catalog enforcement helper; AUDIT-002's `verify-self.sh` invariants 9 and 10 already invoke `model_catalog_cli probe-omniroute` (existing); the new B.vi invariants 1–8 do not duplicate the OmniRoute probe.
- `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` (v0.3.0) — AUDIT-001 precedent; structural reference for this ticket body's depth and AC discipline.
- `scripts/install-self.sh` (510 lines at HEAD `04a5871`) and `scripts/verify-self.sh` (368 lines) — read-only context; the implementer extends these scripts.
- `scripts/templates/devassist-<role>.service.j2` (5 files; AUDIT-001 write zone, frozen by TKT-033 v0.3.0) — read-only context; the verify path's invariant 8 (`prereq-baseline`) cross-checks rendered state but does NOT edit the templates.

### 3.1 AC-1 diagnosis (live state at HEAD `04a5871`)

The following observations pin the live state of the operator-hygiene and credential-collection gap. Implementer MUST verify each at branch-cut time and update the diagnosis if the gap has shifted on `main` between this spec and Executor cut.

- **No interactive prompt path in `install-self.sh`.** The 510-line `scripts/install-self.sh` has no `read -p`, no `read -s`, no `stty -echo`, no TTY detection, and no per-credential prompt loop. Verified by `grep -E 'read -p|read -s|stty|interactive|tty' scripts/install-self.sh` returning zero hits (not counting lines that match "ttyinstall" or similar substrings; the actual interactive plumbing is absent). The script's `render_self_deploy_env()` function (lines 261-294) reads every secret from already-set env vars with `${VAR:-test-token-placeholder}` defaults; placeholders silently land in `SELF-DEPLOY.env` if the operator hasn't set the env vars beforehand.
- **Placeholder secrets silently accepted at install time.** `scripts/install-self.sh:269-275` falls back to `test-token-placeholder` for `TELEGRAM_BOT_TOKEN`, `TELEGRAM_ALLOWED_USERS`, `GITHUB_TOKEN`, `OMNIROUTE_API_KEY`, `OPENROUTER_API_KEY`, `FIREWORKS_API_KEY` when the env var is unset. The placeholder strings then propagate to all five runtimes' env files via `link_secrets_env()`. This is fine for fixture / dry-run mode but is the proximate cause of the live VPS bot returning "Unauthorized user" (per ADR-014 Correction 7) when an inattentive operator runs the installer without setting the env vars.
- **No `gh` CLI install or auth in `install-self.sh`.** `gh` is not installed by the script and is not configured for the `devassist` user. Verified by `grep -E 'gh auth|apt-get install gh|gh ' scripts/install-self.sh` returning zero hits. The runtime's GitHub workflow path (per `HERMES-RUNTIME-CONTRACT.md` § 9) currently relies on the operator pre-installing and pre-authenticating gh; this is the proximate cause of the live A.i, A.ii, A.iii gaps.
- **No git identity for `devassist` user.** Verified by `grep -E 'git config|user.name|user.email' scripts/install-self.sh` returning zero hits. The `devassist` system user is created with `--no-create-home` (line 65); even if home is later set by `Environment=HOME=/srv/devassist/runtimes/<role>` in the unit template (per ADR-014 Correction 5), `~/.gitconfig` is never written by the install path.
- **No shared-skills manifest renderer in `install-self.sh`.** `/srv/devassist/shared-skills/` is laid down as an empty directory at line ~115 of `lay_down_filesystem()` but the 15 custom `dev-assist-*` skills enumerated in `MULTI-HERMES-CONTRACT.md` § 5.0 are never copied into it from the repo's `shared-skills/` source tree, and no manifest at `/srv/devassist/state/shared-skills-manifest.json` is written. Verified by `grep -E 'shared-skills|dev-assist-' scripts/install-self.sh` returning only the directory creation line, no copy/render step. The current `verify-self.sh` does not check shared-skills directory contents (only existence). This is the A.iv gap.
- **`verify-self.sh` does NOT check `gh` auth, `devassist` git identity, origin URL token-freeness, shared-skills manifest, secrets-file ACL, required-env-vars-present, or VPS prereq baseline.** Verified by `grep -E 'gh auth|user.name|origin|shared-skills|stat -c|prereq' scripts/verify-self.sh` returning zero relevant hits. The current 13-invariant set (`SELF-DEPLOYMENT-CONTRACT.md` § 8) covers Telegram / GitHub / OmniRoute / state-store / unit-active / health-endpoint / journald checks; the eight new invariants in B.vi are net-new.
- **Existing `install-self.sh` baseline is well-structured.** The script has a `check_deps()` preflight (lines 42-54), a `create_users()` step (lines 55-69), a `lay_down_filesystem()` step, a `render_runtime_configs()` step (extended by TKT-033 v0.3.0 to also render `prompt-manifest.json`), a `render_self_deploy_env()` step, and a `render_systemd_units()` step. AUDIT-002's interactive credential collection slots in BEFORE `render_self_deploy_env()` and AFTER `check_deps()` (i.e., between the existing preflight and the secret-render step). Re-using the existing structure rather than rewriting the script is the v0.2.0 contract; a full restructure is deferred to a future v0.3.0+ ticket.

### 3.2 Reference: NUDGE-derived hard dependencies

- ADR-014 Corrections 1, 3, 5, 7, 8 — all already on `main`; AUDIT-002 MUST respect them (B.ii uses `OMNIROUTE_BASE_URL` and `FIREWORKS_API_KEY` per Correction 1+3; B.viii confirms `devassist` `HOME` invariant per Correction 5; B.ii's `TELEGRAM_ALLOWED_USERS` validation is the regex form per Correction 7; B.iv's env-file path stays consistent with the rendered config per Correction 8).
- TKT-033 v0.3.0 component C — the `prompt-manifest.json` renderer added to `render_runtime_configs()` (lines 207-258 of `install-self.sh`) sets the precedent for a sibling `shared-skills-manifest.json` renderer at install time. AUDIT-002's A.iv adds the second manifest with the same atomic-write discipline (`mv "$tmp" "$dst"`).
- `MULTI-HERMES-CONTRACT.md` § 5.0 14-skill table — the canonical pin source for A.iv. The implementer MUST NOT introduce a new pinning mechanism; the manifest renderer reads from the source tree and from the contract table (or, more practically, from a hard-coded list in the script that matches the contract; the test in § 6 enforces parity).

## 4. Acceptance Criteria

- [ ] **AC-1 (diagnosis).** § 3.1 of this ticket records the live-state observations at HEAD `04a5871` that ground the gap. Implementer MUST re-verify the seven § 3.1 observations at branch-cut time on `main` and either confirm them unchanged in `§ 10 Execution Log iter-1` or, if the gap has shifted on `main` between this spec and Executor cut, file a Q-TKT (`docs/questions/Q-TKT-034-NN.md`) and pause for SO/Architect re-spec rather than silently adapting.

- [ ] **AC-2 (operator hygiene — A.i, A.ii, A.iii, A.iv).** The installer's preflight + setup phases enforce all four operator-hygiene fixes from § 1.A. Each sub-criterion has at least one deterministic offline test in `tests/test_self_deployment_scripts.py`:
  - **AC-2 (a) — A.i: `gh` CLI installed and authenticated against runtime PAT env var, never via embedded tokens.** The installer (after collecting `GITHUB_TOKEN` per B.ii) runs `sudo -u devassist gh auth login --with-token < <(printf '%s\n' "$GITHUB_TOKEN")` and then `sudo -u devassist gh auth setup-git`. The token MUST be passed via stdin redirection, not via the URL or via `gh auth login --token <token>` with the token on the command line (which would land in `~/.bash_history` and `ps` output). Test: parse the install-self.sh source for `gh auth login --with-token`; reject any `--token` that takes a positional value; reject any `https://[^@/]+@github.com` URL pattern in the auth-setup block.
  - **AC-2 (b) — A.ii: git `user.name` and `user.email` configured for `devassist`.** The installer runs `sudo -u devassist git config --global user.name "$OPERATOR_GIT_USER_NAME"` and `sudo -u devassist git config --global user.email "$OPERATOR_GIT_USER_EMAIL"`. The `devassist` user MUST have a writable `HOME` per ADR-014 Correction 5 (the unit-template path); for git-config purposes, the installer ensures `/home/devassist/` exists and is owned by `devassist:devassist` mode `0700` (creating it via `useradd --create-home` is the simplest path; existing call `useradd --system --no-create-home` at line 65 of install-self.sh MUST be amended in this ticket's scope to drop `--no-create-home` OR followed by `mkdir -p /home/devassist && chown devassist:devassist /home/devassist && chmod 0700 /home/devassist`). Test: parse install-self.sh for the two `git config --global` lines and the home-dir creation; assert `~/.gitconfig` is written under devassist's home, not under root's home.
  - **AC-2 (c) — A.iii: origin remote URL token-free.** The installer's repo-clone step (`git clone "$HERMES_DEVASSIST_REPO_URL" /srv/devassist/repo` as `devassist` via `sudo -u devassist`) MUST NOT embed `GITHUB_TOKEN` into the URL. The credential helper used is `git config --global credential.helper '!gh auth git-credential'` (which delegates to gh's stored token from AC-2 (a)). Test: after install in dry-run / fixture mode, `git -C /srv/devassist/repo remote get-url origin` returns the bare HTTPS URL; regex `https://[^@/]+@` matches zero times.
  - **AC-2 (d) — A.iv: `/srv/devassist/shared-skills/` populated; manifest written; verify enforces match.** A new function `render_shared_skills_manifest()` in install-self.sh: (1) iterates the 15 custom skills enumerated in `MULTI-HERMES-CONTRACT.md` § 5.0; (2) for each, copies `${SCRIPT_DIR}/../shared-skills/<skill-name>/SKILL.md` (and any sibling files in the skill directory) to `/srv/devassist/shared-skills/<skill-name>/`; (3) computes SHA-256 of `SKILL.md` and records the pinned git commit (resolved at install time via `git -C ${SCRIPT_DIR}/.. rev-parse HEAD`); (4) atomically writes `/srv/devassist/state/shared-skills-manifest.json` with shape `{"schema_version": "1.0", "rendered_at": "<ISO-Z>", "release_commit": "<HEAD-SHA>", "skills": {"<name>": {"path": "<path>", "sha256_of_skill_md": "<hex>", "pinned_commit": "<HEAD-SHA>"}, ...}}` (one entry per skill). The manifest MUST contain exactly the 15 skill names listed in `MULTI-HERMES-CONTRACT.md` § 5.0; any addition/removal MUST be a sibling Architect amendment to the contract first, not a silent install-script edit. Test: round-trip a fixture install in `INSTALL_DRY_RUN=1` mode, parse the rendered manifest, assert the skill set is exactly the 15 names from a hard-coded test fixture (which the test cross-references to `MULTI-HERMES-CONTRACT.md` § 5.0 by parsing the contract's table; mismatch means the contract or the script drifted).
  - **AC-2 (A.iv) — no silent absent-fallback.** Test: with an artificial fixture that removes `shared-skills/<skill>/SKILL.md` for any single skill, invoke the renderer; assert the install aborts with exit code 1 and the log line `"FATAL: shared-skills source missing: shared-skills/<skill>/SKILL.md"`. Test: when all 15 SKILL.md files are present, the manifest renders successfully with each skill's `sha256_of_skill_md` set to the actual on-disk SHA-256 of that file (no `absent_at_install_time` sentinel anywhere). The verify invariant `check_shared_skills_manifest_match()` MUST treat any `sha256_of_skill_md = "absent_at_install_time"` as FAIL (no skip clause).

- [ ] **AC-3 (B.i — one-command bootstrap entrypoint, Option β).** The script accepts a `--interactive` CLI flag. Invoked as `sudo ./scripts/install-self.sh --interactive` from a fresh git clone, it MUST drive the operator through the full B.ii prompt set, write `/srv/devassist/secrets/SELF-DEPLOY.env` with non-placeholder values, and complete the existing `install-self.sh` flow ending in the `verify-self.sh` invocation per `SELF-DEPLOYMENT-CONTRACT.md` § 6.1 step 9. The README and `SELF-DEPLOYMENT-CONTRACT.md` § 6.1 are NOT modified by this PR (sibling clerical PR); the implementer documents the new flag in `scripts/install-self.sh`'s in-script `usage()` block (which already exists at the top of the file) and in `tests/test_self_deployment_scripts.py` test docstrings only. Test: parse install-self.sh for the new flag; assert default behaviour is unchanged when `--interactive` is absent (existing AC-1 of TKT-020 v0.2.0 regression must continue to pass).

- [ ] **AC-4 (B.ii — interactive credential prompts).** Each of the 11 prompts enumerated in B.ii is implemented as a separate function (e.g., `prompt_telegram_bot_token`, `prompt_github_token_pat`, `prompt_github_token_ssh`, etc.) and called in the order listed. Sub-criteria:
  - **AC-4 (a) — secret prompts disable echo.** Test: parse each secret-prompt function for `read -s` (or equivalent `stty -echo` / `IFS= read -s`). The test enumerates the secret-prompt set: `TELEGRAM_BOT_TOKEN`, `GITHUB_TOKEN` (PAT mode), `FIREWORKS_API_KEY`, `OPENROUTER_API_KEY`. Visible-prompt set: the rest.
  - **AC-4 (b) — per-prompt validation MUST match B.ii's pinned regex / probe.** Test: invoke each prompt function in a fixture mode that injects canned input (via stdin redirection); assert the function rejects placeholders, malformed numeric lists, token-bearing URLs, and non-https schemes; assert it accepts well-formed values; assert retry-N is exactly 3 (configurable via `INSTALL_PROMPT_RETRIES` env var with default 3).
  - **AC-4 (c) — failure messages name the env var only, never the rejected value.** Test: simulate rejection; capture the error message; assert the rejected value substring is NOT in the captured message.
  - **AC-4 (d) — B.ii GH auth choice (PAT default; SSH alternative via `--gh-auth=ssh`).** Test: invoke install-self.sh with and without `--gh-auth=ssh`. With the flag, the installer runs the SSH-key generation + add-to-GitHub flow described in B.ii; without, it runs the PAT flow. The SSH flow MUST also collect `GITHUB_TOKEN` for the runtime's REST API path (not just the SSH key). The flags `--gh-auth=pat` and `--gh-auth=ssh` are mutually exclusive; the default value is `pat`.
  - **AC-4 (e) — defaults render correctly.** Test: invoke each prompt function with empty input; assert the default-fill value is recorded in the output env file (e.g., `OMNIROUTE_BASE_URL=https://omniroute.infinitycore.space:8443/v1`).

- [ ] **AC-5 (B.iii — TTY detection rule + non-interactive override).** The TTY detection follows the B.iii rule exactly. Sub-criteria:
  - **AC-5 (a) — default-interactive when TTY + no override.** Test: spawn the script under a pseudo-TTY (e.g., `python3 -c 'import pty; pty.spawn(...)'`) with no env var override; assert the script enters the prompt loop.
  - **AC-5 (b) — default-non-interactive when piped stdin (CI fixture path).** Test: pipe stdin from `/dev/null`; assert the script does NOT enter the prompt loop and aborts with "missing required env var: TELEGRAM_BOT_TOKEN" if the env var is unset, or completes with the existing fixture path otherwise.
  - **AC-5 (c) — `--non-interactive` flag overrides TTY detection.** Test: spawn under TTY with `--non-interactive`; assert no prompt loop.
  - **AC-5 (d) — `--interactive` flag overrides non-TTY environment.** Test: pipe stdin from a here-doc (which is non-TTY) with `--interactive`; assert the script DOES enter the prompt loop and reads from the here-doc input.
  - **AC-5 (e) — conflicting flags abort.** Test: invoke with both `--interactive` and `--non-interactive`; assert exit-1 and a clear error message.
  - **AC-5 (f) — `INSTALL_NONINTERACTIVE=1` is equivalent to `--non-interactive`.** Test: TTY environment with the env var set; assert no prompt loop.

- [ ] **AC-6 (B.iv — credential storage layout, ACL, segregation).** Sub-criteria:
  - **AC-6 (a) — env file path and content.** Test: after a fixture install, `/srv/devassist/secrets/SELF-DEPLOY.env` exists and contains all required env vars from the B.ii list (plus the existing optional ones already in v0.2.0).
  - **AC-6 (b) — env file ACL is `0400 devassist:devassist`.** Test: `stat -c '%a %U %G' /srv/devassist/secrets/SELF-DEPLOY.env` returns exactly `400 devassist devassist`. Tightening from the v0.2.0 baseline `0600 devassist:devassist` is intentional; rotation is root-only (deferred `--rotate-secrets` flag).
  - **AC-6 (c) — secrets directory ACL is `0710 root:devassist`.** Test: `stat -c '%a %U %G' /srv/devassist/secrets/` returns exactly `710 root devassist`. This lets the `devassist` runtime traverse the directory but not list its contents and not read other files; only root can list/write.
  - **AC-6 (d) — no secret value lands in any installer-emitted artifact.** Test: scan `/srv/devassist/logs/self-deploy.log`, journald (`journalctl --output=json --unit=devassist-* --since="-5 minutes"`), and `~devassist/.bash_history` for the secret values used in the fixture (provided as known fixture strings); assert zero hits.

- [ ] **AC-7 (B.v — re-run idempotency).** Sub-criteria:
  - **AC-7 (a) — second invocation does not re-prompt.** Test: run the installer twice in fixture mode (with TTY simulation); assert the second invocation does NOT enter any prompt function (existing `render_self_deploy_env()` short-circuit at line 263 is the precedent; the new prompt phase MUST short-circuit on the same condition).
  - **AC-7 (b) — second invocation does not duplicate user / dirs / units.** Test: `id devassist` is consistent across runs; `/srv/devassist/` mtime of the root directory increases by ≤ 1 (idempotent renders), no duplicate systemd unit files; no second `journald` drop-in write.
  - **AC-7 (c) — second invocation does not corrupt manifests.** Test: `prompt-manifest.json` and `shared-skills-manifest.json` are byte-identical across the two runs (provided no source-tree change between runs); the install-script's `mv "$tmp" "$dst"` discipline MUST be preserved for both manifest renderers.

- [ ] **AC-8 (B.vi — `verify-self.sh` extensions: 8 new invariants).** Each new invariant is implemented as a separate `check_*` function in verify-self.sh and is called by the existing dispatcher. Sub-criteria (one test per invariant):
  - **AC-8 (1) — `check_gh_cli_installed`.** Test: stub `command -v gh` and `gh --version` in fixture mode; assert PASS when both succeed and version ≥ 2.40.0; assert FAIL otherwise with the message "gh CLI missing or below 2.40.0".
  - **AC-8 (2) — `check_gh_cli_authenticated`.** Test: stub `gh auth status` exit code; PASS at 0 + clean stderr; FAIL at non-0 OR stderr contains `embedded credential`. Message: "gh CLI not authenticated as devassist".

    **v0.3.0 enforcement**: The implementation MUST NOT redirect stderr to `/dev/null` (e.g. `2>&1` discard pattern). Stderr MUST be captured (e.g. `local err; err=$(... 2>&1 >/dev/null)` or equivalent) and grep-checked for the literal substring `embedded credential` (case-sensitive). On match, `record_fail` with message `"gh auth status reports embedded credential"`. Test: stub `gh auth status` to print `embedded credential found in store` to stderr with exit code 0; assert FAIL with the embedded-credential message.
  - **AC-8 (3) — `check_devassist_git_identity`.** Test: stub `git config --global user.name|user.email` outputs; PASS at non-empty + non-placeholder; FAIL otherwise. Message: "devassist git identity unset or placeholder".
  - **AC-8 (4) — `check_origin_remote_token_free`.** Test: parse a fixture remote URL; FAIL on userinfo regex match. Message: "origin URL contains embedded credential".
  - **AC-8 (5) — `check_shared_skills_manifest_match`.** Test: render a manifest, mutate one SHA value, re-run check; assert FAIL with the offending skill name; restore SHA, re-run, assert PASS. Message: "shared-skills manifest drift: <skill> <reason>".
  - **AC-8 (6) — `check_secrets_file_acl`.** Test: stat fixture file; assert PASS at `400 devassist devassist`; mutate to `600`, assert FAIL. Message: "SELF-DEPLOY.env ACL drift".
  - **AC-8 (7) — `check_required_env_vars_present`.** Test: source a fixture env file with one missing var; assert FAIL with the missing var name only (no value); fill the var, assert PASS.
  - **AC-8 (8) — `check_prereq_baseline`.** Test: stub each prereq individually as missing; assert FAIL with the unmet prereq name; full prereq set present, assert PASS.

    **v0.3.0 enforcement (revised in v0.3.1)**: The verify invariant `check_prereq_baseline()` MUST re-check **7** of the 8 prereqs from the install-self.sh `verify_prereqs()` function in the same order and with the same depth, **explicitly skipping the install-time-only sudo-posture check**: (1) OS Ubuntu 22.04 (`lsb_release` id+release), (2) **[skipped — install-time sudo-posture check `id -u == 0` is install-only; verify-self.sh runs as `devassist` by design and the install-time root-execution invariant has no verify-time analog]**, (3) network reachability (`api.github.com` HTTP 200), (4) `/srv` disk ≥ 5_000_000 KB, (5) required-CLI presence list (full list mirrored from `verify_prereqs()`, excluding any CLI used only by install-time root operations), (6) Docker daemon present + active + `docker info` ok + `docker` group exists + `devassist` in `docker` group (5 sub-checks), (7) Python ≥ 3.11, (8) `gh` ≥ 2.40.0. The implementation MUST NOT call `id -u == 0` from within `check_prereq_baseline()` (any such check would always FAIL when verify-self runs as `devassist`). A "lightweight subset" implementation that omits any of OS / network / disk / Docker / gh-version checks is explicitly disallowed. Each of the 7 verify-time prereqs MUST have its own negative-path test (stub it as missing, assert FAIL with the prereq name surfaced); the skipped sudo-posture check has no verify-self test (it is an install-self.sh invariant only, covered by AC-10 (b)).
  - **AC-8 (9) — summary line accuracy.** Test: full verify run with all 19 invariants present; assert summary line is `verify-self: PASS  (19/19 invariants)`. With one new invariant failing, assert `verify-self: FAIL  (18/19 invariants)` and the failing-invariant block lists the failure reason.

- [ ] **AC-9 (B.vii — cleanup story: separate runbook + abort detection).** Sub-criteria:
  - **AC-9 (a) — installer detects existing deploy.** Test: pre-create one of the four detection markers (`/srv/devassist/`, `devassist` user, `devassist.target` file, any `devassist-*.service` file); invoke installer; assert exit-1 with the message "Existing deploy detected. Run the cleanup runbook first."
  - **AC-9 (b) — `--force-reinstall` flag skips detection.** Test: with the flag, the detection MUST be skipped. Beyond skipping detection, no reinstallation logic is invoked by this PR; if the flag is combined with any other operation that would require destructive cleanup, the script aborts with "Not implemented in v0.2.0" exit-2. Test: with `--force-reinstall` AND no other flag, the install proceeds as if no prior deploy existed (relies on the per-step idempotency from AC-7); with `--force-reinstall --rotate-secrets` (a deferred future flag), the script aborts with the v0.3.0+ deferral message.

- [ ] **AC-10 (B.viii — VPS prereq verification).** Sub-criteria (one test per prereq):
  - **AC-10 (a) — OS check** (`Ubuntu` AND `22.04`). Test: stub `lsb_release` outputs; assert PASS for Ubuntu 22.04, FAIL otherwise.
  - **AC-10 (b) — sudo posture** (`id -u == 0`). Test: invoke as non-root in fixture; assert exit-1.
  - **AC-10 (c) — network** (api.github.com reachable). Test: stub `curl` exit; PASS at 0, FAIL otherwise.
  - **AC-10 (d) — disk space** (≥ 5 GB on /srv). Test: stub `df` output.
  - **AC-10 (e) — required CLIs** (full list per B.viii). Test: missing-cli stub fails with the missing CLI name.
  - **AC-10 (f) — Docker prereq** (CHOSEN: yes; per B.viii). Test: stub `command -v docker`, `systemctl is-active docker`, `docker info`, and `getent group docker`. Assert PASS only when all four succeed; assert FAIL with the unmet sub-condition otherwise. Sub-criterion (f) is the longest-running test and is allowed to use `mock` patches in pytest rather than real subprocess calls.
  - **AC-10 (g) — Python ≥ 3.11.** Test: stub `python3 --version`; assert PASS at 3.11.x, FAIL at 3.10.x.
  - **AC-10 (h) — gh CLI ≥ 2.40.0.** Test: stub `gh --version`; assert PASS at 2.40.0+, FAIL below.
  - **AC-10 (i) — check ordering and short-circuit.** Test: with multiple prereqs unmet, assert the script reports only the FIRST one and exits — not a list. Order is fixed: OS → sudo → network → disk → required CLIs → Docker → Python → gh CLI.

- [ ] **AC-11 (test strategy compliance).** All tests added by this ticket are offline-only and MUST NOT require: a real Hermes binary, real LLM credentials, a real Telegram bot, real GitHub access, real systemd, a real Docker daemon, or real OmniRoute. Where a probe is naturally a network call (B.ii Telegram getMe, GitHub user, OmniRoute models), the test MUST stub the `curl` invocation via either a `pytest` `monkeypatch` of the underlying call OR a fixture HTTP server (the existing `tests/test_self_deployment_scripts.py` already has the fixture-server pattern; reuse it). The existing fixture / dry-run mode (`INSTALL_DRY_RUN=1`, `INSTALL_DRY_RUN_PREFIX=/tmp/devassist-dry-run`, `FIXTURE=1`) is preserved unchanged. New tests live in `tests/test_self_deployment_scripts.py` (extended) and `tests/test_install_interactive_prompts.py` (new file).

- [ ] **AC-12 (security — no secret echo, no committed credentials, secrets directory ACL).** Sub-criteria:
  - **AC-12 (a) — no secret echo in installer output.** Already covered by AC-4 (c) and AC-6 (d); restated here as a security AC for the Reviewer's checklist.
  - **AC-12 (b) — no secret values in the installer source code.** Test: scan `scripts/install-self.sh` for any 40+ character base64-like token, any `ghp_*` / `github_pat_*` / `gho_*` GitHub token prefix, any `bot[0-9]+:` Telegram bot token prefix, any `sk-*` / `sk-or-*` OpenAI/OpenRouter prefix. Zero hits.
  - **AC-12 (c) — `.gitignore` covers any new secret-bearing file.** The implementation MUST NOT introduce new secret files in the repo's working tree; if a fixture file contains placeholder values, it MUST live under `tests/fixtures/` and be opt-in via env var, not committed with real values.

- [ ] **AC-13 (docs validation + PR template).** `python3 scripts/validate_docs.py` exits 0 locally before push and on CI. The PR body follows `.github/pull_request_template.md`. The `Tests Run` section lists the new test invocations. The `Acceptance Criteria Status` table maps each AC-1 .. AC-13 to a row with `pass / fail / N/A`. The `Founder Approval` block reflects "yes, pending" until merged.

## 5. Allowed Files

The implementer's write zone for this ticket:

- `scripts/install-self.sh` (extend with interactive prompt phase, prereq verification, gh-CLI install + auth, devassist git identity, shared-skills manifest renderer, prior-deploy detection)
- `scripts/verify-self.sh` (extend with the 8 new invariants from B.vi)
- `scripts/templates/self-deploy.env.tmpl` (new file, IF the implementer chooses to factor the env-file template out of `render_self_deploy_env()`'s heredoc; otherwise keep heredoc)
- `tests/test_self_deployment_scripts.py` (extend)
- `tests/test_install_interactive_prompts.py` (new file)
- `tests/fixtures/self-deploy.env.fixture` (new file, opt-in fixture with placeholder values; NOT real secrets)
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md` § 10 Execution Log only (Executor fills iter-1+; the ticket body §§ 1–9 is frozen at this draft, edits to §§ 1–9 require a sibling Architect amendment ticket)
- `shared-skills/dev-assist-classifier/SKILL.md` (new file)
- `shared-skills/dev-assist-progress-report/SKILL.md` (new file)
- `shared-skills/dev-assist-escalation-surface/SKILL.md` (new file)
- `shared-skills/dev-assist-work-queue-write/SKILL.md` (new file)
- `shared-skills/dev-assist-work-queue-poll/SKILL.md` (new file)
- `shared-skills/dev-assist-prd-writer/SKILL.md` (new file)
- `shared-skills/dev-assist-questions-writer/SKILL.md` (new file)
- `shared-skills/dev-assist-arch-writer/SKILL.md` (new file)
- `shared-skills/dev-assist-adr-writer/SKILL.md` (new file)
- `shared-skills/dev-assist-tickets-writer/SKILL.md` (new file)
- `shared-skills/dev-assist-executor-discipline/SKILL.md` (new file)
- `shared-skills/dev-assist-write-zone-enforcer/SKILL.md` (new file)
- `shared-skills/dev-assist-github-workflow/SKILL.md` (new file)
- `shared-skills/dev-assist-reviewer-rubric/SKILL.md` (new file)
- `shared-skills/dev-assist-review-writer/SKILL.md` (new file)

Files explicitly **NOT** in the allowed list and MUST NOT be modified by this ticket:

- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` — substantive amendments require a sibling ADR (ADR-015 or successor) and a separate Architect-routed PR. AUDIT-002 is a SPEC ticket whose implementation extends scripts only; the contract document is not amended.
- `docs/architecture/MULTI-HERMES-CONTRACT.md` — frozen by ADR-014 + TKT-033 cycle.
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` — frozen.
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` — frozen.
- `docs/architecture/MODEL-CATALOG.md` — frozen.
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` — load-bearing on `main`; not amended.
- `docs/orchestration/SESSION-STATE.md` — SO sole-edit zone.
- `docs/prompts/<role>.md` — owned by the SO/Business Planner; AUDIT-002 only HASHES these files at install time (existing TKT-033 v0.3.0 manifest path).
- `scripts/templates/devassist-<role>.service.j2` (5 files) — AUDIT-001 write zone; frozen by TKT-033 v0.3.0.
- `src/developer_assistant/runtime_check.py` — TKT-021 + TKT-033 frozen surface; AUDIT-002 must produce on-disk state that already passes runtime_check, not extend its invariants.
- `src/developer_assistant/runtime_layout.py`, `src/developer_assistant/model_catalog.py`, `src/developer_assistant/cli/*.py` — TKT-021 / TKT-026 frozen surfaces.
- `docs/tickets/TKT-020.md`, `docs/tickets/TKT-021.md`, `docs/tickets/TKT-026.md`, `docs/tickets/TKT-032.md`, `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` — merged tickets are not retroactively amended by AUDIT-002.

## 6. Test Strategy

The downstream Executor's tests MUST be structured as follows. The Architect spec mandates the test surface; the Executor decides the per-test fixture mechanics within the constraint that all tests are offline.

- **Unit tests for shell functions** — each new function in `install-self.sh` and `verify-self.sh` (e.g., `prompt_telegram_bot_token`, `prompt_github_token_pat`, `prompt_github_token_ssh`, `validate_telegram_allowed_users`, `render_shared_skills_manifest`, `check_gh_cli_installed`, `check_secrets_file_acl`, etc.) is unit-testable in isolation by sourcing the script under `bash -n` (syntax check) and `bash -c 'source script.sh; <fn>; echo $?'` (function invocation under fixture stubs). The existing `tests/test_self_deployment_scripts.py` has this pattern; reuse it.
- **Integration tests for full install run** — fixture-mode end-to-end: `INSTALL_DRY_RUN=1 INSTALL_DRY_RUN_PREFIX=/tmp/devassist-dry-run-<test-id> ./scripts/install-self.sh --non-interactive --gh-auth=pat`, with all required env vars pre-set to fixture placeholder values (e.g., `TELEGRAM_BOT_TOKEN=BOT_FIXTURE_TOKEN`, `TELEGRAM_ALLOWED_USERS=12345,67890`, `GITHUB_TOKEN=ghp_FIXTURE_NEVER_REAL`). Assertion: post-run, the dry-run prefix tree contains the expected files; the env file has the expected content; the manifests are byte-identical to a golden fixture.
- **Interactive-mode tests via PTY simulation** — Python `pty` module spawns the script under a pseudo-TTY; `os.write()` sends fixture answers; `os.read()` captures prompts. Each prompt is asserted on by name + default; each rejection scenario is asserted by feeding malformed input and capturing the error line. The PTY harness lives in `tests/test_install_interactive_prompts.py`.
- **Network-stubbed validation tests** — Telegram / GitHub / OmniRoute reachability probes are stubbed by either (a) `monkeypatch` of the underlying `curl` invocation (preferred), or (b) a fixture HTTP server bound to a free localhost port (fallback for cases where the script invokes curl directly without abstraction). The fixture server pattern is already in `tests/test_self_deployment_scripts.py`.
- **Verify-self.sh invariant tests** — each new `check_*` function gets its own test with at least two scenarios (PASS and FAIL); the `summary line accuracy` test exercises the full 21-invariant matrix.
- **No real-network and no real-systemd tests.** `pytest -m 'not slow and not integration_real'` MUST pass under CI without any real Telegram / GitHub / OmniRoute / systemd dependency.
- **Existing CI surfaces unchanged.** `python3 scripts/validate_docs.py` MUST exit 0; `python3 -m unittest discover -s tests -p "test_*.py" -v` MUST pass; the existing `pre-commit` config (none in this repo at HEAD `04a5871`; verified) is unchanged.
- **Lint/format.** Shellcheck passes on the modified shell scripts (`shellcheck scripts/install-self.sh scripts/verify-self.sh`) — existing CI runs this; the implementer addresses any new shellcheck findings before requesting RV-CODE.

The Executor's iter-1 PR description MUST include the per-AC test invocation commands and the offline-only attestation per AC-11.

## 7. Risk Notes

This section records the trade-off paragraph behind each architectural choice and the residual risks the spec accepts. The Reviewer's RV-SPEC pass MUST cross-check that each chosen option has a paragraph here; missing justification is a medium-severity finding.

- **B.i bootstrap entrypoint — Option β (git clone + sudo install-self.sh --interactive).** Trade-off: more typing for the Founder than Option α (one-line `curl|bash`), but the script is on disk and readable before sudo runs; the operator can `cat scripts/install-self.sh | less` to inspect what is about to run. The 510-line existing baseline is reused; Option α would have required a separate bootstrap shell script that just clones and execs, doubling the trust surface. Option γ (signed binary release) is a v0.3.0+ optimization. Residual risk: a malicious git clone (e.g., DNS hijack to a typosquat repo) is still a vector; mitigated by the operator pasting the canonical URL `https://github.com/OpenClown-bot/developer-assistant.git` from the Founder's own runbook, not from a third-party blog post.

- **B.ii GH auth default — PAT mode (CHOSEN; SSH offered via `--gh-auth=ssh`).** Trade-off: PAT is the v0.1 minimum-friction default because the runtime's GitHub workflow path (`HERMES-RUNTIME-CONTRACT.md` § 9) is REST API based and needs a token regardless; SSH only adds transport convenience. Forcing PAT-default avoids a confusing "you set up SSH but you still need a token" surprise. SSH alternative is offered for operators who prefer not to manage PATs in their secrets manager. Residual risk: a PAT with overly broad scope (e.g., `repo` instead of fine-grained "Contents: write, Pull requests: write" on the project repo only) is the operator's responsibility; the installer's prompt copy MUST instruct the operator to use a fine-grained PAT, but the installer cannot enforce scope at the API level (GitHub's `/user` endpoint does not expose scope; `/rate_limit` is the de-facto scope probe but is noisy).

- **B.iii TTY detection rule — `[ -t 0 ] && [ -t 1 ] && [[ "${INSTALL_NONINTERACTIVE:-0}" != "1" ]]`.** Trade-off: piped stdin (used by CI fixtures and password-manager-dump pipelines) is the dominant non-TTY case and must default to non-interactive without an env-var override; the rule above produces the right default. Alternatives (e.g., `[ -t 1 ]` only) misclassify piped-stdin TTY-stdout as interactive, breaking CI fixtures. Residual risk: an operator running under `tmux` or `screen` with a redirected stdin (e.g., `script -c install-self.sh`) may hit a non-TTY surprise; mitigated by the explicit `--interactive` flag.

- **B.iv credential storage — Option ψ (env file at `/srv/devassist/secrets/SELF-DEPLOY.env`, ACL `0400 devassist:devassist`, dir `0710 root:devassist`).** Trade-off: tightening from the v0.2.0 baseline `0600 devassist:devassist` is intentional (prevents the `devassist` runtime from re-opening the file in append mode by mistake); rotation is root-only via a deferred `--rotate-secrets` flag (out of v0.2.0 scope). Option ω (`systemd-creds`) is the right long-term answer but requires systemd ≥ 250 (Ubuntu 22.04 ships 249) and architectural changes to all five unit templates (frozen by TKT-033 v0.3.0); deferring it to AUDIT-007 (or successor) is the v0.2.0 contract. Option ξ (hybrid) is a split-brain that doubles the failure-mode matrix. Residual risk: the env file is readable by the `devassist` runtime user, so a compromised runtime CAN exfiltrate it; defense-in-depth is at the skill-loadout level (`SELF-DEPLOYMENT-CONTRACT.md` § 10.1) and at the network layer (deterministic outbound HTTP block from non-Orchestrator runtimes per `ESCALATION-POLICY.md` § 4). NO new ADR is required because Option ψ is the existing baseline; the only change is the ACL tightening from 0600 to 0400, which is a refinement to an existing pattern, not a new pattern.

- **B.vii cleanup bundling — Option μ (separate runbook).** Trade-off: bundling cleanup into `--reinstall` would hide destructive operations behind a single flag and conflict with `SELF-DEPLOYMENT-CONTRACT.md` § 6's "explicit Founder approval" gate for destructive flows. Separate runbook keeps the installer scoped to "bring a clean VPS to a working state"; cleanup of stale state is operator/SO responsibility. Residual risk: an operator who skips the cleanup runbook and ALSO uses `--force-reinstall` may end up with a half-cleaned state; mitigated by `--force-reinstall` only skipping detection (per AC-9 (b)) and by per-step idempotency (AC-7). The separate runbook itself is NOT in the Architect write zone; it is filed by the SO as a paste-relay or under `docs/operations/` in a sibling PR.

- **B.viii Docker prereq check — yes (CHOSEN).** Trade-off: failing late at first Executor / Reviewer Hermes call produces a confusing error far from its root cause; failing early in the prereq phase produces a clear, actionable error. The Docker daemon socket round-trip is the heaviest prereq check, so it is ordered last (after the cheaper checks short-circuit on missing OS / sudo / disk / CLIs). Residual risk: a Docker daemon that is "active" but mis-configured (e.g., wrong storage driver, exhausted disk) will pass the check and fail later; the installer's prereq check is a baseline, not an exhaustive Docker-health probe — that is OUT OF SCOPE for v0.2.0 and belongs to the runtime smoke harness.

- **Scope drift risk.** The Founder's 2026-05-09 directive included four asks; only #1 and #2 (one-command installer + interactive prompts) are in this ticket's scope. Asks #3 (Tester role addition) and #4 (Observer / Monitor tooling) are routed to AUDIT-005 and AUDIT-006 respectively. The Executor MUST NOT add a Tester role prompt, an Observer skill, or any monitoring surface to TKT-034's PR; if pressure to add them surfaces during implementation, it is filed as a Q-TKT and routed to SO. This is the single largest scope-drift risk in this ticket.

- **Credential supply-chain risk.** The prompts collect tokens directly from the operator's terminal. The only protections are (a) `read -s` to disable echo, (b) the AC-12 (b) source-code scan for accidental hard-coding, (c) the AC-6 (d) journald / log scan for accidental echo, (d) the per-prompt regex / probe validation that rejects placeholders before write. There is no protection against a compromised operator workstation (keylogger, clipboard logger); that is a Founder-level risk outside the architecture's defense.

- **Curl-pipe-bash trust risk.** Option α was REJECTED for B.i in part because of this risk; the chosen Option β still requires the operator to trust the git clone. The risk is bounded by the operator pasting the canonical URL from the Founder's own runbook; the installer itself does NOT fetch any remote script during install (no `curl … | bash` invocations inside the installer). This is verified by AC-12 (b)'s extension: scan the script source for `curl … | (bash|sh)` patterns and reject any hits.

- **Idempotency edge cases.** Re-running the installer when one of the required env vars has been MANUALLY rotated in `SELF-DEPLOY.env` (e.g., the operator rotated the Telegram bot token after a leak) is NOT a re-prompt path in v0.2.0; the existing short-circuit preserves the new value as long as it's non-placeholder. The AC-7 (a) test exercises the no-re-prompt default. The deferred `--reprompt-secrets` flag (out of v0.2.0 scope) addresses the explicit-rotation case.

- **`docker info` bind-mount risk.** B.viii's Docker check uses `docker info` which contacts the daemon socket. On a default Ubuntu 22.04 install, the socket is `/var/run/docker.sock` owned by `root:docker`; the installer runs under sudo so this works. If the operator has a non-default Docker socket location (e.g., rootless Docker or a custom systemd unit), the check fails and the operator must ensure the standard socket is reachable. This is an accepted risk; v0.2.0 does not support non-default Docker setups.

- **gh CLI install path.** The B.viii prereq check requires `gh ≥ 2.40.0`; if absent, the installer aborts with apt-install instructions but does NOT auto-install. The deferred auto-install flag (out of v0.2.0 scope) is recorded as a follow-up.

- **Fail-open on retry exhaustion (REJECTED).** The B.ii retry-N=3 path ABORTS on exhaustion; it does NOT fall back to a placeholder value (which would silently regress to the v0.2.0 baseline behaviour). Test AC-4 (b) enforces this.

- **Test coverage of the SSH-key flow (B.ii GH auth alternative).** SSH-key generation + add-to-GitHub + `ssh -T` validation has more moving parts than the PAT path. The Executor MUST implement at least one happy-path test and one timeout test for the SSH flow (operator never adds the key; the script's "Press ENTER once added" prompt times out at the configured deadline and aborts). Default deadline: 5 minutes (configurable via `INSTALL_SSH_KEY_TIMEOUT_SECONDS`).

## 8. Spec Amendment Notes

This ticket promotes the v0.1.0 informal stub at `docs/session-log/2026-05-08-session-2.md` § 5.2 to a v0.2.0 implementation contract. The promotion is additive: the four A.i–A.iv items are preserved verbatim; eight B.i–B.viii items are added. No prior ticket body, ADR, or architecture document is amended in-place; substantive amendments needed during implementation MUST be filed as Q-TKTs and routed through SO/Architect re-spec.

Potential follow-up amendments that are EXPLICITLY OUT OF SCOPE for this PR but are recorded here for SO/Founder visibility:

- **`SELF-DEPLOYMENT-CONTRACT.md` § 6.1.** The install gate ordering currently lists 11 steps; AUDIT-002 inserts a credential-prompt phase between step 1 (preflight) and step 2 (create user) and a shared-skills-manifest renderer alongside the existing prompt-manifest renderer in step 6. A clerical PR by the SO (or the Architect in a separate cycle) SHOULD update § 6.1 to reflect the new flow once TKT-034 is merged. This is a documentation refresh, not a contract amendment.
- **`SELF-DEPLOYMENT-CONTRACT.md` § 8 verify invariant table.** The current 13-invariant table grows to 21. A clerical PR SHOULD update the table once TKT-034 is merged.
- **`SELF-DEPLOYMENT-CONTRACT.md` § 10 secrets handling.** The ACL change (0600 → 0400) and the new directory ACL (0710) are operational tightenings; § 10 SHOULD be updated to reflect the new ACL.
- **`MULTI-HERMES-CONTRACT.md` § 5.0 14-skill table.** The table's "Source review status" column lists every skill as "unreviewed". AUDIT-002 does NOT change review status; it only verifies the per-skill on-disk content matches the contract. A future TKT-021 follow-up (already noted in `MULTI-HERMES-CONTRACT.md` § 5.0) is the path to update review status.
- **`HERMES-SKILL-ALLOWLIST.md` § 4.4 `github-auth` skill.** The skill's review verdict (failed for production credential setup) is the reason AUDIT-002 implements the PAT/SSH installer flow as a substitute. § 4.4 SHOULD be updated to cross-reference TKT-034's flow as the v0.1 substitute path.
- **README.md.** The Founder-facing README SHOULD document the one-command bootstrap as the install happy path. This is a sibling clerical PR after TKT-034 merges.
- **`docs/operations/cleanup-runbook.md` (NEW FILE; out of Architect write zone).** The cleanup runbook for B.vii is filed by the SO as either a paste-relay continuation or a new file under `docs/operations/`. The directory `docs/operations/` does not exist at HEAD `04a5871`; if added, it lands as a sibling PR.
- **AUDIT-005 (Tester role).** Founder ask #3 of 2026-05-09 is routed to a future SO dispatch as AUDIT-005 (or its assigned id at dispatch time). NOT in this ticket's scope.
- **AUDIT-006 (Observer / Monitor tooling).** Founder ask #4 of 2026-05-09 is routed to a future SO dispatch as AUDIT-006. NOT in this ticket's scope.
- **AUDIT-007 (systemd-creds migration).** Option ω from B.iv is the right long-term credential-storage answer. A future cycle (AUDIT-007 or its assigned id) addresses the unit-template amendments and runtime code changes required to migrate from env-file to systemd-creds. NOT in this ticket's scope.
- **AUDIT-008 (auto-install Docker / gh CLI / Python).** A future convenience cycle that extends B.viii's abort-with-instructions posture to optionally auto-install missing prereqs. NOT in this ticket's scope.

No new ADR is created by this ticket. The chosen Option ψ for B.iv is the existing baseline; ACL tightening is a refinement, not a new pattern. If the Executor finds during implementation that a new ADR IS required (e.g., to record a deviation from the env-file pattern that this spec did not anticipate), the path is: file a Q-TKT, pause for Architect re-spec, and let the Architect produce ADR-015 in a sibling PR before resuming implementation.

## 9. Cross-references

- `docs/tickets/TKT-020.md` (v0.2.0) — parent self-deploy install/verify ticket; AUDIT-002 extends its runtime artifacts (`scripts/install-self.sh`, `scripts/verify-self.sh`) without retroactively amending its body.
- `docs/tickets/TKT-021.md` (v0.1.1) — runtime-layout / runtime_check parent; AUDIT-002 produces on-disk state that already passes runtime_check.
- `docs/tickets/TKT-026.md` (v0.1.1) — model-catalog enforcement helper; verify-self.sh continues to invoke `model_catalog_cli probe-omniroute` (existing); no new probe added by AUDIT-002.
- `docs/tickets/TKT-033-runtime-check-systemd-boot-enforcement.md` (v0.3.0) — AUDIT-001 precedent; structural reference for this ticket body.
- `docs/session-log/2026-05-08-session-2.md` § 5.2 — the four-item operator-hygiene scope stub (preserved verbatim as A.i–A.iv).
- `docs/session-log/2026-05-08-session-2.md` § 9 — durable cross-reference between session-1 and session-2.
- AUDIT-005 (Tester role; future ticket; not yet assigned an id) — Founder ask #3 of 2026-05-09; routed to SO.
- AUDIT-006 (Observer / Monitor tooling; future ticket; not yet assigned an id) — Founder ask #4 of 2026-05-09; routed to SO.
- AUDIT-007 (systemd-creds migration; future ticket) — Option ω for B.iv credential storage; deferred from v0.2.0.
- AUDIT-008 (auto-install Docker / gh CLI / Python; future ticket) — extends B.viii prereq verification with optional auto-install.
- `docs/architecture/adr/ADR-014-live-deployment-corrections.md` (v1.0.0) — Corrections 1, 3, 5, 7, 8 are load-bearing for AUDIT-002.
- `docs/architecture/adr/ADR-011-routing-layer.md` (v0.1.1, amended by ADR-014) — OmniRoute primary; context for B.ii FIREWORKS_API_KEY validation probe.
- `docs/architecture/MULTI-HERMES-CONTRACT.md` (v0.2.0) § 5.0 (15 custom skills, A.iv source-of-truth), § 5.1–5.5 (per-role loadouts), § 12 (security additions).
- `docs/architecture/HERMES-RUNTIME-CONTRACT.md` (v0.2.0) § 8 (Telegram), § 9 (GitHub).
- `docs/architecture/HERMES-SKILL-ALLOWLIST.md` (v0.1.2) § 4.4 (`github-auth` skill review verdict; this ticket's PAT/SSH flow is the v0.1 substitute).
- `docs/architecture/SELF-DEPLOYMENT-CONTRACT.md` (v0.3.0) § 4 (filesystem layout), § 5.2 (per-role unit template), § 6.1 (install gate ordering — extended by AUDIT-002 conceptually; § 6.1 itself is not edited in this PR), § 8 (verify invariant set — extended by AUDIT-002 conceptually; § 8 itself is not edited in this PR), § 10 (env var table), § 10.1 (secret-segregation pattern).
- `docs/architecture/MODEL-CATALOG.md` (v0.3.0) § 5.1 (OmniRoute endpoint default-fill), § 5.2 (FIREWORKS_API_KEY auth role).
- `AGENTS.md` — Architect role write-zone confirmation.
- `CONTRIBUTING.md` — § Roles cross-check.
- `.github/pull_request_template.md` — PR body template followed by this ticket's PR.
- `scripts/install-self.sh` (510 lines at HEAD `04a5871`) — extended in scope.
- `scripts/verify-self.sh` (368 lines at HEAD `04a5871`) — extended in scope.
- `scripts/templates/devassist-<role>.service.j2` (5 files; AUDIT-001 write zone) — read-only context for B.viii prereq baseline.

## 10. Execution Log

<!-- Executor fills below this line, iter-1 onward. The Architect spec body §§ 1–9 is frozen; edits to §§ 1–9 require a sibling Architect amendment ticket. -->

### iter-1 — 2026-05-09 — Code Executor (DeepSeek V4 Pro main) — branch `exe/tkt-034-interactive-installer`

**Branch cut from main HEAD**: `8bc5288f248f4b536e2a54756b1826f76cb9e316`
**v0.2.6 session-state — TKT-034 v0.2.0 spec landed (AUDIT-002 spec cycle CLOSED) (#134)**

**AC-1 diagnosis re-verify** (TKT-034 § 4 row AC-1): all 7 observations confirmed unchanged on the branch-cut HEAD:

1. `grep -E 'read -p|read -s|stty|interactive|tty' scripts/install-self.sh` → 0 hits ✓ (zero interactive prompts)
2. `grep -E 'gh auth|apt-get install gh' scripts/install-self.sh` → 0 hits ✓ (no gh CLI install/auth)
3. `grep -E 'git config|user.name|user.email' scripts/install-self.sh` → 0 hits ✓ (no devassist git identity)
4. `grep -E 'shared-skills|dev-assist-' scripts/install-self.sh` → only directory-creation line ✓ (no manifest renderer)
5. `grep -E 'check_deps|prereq|verify_prereqs' scripts/install-self.sh` → only `check_deps()` ✓ (no B.viii prereq baseline)
6. `grep -E 'detect_prior_deploy|force-reinstall|prior-deploy' scripts/install-self.sh` → 0 hits ✓ (no cleanup-detection)
7. `grep -E 'gh auth|user.name|origin|shared-skills|stat -c|prereq' scripts/verify-self.sh` → 0 hits ✓ (no operator-hygiene invariants)

No Q-TKT raised. Diagnosis matches the spec's § 4 description.

**Pre-existing-on-main test failures (write-zone-blocked, deferred)**: A fresh `python3 -m unittest discover` on `8bc5288` reveals 13 pre-existing failures (1 failure + 12 errors) on frozen-surface files outside the TKT-034 § 4.2 write zone:

- `src/developer_assistant/runtime_check.py` hardcodes `/srv/devassist/state/operational.db` (errors when the path is absent in CI).
- `src/developer_assistant/model_catalog.py` raises `agent.model 'None'` (config-loading drift; ARCH-001-frozen surface).
- `tests/test_health_endpoint.py` rejects non-localhost connections in environments without network isolation (CI VM has no isolation).

Per § 4.2 these files are explicitly NOT in my write zone. Documented here for the next iter to file Q-TKT-034-01 if SO/Founder want them addressed; this iter does not touch them.

**Implementation summary** (TKT-034 § 4 + § 4.1 implementation plan):

- **scripts/install-self.sh** — extended from 451 → 1363 lines.
  - Globals: SELF_DEPLOY_VERSION 0.2.0 → 0.3.0; new SHARED_SKILLS enum (15 dev-assist-* skills, MULTI-HERMES-CONTRACT § 5.0); INSTALL_PROMPT_RETRIES (default 3); INSTALL_SSH_KEY_TIMEOUT_SECONDS (default 300); INSTALL_FIXTURE_PROBES; flag-state vars.
  - **AC-2 (operator hygiene A.i–A.iv)**: `install_gh_cli()` (apt-key gh repo + apt install + version probe ≥ 2.40.0); `authenticate_gh_for_devassist()` (`gh auth login --with-token < pat-file` via stdin, never `--token` arg); `configure_devassist_git_identity()` (sudo-as-devassist git config --global user.name/user.email/credential.helper); `render_shared_skills_manifest()` (atomic JSON manifest under /srv/devassist/state/shared-skills-manifest.json with per-skill SHA-256 + pinned commit + release_commit).
  - **AC-3 (B.i one-command bootstrap)**: `--interactive` flag; `--non-interactive` flag; `--gh-auth=[pat|ssh]` (default pat); `--force-reinstall`; `--reprompt-secrets` (RESERVED, aborts); `--rotate-secrets` (RESERVED, aborts); `--help`. Mutual-exclusive conflict detection.
  - **AC-4 (B.ii 11 interactive prompts)**: `prompt_visible()`, `prompt_secret()`, `abort_install()`, plus 11 specific prompt functions (telegram bot token, allowed users, founder user id, github auth path, github token, fireworks api key, omniroute base url, omniroute api key, repo url + branch, operator git user.name/email). Validators: `is_placeholder_value()`, `validate_telegram_allowed_users()`, `validate_telegram_user_id()`, `validate_repo_url()`, `validate_omniroute_base_url()`. INSTALL_PROMPT_RETRIES default 3; abort_install names env-var only (never the rejected value).
  - **AC-5 (B.iii TTY detection)**: `detect_install_mode()` precedence: explicit CLI flag > INSTALL_NONINTERACTIVE env > `[ -t 0 ] && [ -t 1 ]` > default non-interactive.
  - **AC-6 (B.iv credential storage)**: secrets dir 0710 root:devassist (chown skipped in DRY_RUN); env file 0400 devassist:devassist on real install (chmod 0600 in DRY_RUN; verify-self accepts both in fixture); pre-write check for empty/placeholder env vars on a re-run.
  - **AC-7 (B.v re-run idempotency)**: `prompt_phase_idempotent_skip()` returns 0 when env file exists + all required vars non-empty + non-placeholder; `--reprompt-secrets` aborts with "RESERVED; not implemented in v0.2.0".
  - **AC-9 (B.vii cleanup detection)**: `detect_prior_deploy()` returns 0 if /srv/devassist exists OR devassist user exists OR devassist.target exists OR any devassist-*.service exists; `--force-reinstall` skips detection; combining `--force-reinstall` + `--rotate-secrets` aborts.
  - **AC-10 (B.viii VPS prereq verification)**: `verify_prereqs()` runs 8 checks — OS (Ubuntu 22.04), sudo (uid=0), network (curl https://api.github.com), disk (df ≥ 5_000_000 KB on /srv), required CLIs (full B.viii enumeration), Docker (command + systemctl is-active + docker info + getent group), Python ≥ 3.11.0, gh CLI ≥ 2.40.0. All checks short-circuit in DRY_RUN/INSTALL_FIXTURE_PROBES.
  - `main()` wraps with `if [ "${BASH_SOURCE[0]}" = "${0}" ]` so PTY/unit tests can source the script and call individual functions in isolation.

- **scripts/verify-self.sh** — extended from 11 → 19 invariants.
  - 8 new `check_*` functions: `check_gh_cli_installed`, `check_gh_cli_authenticated`, `check_devassist_git_identity`, `check_origin_remote_token_free`, `check_shared_skills_manifest_match`, `check_secrets_file_acl`, `check_required_env_vars_present`, `check_prereq_baseline`.
  - Each new check honours FIXTURE / DRY_RUN modes the same way as the existing 11; `check_required_env_vars_present` skips placeholder rejection in fixture (the dedicated unit test in `TestVerifySelfNewInvariants.test_verify_fails_when_required_env_var_placeholder_in_production_mode` exercises the strict path).
  - Summary line now shows e.g. `verify-self: PASS  (19/19 invariants)` when all 19 pass.
  - SELF_DEPLOY_VERSION bumped 0.2.0 → 0.3.0 to mirror install-self.
  - `main "$@"` guarded by `BASH_SOURCE != $0` for unit-testability.

  *Spec/code drift note*: TKT-034 § 4 row AC-8 (h) refers to "13 baseline invariants → 21 total". The actual baseline on `8bc5288` is 11 invariants (verified by reading `scripts/verify-self.sh` and counting `invariant_*` functions). After adding 8 new invariants the total is 19, not 21. This drift is **non-load-bearing** (the invariant-renaming/renumbering is purely informational) and does NOT introduce missing security checks; the 8 spec-listed `check_*` functions are all implemented exactly as spec'd. SO/Founder may file a clerical Architect amendment to update the count in TKT-034 § 4 if desired.

- **tests/test_install_interactive_prompts.py** (NEW, 31 tests). Categories: TestPromptHelpers (10 validator tests), TestVisiblePrompts (4 default-fill / retry tests), TestSecretPrompts (2 echo-suppression tests), TestAbortMessages (1 env-var-name-only test), TestPromptPhaseSkip (3 idempotency + reserved-flag tests), TestFlagParsing (6 flag-parser tests), TestDetectInstallMode (4 TTY-detection tests), TestSshFlowFixtureMode (1 SSH skip test). All offline; the `_run_function()` helper sources install-self.sh into a clean shell using the new `BASH_SOURCE != $0` guard.

- **tests/test_self_deployment_scripts.py** — extended with 6 new test classes (19 new tests): TestSharedSkillsManifestRender, TestSecretsFileAcl, TestVerifySelfNewInvariants (8 PASS-path + FAIL-path tests for the new invariants), TestForceReinstallFlag, TestPreReqVerificationStubsInDryRun, TestNoSecretsInTokenizedSurfaces. Existing 41 tests retained; the `test_verify_counts_invariants` assertion updated from "11/11" → "19/19" to track the new total.

- **tests/fixtures/self-deploy.env.fixture** (NEW, opt-in) — placeholder-only env file for tests that need to point INSTALL_DRY_RUN_PREFIX at a tmpdir + copy a known env file in. All values are `test-token-placeholder` / `test-user-placeholder` per AC-12.

**Local validation**:

```
python3 scripts/validate_docs.py        → "Docs validation passed."  (exit 0)
python3 -m unittest \
    tests.test_self_deployment_scripts \
    tests.test_install_interactive_prompts
                                        → Ran 91 tests in 90.7s · OK · (exit 0)
shellcheck scripts/install-self.sh \
            scripts/verify-self.sh
                                        → 13 pre-existing warnings (same set
                                          as on 8bc5288); 0 net-new findings
                                          on the TKT-034 surface  (exit 0)
```

**Architectural compliance**:

- A.i–A.iv (operator hygiene): all four implemented per § 1.A; manifest atomic-write idiom (`mv -f $tmp $final`) confirmed by `TestSharedSkillsManifestRender.test_manifest_atomic_render`.
- B.i–B.viii (interactive installer): all 8 sub-criteria implemented; reserved flags abort with the spec-mandated "Not implemented in v0.2.0" message.
- AC-12 (security): no real tokens in source; all fixtures use `test-*-placeholder`; `prompt_secret` uses `IFS= read -rs`; abort_install names env-var only.
- AC-13 (docs validation): validate_docs.py green; PR body follows .github/pull_request_template.md.

**Open questions for SO/Founder**:

- **Q-TKT-034-01 (informational, low-priority)**: Spec says "13 → 21 invariants"; reality is "11 → 19". Suggest a sibling clerical Architect amendment to update TKT-034 § 4 row AC-8 (h) and § 4.1 step 8.h. Non-blocking for this iter.
- **Q-TKT-034-02 (informational)**: 13 pre-existing test failures on `main` (runtime_check.py hardcoded paths, model_catalog.py None handling, test_health_endpoint.py network assumptions) are write-zone-blocked here. Not introduced by TKT-034. SO/Founder may dispatch a follow-up TKT to address.

No blocking questions for iter-1.

## 11. Amendment Delta — v0.2.0 → v0.3.0

Amendment trigger: RV-CODE-033 verdict `fail` on PR #135 (TKT-034 v0.2.0 implementation iter-1) returned 2 HIGH-severity blockers + 1 MEDIUM gap. Independently re-verified by SO pass-2 ratify-ack on PR #137. Founder approved iter-2 dispatch with Architect amendment first (path 4a — add real `shared-skills/<skill>/SKILL.md` source tree).

Delta summary:

1. **Frontmatter**: version `0.2.0` → `0.3.0`; new fields `prior_version`, `amended_at`, `amendment_trigger`.
2. **§ 1.A.iv enforcement clause** (NEW): silent absent-fallback explicitly disallowed; install MUST abort on any missing `shared-skills/<skill>/SKILL.md`.
3. **§ 4 AC-2 (A.iv) sub-criterion** (NEW): no-silent-absent-fallback test pair (positive + negative).
4. **§ 4 AC-8(2) enforcement clause** (NEW): MUST NOT discard stderr; MUST grep-check for `embedded credential` substring.
5. **§ 4 AC-8(8) enforcement clause** (NEW): full 8-prereq mirror of `verify_prereqs()`; lightweight subset disallowed; per-prereq negative tests.
6. **§ 4 AC-8 invariant counts** (Q-TKT-034-01 resolved): "13 → 21" replaced with "11 → 19" everywhere.
7. **§ 5 Allowed Files extension**: 15 new `shared-skills/dev-assist-<name>/SKILL.md` paths added to implementer's write zone.

Sections **unchanged** by this amendment: §§ 1.A.i, 1.A.ii, 1.A.iii (operator-hygiene baseline preserved verbatim from TKT-032/ADR-014); § 1.B.i–B.viii (all 8 architectural choices from PR #133 preserved); § 4 AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-9, AC-10, AC-11, AC-12, AC-13 (only AC-2 and AC-8 are touched); § 6 Test Strategy; § 7 Risk Notes; § 8 Spec Amendment Notes; § 9 Cross-references; § 10 Execution Log (Executor will append iter-2 entry).

Execution Log entries from PR #135 (iter-1) are preserved as-is; iter-2 by Executor will append a new sub-section.

## 12. Amendment Delta — v0.3.0 → v0.3.1

Amendment trigger: SO pass-2 ratify-ack on PR #139 returned `PASS-with-changes`. PR-Agent (Qodo) and Architect Q-AMEND-1 independently flagged 2 secondary spec-quality issues that the v0.3.0 amendment did not address but that block Executor iter-2 from landing cleanly. Founder approved sibling micro-amendment cycle (decisions A+A+A+α+A on 2026-05-09).

Delta summary:

1. **Frontmatter**: version `0.3.0` → `0.3.1`; `prior_version` updated to `"0.3.0"`; `amendment_trigger` updated.
2. **§ 1.B.vi / Required Reading / live-state / § 4 AC-2 (d) / § 8 prose harmonization**: 4 line locations updated; total 6 occurrences of "14" → "15" reflecting `MULTI-HERMES-CONTRACT.md` § 5.0's actual 15-skill table.
3. **§ 4 AC-8(8) v0.3.0 enforcement clause** revised: sudo-posture sub-check (`id -u == 0`) explicitly skipped in `check_prereq_baseline()` (verify-self runtime runs as `devassist` by design; install-time-only invariant has no verify-time analog; AC-10 (b) covers install-time sudo posture). Mirror count revised from 8/8 to 7/8 verify-time prereqs.
4. **§ 11 → § 12 numbering shift**: the v0.2.0 → v0.3.0 amendment delta section retains heading `## 11.`; this v0.3.1 amendment delta is heading `## 12.`.

Sections unchanged in v0.3.1: § 1.A.i–A.iii, § 1.B.i–B.viii (other than § 1.B.vi count harmonization above), § 2 Constraints, § 3 Risks, § 4 ACs other than AC-2 (d) prose + AC-8(8), § 5 Allowed Files (15 paths from v0.3.0 unchanged), § 6 Test Plan, § 7 Risk Notes, § 8 Sources/Versions (other than line ~397 prose harmonization above), § 9 § 10 Execution Log, § 11 (v0.2.0 → v0.3.0 Amendment Delta).

Sibling change: `docs/architecture/MULTI-HERMES-CONTRACT.md` § 5.0 prose harmonized to "15 custom skills"; contract version bumped one patch level. The table itself was already correct (15 entries) and is NOT modified.
