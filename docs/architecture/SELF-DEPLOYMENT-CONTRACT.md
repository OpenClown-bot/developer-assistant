---
id: SELF-DEPLOYMENT-CONTRACT
version: 0.3.0
status: draft
amendments: ADR-014 (live deployment corrections from TKT-032, 2026-05-08)
---

# Self-Deployment Contract

## 1. Purpose

This document defines the v0.1 contract for **self-deployment** of `developer-assistant` onto a Founder-owned Ubuntu 22.04 LTS VPS. It satisfies `PRD-001.md` § 12 (self-deployment as a v0.1 prerequisite) and § 12.5 (three approval gates: `install`, `start`, `upgrade`). It is distinct from `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md`, which governs deployment of projects the assistant generates for the Founder.

The contract is a boundary specification: it states what the install, verify, rollback, and upgrade entry points must do, what filesystem layout they create, what systemd units they manage, and what Founder-visible behavior they exhibit. It does not include shell-script source code (Executors implement that under TKT-020).

## 2. Scope

In scope for v0.1:

- One-command **install** that lays down the multi-Hermes runtime layout, installs the Hermes Agent foundation once, configures five per-runtime `HERMES_HOME` directories, renders systemd unit templates, runs preflight checks, and stops without starting any runtime.
- One-command **verify** that runs the connectivity-only health invariant set and returns non-zero on failure.
- One-command **rollback** that restores the last `operational.db` backup (the shared operational store) and the last known-good runtime config tarball, then restarts units that were running prior to rollback.
- One-command **upgrade** that takes a state-store backup, fetches the new release, runs install in-place, runs verify, and surfaces a Founder approval prompt before activating units running the new version.
- Three approval gates per `PRD-001.md` § 12.5: `install` (no approval), `start` (explicit Founder approval), `upgrade` (explicit Founder approval AND a state-store backup).
- A single secrets file (`/srv/devassist/secrets/SELF-DEPLOY.env`) the install script reads and the systemd units load via `EnvironmentFile=`.

Out of scope for v0.1:

- Auto-start on VPS reboot (default: manual; `PRD-001.md` § 10 Q13).
- Public-internet exposure of the VPS (Telegram polling mode keeps the VPS outbound-only; `HERMES-SKILL-ALLOWLIST.md` § 4.1).
- Multi-VPS deployment, hot-swap, blue/green deploy, or live migration.
- Paid third-party deploy targets (Modal, Daytona, Vercel sandboxes, hosted Postgres, hosted vector store, hosted Letta, etc.).
- Generated-project deployment (governed by `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md`).

## 3. Founder-Visible Surface

The Founder sees four entry points in the repository, all under `scripts/`:

| Entry point | Purpose | Approval gate |
| --- | --- | --- |
| `scripts/install-self.sh` | One-command install. Idempotent. | None for `install` per `PRD-001.md` § 12.5. |
| `scripts/verify-self.sh` | One-command health verification. Non-zero exit on any failed invariant. | None. |
| `scripts/rollback-self.sh` | One-command rollback to last known-good. | None to invoke; rollback itself does not change scope. |
| `scripts/upgrade-self.sh` | One-command upgrade. Internally takes a state-store backup, fetches the new release, runs install, runs verify, and stops at the activation gate awaiting Founder approval. | `upgrade` requires explicit Founder approval **and** a state-store backup taken before activation. |

The `start` gate is exercised inside `install-self.sh` (and inside `upgrade-self.sh`). Install/upgrade does **not** auto-start. The script ends with a clear instruction to run a single `systemctl start devassist.target` command (or `--start` flag on the script) once the Founder approves.

All four scripts are short, observable, and rely on standard Ubuntu 22.04 LTS tooling (`bash`, `systemctl`, `journalctl`, `sqlite3`, `tar`, `curl`, `git`). No language runtime is required to run the scripts themselves.

## 4. Filesystem Layout

The install script lays down this layout. All paths are owned by the `devassist` system user (uid/gid created by the script if missing) unless otherwise noted.

```
/usr/local/lib/hermes-agent/                   # Hermes Agent install (one copy, shared)
                                               # owner: root:root, mode 0755
/srv/devassist/
├── repo/                                      # git checkout of OpenClown-bot/developer-assistant
│   └── ...                                    # owner: devassist:devassist
├── runtimes/                                  # one Hermes HERMES_HOME per role
│   ├── orchestrator/
│   │   └── .hermes/
│   │       ├── config.yaml
│   │       ├── .env -> /srv/devassist/secrets/SELF-DEPLOY.env  (symlink)
│   │       ├── auth.json
│   │       ├── SOUL.md
│   │       ├── memories/{MEMORY.md, USER.md}
│   │       ├── sessions/
│   │       ├── state.db                                       # Hermes native sessions index (per-runtime, NOT a symlink)
│   │       ├── operational.db -> /srv/devassist/state/operational.db  (symlink to shared operational store)
│   │       ├── cron/
│   │       ├── logs/
│   │       └── skills/                        # per-runtime skills (mostly built-in references)
│   ├── planner/.hermes/...                    # same shape
│   ├── architect/.hermes/...
│   ├── executor/.hermes/...
│   └── reviewer/.hermes/...
├── shared-skills/                             # custom dev-assist-* skills, loaded by all runtimes
│   ├── dev-assist-classifier/SKILL.md
│   ├── dev-assist-progress-report/SKILL.md
│   ├── dev-assist-escalation-surface/SKILL.md
│   ├── dev-assist-work-queue-write/SKILL.md
│   ├── dev-assist-work-queue-poll/SKILL.md
│   ├── dev-assist-prd-writer/SKILL.md
│   ├── dev-assist-questions-writer/SKILL.md
│   ├── dev-assist-arch-writer/SKILL.md
│   ├── dev-assist-adr-writer/SKILL.md
│   ├── dev-assist-tickets-writer/SKILL.md
│   ├── dev-assist-executor-discipline/SKILL.md
│   ├── dev-assist-write-zone-enforcer/SKILL.md
│   ├── dev-assist-github-workflow/SKILL.md
│   ├── dev-assist-reviewer-rubric/SKILL.md
│   └── dev-assist-review-writer/SKILL.md
├── shared-plugins/                            # Python plugin packages (installed via pip)
│   ├── dev-assist-escalation-policy/
│   └── dev-assist-work-queue/
├── state/
│   ├── operational.db                         # the SQLite operational store (shared by all five runtimes); mode 0640
│   └── backups/                               # rotating snapshots; mode 0700
│       └── operational-YYYYMMDD-HHMMSS.db
├── secrets/
│   └── SELF-DEPLOY.env                        # mode 0600, owner devassist:devassist
├── releases/
│   ├── current -> /srv/devassist/releases/<release-id>/  (symlink)
│   ├── previous -> ...                                    (symlink)
│   └── <release-id>/                          # snapshot of repo + shared-skills + shared-plugins
├── omniroute/                                 # OmniRoute working tree (ONLY when OmniRoute is local per ADR-014 Correction 1; omitted for remote OmniRoute)
│   ├── omniroute.db                           # OmniRoute's own state DB (provider registry, alias map, FIREWORKS_API_KEY) — only for local OmniRoute
│   └── logs/
├── web/
│   └── templates/                             # HTML templates for dev-assist-cli serve-web (per ADR-013)
└── logs/
    └── self-deploy.log                        # install/verify/rollback/upgrade trace
```

Additional v0.2.0 paths laid down by the install script (outside `/srv/devassist/`):

```
/opt/dev-assist/bin/dev-assist-cli              # operator CLI + web server binary (ADR-010 / TKT-027 / ADR-013)
/opt/omniroute/                                 # OmniRoute v3.7.x install root (ADR-011); owner: omniroute:omniroute — ONLY when OmniRoute is local per ADR-014 Correction 1
/etc/systemd/journald.conf.d/dev-assist.conf    # journald drop-in (FR-OBS-09a; ADR-010)
```

Notes:

- Per-runtime `HERMES_HOME` directories share the SQLite operational store via the symlink `operational.db -> /srv/devassist/state/operational.db`. This is the explicit mechanism that lets all five runtimes see the same `work_items` and `escalations` tables (`MULTI-HERMES-CONTRACT.md` § 6, `OPERATIONAL-STATE-STORE.md` v0.2.1).
- The per-runtime `state.db` (Hermes' native sessions index, FTS5 over JSONL transcripts) is **not** a symlink and **not** shared. It lives inside each runtime's `HERMES_HOME` directory and is owned by the Hermes runtime itself (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.5). The `state.db` and `operational.db` filename-distinction prevents the upstream Hermes default-layout collision flagged in RV-SPEC-010 CRIT-1.
- The `.env` symlink to `/srv/devassist/secrets/SELF-DEPLOY.env` makes each runtime see the same secret values (Telegram bot token, GitHub PAT, OmniRoute API key, etc.) without duplicating the secrets file. Although all five units load the same env file, only the Orchestrator's `config.yaml` enables `gateway.enabled: true` and loads the `telegram-gateway` skill, so non-Orchestrator runtimes cannot reach the Telegram API even though `TELEGRAM_BOT_TOKEN` is present in their environment. § 10 elaborates on this defense-in-depth pattern.
- Per-runtime `memories/`, `sessions/`, `cron/`, and `logs/` directories are NOT shared. Memory isolation between runtimes is **filesystem-level**: enforced by distinct `HERMES_HOME` paths plus the systemd sandbox directives in § 5.2 (`ProtectHome=`, `ReadOnlyPaths=`, `ReadWritePaths=`, `BindReadOnlyPaths=`, `PrivateTmp=`). All five runtimes share the `devassist` Linux uid; the isolation is conditional on correct systemd unit configuration (`ARCH-001.md` § 11.1).
- The `releases/current` symlink is the activation surface. Upgrade flips it from the previous release to the new one **only** after the Founder approves.

## 5. systemd Units

Eight unit files are written by the install script when OmniRoute is local (v0.2.0 adds `omniroute.service` per ADR-011 and `devassist-web.service` per ADR-013 to the v0.1.1 set of six). When OmniRoute is remote (ADR-014 Correction 1), seven unit files are written — `omniroute.service` is omitted:

```
/etc/systemd/system/devassist.target
/etc/systemd/system/devassist-orchestrator.service
/etc/systemd/system/devassist-planner.service
/etc/systemd/system/devassist-architect.service
/etc/systemd/system/devassist-executor.service
/etc/systemd/system/devassist-reviewer.service
/etc/systemd/system/omniroute.service          # ONLY when OmniRoute is local (OMNIROUTE_BASE_URL=localhost)
/etc/systemd/system/devassist-web.service
```

`omniroute.service` and `devassist-web.service` are both `PartOf=devassist.target` and listed in the target's `Wants=` / `After=`. `omniroute.service` is sequenced **before** the five specialist runtimes so the routing layer is up by the time any runtime issues an LLM call; `devassist-web.service` is sequenced **after** all five runtimes so the web surface only renders once per-runtime health endpoints are reachable.

### 5.1 Umbrella target

`devassist.target` is the umbrella unit. `systemctl start devassist.target` starts all five runtimes; `systemctl stop devassist.target` stops them. `systemctl status devassist.target` shows aggregate status. The target's `Wants=` and `After=` entries reference all five runtime units.

### 5.2 Per-runtime service template

Each `devassist-<role>.service` follows this template (Executor implementation under TKT-020):

```
[Unit]
Description=developer-assistant <role> Hermes runtime
PartOf=devassist.target
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=devassist
Group=devassist
WorkingDirectory=/srv/devassist/runtimes/<role>
Environment=HERMES_HOME=/srv/devassist/runtimes/<role>/.hermes
Environment=HOME=/srv/devassist/runtimes/<role>
Environment=HERMES_DEVASSIST_ROLE=<role>
EnvironmentFile=/srv/devassist/secrets/SELF-DEPLOY.env
# ExecStart is role-specific (see § 5.2.1 for the per-role table). Default below is the specialist (non-gateway) runtime.
ExecStart=/usr/local/bin/hermes run
Restart=on-failure
RestartSec=10s

# Sandboxing
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
# Read-only by default for everything under /srv/devassist; ReadWritePaths below override this carve-out for the runtime's own directory plus shared writable paths.
ReadOnlyPaths=/srv/devassist
ReadWritePaths=/srv/devassist/runtimes/<role> /srv/devassist/state /srv/devassist/logs
# Other runtime directories and the read-only shared assets are explicitly bound read-only as defense-in-depth, even though same-uid DAC alone is acceptable in v0.1.
BindReadOnlyPaths=/srv/devassist/repo /srv/devassist/shared-skills /srv/devassist/shared-plugins /srv/devassist/releases

[Install]
WantedBy=devassist.target
```

### 5.2.1 Per-Role `ExecStart` And Overrides

The template above defaults to the specialist (non-gateway) runtime. The install script renders one unit per role with the following exact `ExecStart` and overrides:

| Role | `ExecStart` | Other overrides |
| --- | --- | --- |
| `orchestrator` | `/usr/local/bin/hermes gateway run` | Loads `telegram-gateway` skill (only runtime that does); `gateway.enabled: true` in `config.yaml`. |
| `planner` | `/usr/local/bin/hermes run` | `gateway.enabled: false`; no `telegram-gateway` skill loaded. |
| `architect` | `/usr/local/bin/hermes run` | `gateway.enabled: false`; no `telegram-gateway` skill loaded. |
| `executor` | `/usr/local/bin/hermes run` | `gateway.enabled: false`; `SupplementaryGroups=docker` so the Hermes terminal Docker backend can reach `/var/run/docker.sock`. |
| `reviewer` | `/usr/local/bin/hermes run` | `gateway.enabled: false`; `SupplementaryGroups=docker`; Docker sandbox runs with read-only bind of the project repo (`HERMES-SKILL-ALLOWLIST.md` § 4.6). |

`hermes gateway run` and `hermes run` are distinct entry points in Hermes Agent v2026.4.30 (`RESEARCH-001-hermes-and-openclaw-ecosystems.md` § 3.6). The specialist runtimes never invoke the gateway entry point and never expose any inbound listener; they are pure tool-using agent loops driven by `dev-assist-work-queue-poll` and `cronjob`. This eliminates the ambiguity flagged in RV-SPEC-011 MAJ-2 about whether `hermes gateway run` would gracefully degrade to a non-gateway worker when `gateway.enabled: false`.

### 5.3 OmniRoute routing layer configuration

**Amended per ADR-014 Correction 1 (2026-05-08):** OmniRoute runs on a remote host, not on the VPS as a local systemd unit. The prior `omniroute.service` unit template is removed. The routing layer is configured via the `OMNIROUTE_BASE_URL` environment variable.

The routing layer (ADR-011 v0.1.1) is configured as follows:

| Configuration mode | When | `OMNIROUTE_BASE_URL` value | Systemd unit |
| --- | --- | --- | --- |
| Remote OmniRoute (current deployment) | `OMNIROUTE_BASE_URL` points to a remote host | `https://omniroute.infinitycore.space:8443/v1` (or equivalent) | None — no local `omniroute.service` needed |
| Local OmniRoute (future option) | `OMNIROUTE_BASE_URL` is unset or `http://127.0.0.1:20128` | `http://127.0.0.1:20128` | `omniroute.service` (per ADR-011 original text) |

When OmniRoute is remote:

- No `omniroute` Linux user or `/opt/omniroute/` install directory is created.
- No `omniroute.service` unit is rendered.
- The `omniroute/` working tree under `/srv/devassist/` is not created.
- `FIREWORKS_API_KEY` is used directly by specialist runtimes as the OmniRoute authentication key (ADR-014 Correction 3).
- The install script's `render_runtime_configs()` sets `model.base_url` in each runtime's `config.yaml` to the value of `OMNIROUTE_BASE_URL`.

When OmniRoute is local (future option, not currently deployed):

- The `omniroute.service` unit from ADR-011 § 5.3 original text is rendered and supervised.
- `omniroute` Linux user and `/opt/omniroute/` are created.
- Specialist runtimes use `OMNIROUTE_API_KEY` to authenticate to the local OmniRoute (isolated from `FIREWORKS_API_KEY`).

The install script detects the mode from `OMNIROUTE_BASE_URL`: if the value does not start with `http://127.0.0.1` or `http://localhost`, OmniRoute is treated as remote.

Key invariants (updated from ADR-011):

- All five specialist runtimes' `config.yaml` set the LLM provider base URL to `OMNIROUTE_BASE_URL` (rendered into the config template at install time, not via Hermes env var expansion).
- Specialist runtimes authenticate to OmniRoute using `FIREWORKS_API_KEY` as the `model.api_key` value (ADR-014 Correction 3).
- Crash recovery for the local-OmniRoute case is `Restart=on-failure` with `RestartSec=10s`. For the remote-OmniRoute case, crash recovery is the responsibility of the remote host operator.
- The verify script's connectivity invariant checks `OMNIROUTE_BASE_URL/v1/models` (not `127.0.0.1:20128`).

### 5.4 Web surface service

The Founder-facing read-only web surface (ADR-013) runs as a dedicated systemd unit. It is the eighth unit in the install set (added in v0.2.0):

```
[Unit]
Description=developer-assistant read-only web status surface (dev-assist-cli serve-web)
PartOf=devassist.target
After=network-online.target devassist-orchestrator.service devassist-planner.service devassist-architect.service devassist-executor.service devassist-reviewer.service
Wants=network-online.target
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
User=devassist
Group=devassist
WorkingDirectory=/srv/devassist
Environment=DEVASSIST_OPERATIONAL_DB=/srv/devassist/state/operational.db
Environment=DEVASSIST_REPO=/srv/devassist/repo
Environment=HOME=/srv/devassist
ExecStart=/opt/dev-assist/bin/dev-assist-cli serve-web --port 8180 --bind 127.0.0.1
Restart=on-failure
RestartSec=10s

# Sandboxing — same posture as specialist runtimes
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
PrivateTmp=true
ReadOnlyPaths=/srv/devassist
ReadWritePaths=/srv/devassist/logs
# operational.db is opened read-only by serve-web; no ReadWritePaths needed for /srv/devassist/state.
BindReadOnlyPaths=/srv/devassist/state /srv/devassist/repo /srv/devassist/web

[Install]
WantedBy=devassist.target
```

Key invariants:

- Bound to `127.0.0.1:8180` (ADR-013 § Port Assignment And Network Posture). The web surface never opens any other port. The default install does not add a `ufw` rule for port 8180; the Founder explicitly opens external access if and when desired.
- Read-only at the application layer (no SQLite write paths, no escalation row writes, no LLM calls) and read-only at the systemd layer (`/srv/devassist/state` is bind-mounted read-only for this unit).
- Sequenced **after** the five specialist runtimes so the per-runtime `GET /health` endpoints (`127.0.0.1:8181..8185`) are reachable when the web surface fans out to them at request time.
- Crashes are `Restart=on-failure`. A crashed web surface does not block the runtimes; the Founder still has the `dev-assist-cli` operator path and the daily Telegram digest.
- The unit is part of the same `devassist.target` so `systemctl stop devassist.target` cleanly stops the web surface alongside the runtimes.

### 5.5 journald drop-in

Observability requires journald retention semantics per FR-OBS-09a (`OBSERVABILITY-CONTRACT.md` v0.1.1). The install script writes a single drop-in:

```
# /etc/systemd/journald.conf.d/dev-assist.conf
[Journal]
Storage=persistent
SystemMaxUse=1G
SystemMaxFileSize=128M
MaxRetentionSec=30d
ForwardToSyslog=no
```

Key invariants:

- `Storage=persistent` ensures journald writes to `/var/log/journal/<machine-id>/` and survives reboot.
- `SystemMaxUse=1G` and `MaxRetentionSec=30d` cap disk usage on the small VPS profile.
- `ForwardToSyslog=no` avoids duplicating logs to `/var/log/syslog` (the operator CLI reads journald directly).
- The install script runs `systemctl restart systemd-journald` after writing the drop-in. This is the only journald restart the install script triggers.
- The verify invariant set (§ 8) checks that the drop-in exists and `journalctl --output=json --unit=devassist-* --since="-1 minute"` returns at least one structured line per active unit.

### 5.6 No auto-enable

The install script does NOT run `systemctl enable` for any unit by default — neither for the five specialist runtimes, nor for `omniroute.service`, nor for `devassist-web.service`. Auto-start on reboot is opt-in per `PRD-001.md` § 10 Q13 (default: manual). The Founder enables it later with `systemctl enable devassist.target` (which cascades to all `WantedBy=devassist.target` units) if and when desired.

## 6. Approval Gates

Three gates per `PRD-001.md` § 12.5.

### 6.1 install gate

`scripts/install-self.sh` runs without Founder approval. It:

1. Validates preflight requirements (Ubuntu 22.04, Docker installed, ≥4GB RAM, sufficient disk, `TELEGRAM_ALLOWED_USERS` is set to a non-placeholder numeric value per ADR-014 Correction 7).
2. Creates the `devassist` system user/group if missing, with `--create-home` or with `HOME` set via systemd `Environment=` (ADR-014 Correction 5).
3. Lays down `/srv/devassist/` filesystem layout.
4. Installs Hermes Agent at `/usr/local/lib/hermes-agent/` (idempotent: skips reinstall if already at the pinned version).
5. Lays down per-runtime `HERMES_HOME` directories.
6. **Renders config templates** via `render_runtime_configs()`: substitutes `{{omniroute_base_url}}`, `{{api_key}}`, `{{model_id}}` placeholders with values from environment into `config.yaml` files. Raw `.tmpl` files are NOT copied as-is (ADR-014 Correction 8).
7. Renders systemd unit files.
8. Runs `systemctl daemon-reload`.
9. Runs `scripts/verify-self.sh` (non-zero exit aborts the install).
10. Logs to `/srv/devassist/logs/self-deploy.log`.
11. Prints a final message: "Install complete. Runtimes are NOT started. To start, run: `systemctl start devassist.target`. To verify, run: `scripts/verify-self.sh`."

The install must be safe to re-run on an already-installed VPS without duplicating runtime processes or corrupting the operational state store (`PRD-001.md` § 9 success criterion).

### 6.2 start gate

The install script does not start any runtime. The Founder explicitly approves start by running `systemctl start devassist.target` (or `scripts/install-self.sh --start` after reading the install summary). This is the start gate.

After start:

- The Orchestrator runtime begins polling Telegram.
- Specialist runtimes begin polling the `work_items` table.
- The 30-60 minute progress-report cron is registered.

### 6.3 upgrade gate

`scripts/upgrade-self.sh` runs the upgrade flow:

1. Records the current release id (target of `/srv/devassist/releases/current`).
2. Takes a state-store backup (`sqlite3 .backup ...` to `/srv/devassist/state/backups/operational-<timestamp>.db`).
3. Tarballs the current `runtimes/*/.hermes/{memories,sessions}` and shared-skills, shared-plugins, model catalog, and escalation policy artifacts to `/srv/devassist/state/backups/runtime-state-<timestamp>.tar.gz`.
4. Fetches the new release into `/srv/devassist/releases/<new-release-id>/`.
5. Runs `scripts/install-self.sh` against the new release (idempotent; updates Hermes if needed; renders new unit files).
6. Runs `scripts/verify-self.sh` against the new release.
7. **Stops here** with a Founder approval prompt: "Upgrade staged at release <new-release-id>. State-store backup: <path>. Verify passed/failed: <result>. To activate, run: `scripts/upgrade-self.sh --activate`. To abort and rollback, run: `scripts/rollback-self.sh`."
8. On `--activate`: stops `devassist.target`, flips `releases/current` symlink, starts `devassist.target`, runs verify again.

The upgrade gate is therefore: explicit Founder approval (the `--activate` invocation is the approval) AND a state-store backup taken before activation (step 2 above).

## 7. State Preservation Across Rollback And Upgrade

Self-deployment rollback and upgrade must preserve per-runtime state and shared state per `PRD-001.md` § 12.4 and § 13.2.

Per-runtime state preserved:

- `runtimes/<role>/.hermes/memories/MEMORY.md`
- `runtimes/<role>/.hermes/memories/USER.md`
- `runtimes/<role>/.hermes/sessions/` (full transcript history)
- `runtimes/<role>/.hermes/cron/` (scheduled progress-report jobs)

Shared state preserved:

- `/srv/devassist/state/operational.db` (the shared operational store, including `work_items`, `escalations`, project registry, scheduled progress timers, in-flight Hermes run metadata, errors, llm_calls, llm_calls_daily — see `OPERATIONAL-STATE-STORE.md` v0.2.1+)
- `/srv/devassist/shared-skills/` and `/srv/devassist/shared-plugins/` (the version pinned by the previous release id)
- `MODEL-CATALOG.md` and `ESCALATION-POLICY.md` (read from the new release; if a Founder-edited override file exists at `/srv/devassist/state/founder-overrides/`, it is preserved).

NOT preserved across rollback (because they belong to the failed release):

- `runtimes/<role>/.hermes/logs/` from the failed release window (rotated to `/srv/devassist/logs/post-rollback/<timestamp>/`).
- The new release's `releases/<new-release-id>/` directory is left in place for forensic inspection but not activated.

## 8. Health Verification Invariants

`scripts/verify-self.sh` checks **connectivity-only** invariants per the `PRD-001.md` § 10 Q12 recommendation. It does NOT exercise behavior.

| Invariant | Check | Failure mode |
| --- | --- | --- |
| Telegram reachable | HTTPS GET to `https://api.telegram.org/bot<TOKEN>/getMe` returns `200 OK` | Non-zero exit, log: "Telegram getMe failed" |
| GitHub PAT valid | HTTPS GET to `https://api.github.com/user` with `Authorization: token <PAT>` returns `200 OK` | Non-zero exit, log: "GitHub PAT invalid" |
| OmniRoute reachable | `curl -fs ${OMNIROUTE_BASE_URL}/models` returns `200 OK` and lists catalog model identifiers (remote or local per `OMNIROUTE_BASE_URL` value) | Non-zero exit, log: "OmniRoute model list mismatch" |
| OmniRoute model probe | TKT-026's `dev-assist-cli probe-omniroute` issues a 1-token completion against `${OMNIROUTE_BASE_URL}/chat/completions` for each catalog identifier; failure raises `paid:third_party_external_service_not_yet_supported` (ESCALATION-POLICY § 4.6) | Non-zero exit, log: "OmniRoute probe failed for <identifier>" |
| State store writable | `sqlite3 /srv/devassist/state/operational.db 'PRAGMA quick_check;'` returns `ok` | Non-zero exit, log: "operational.db check failed" |
| Schema version | Apply migrations idempotently; final schema version equals expected | Non-zero exit, log: "schema version mismatch" |
| Each runtime unit active | `systemctl is-active devassist-<role>.service` returns `active` for all five | Non-zero exit, log: "<role> unit inactive" |
| OmniRoute unit active | `systemctl is-active omniroute.service` returns `active` — **only checked when `OMNIROUTE_BASE_URL` points to localhost** (remote OmniRoute has no local unit) | Non-zero exit, log: "omniroute unit inactive" (skipped for remote OmniRoute) |
| Web unit active | `systemctl is-active devassist-web.service` returns `active` AND `curl -fs http://127.0.0.1:8180/health` returns `200 OK` with body `{"role":"web","ok":true}` | Non-zero exit, log: "devassist-web unit inactive" or "web /health probe failed" |
| Per-runtime health endpoints | `curl -fs http://127.0.0.1:8181/health` ... `http://127.0.0.1:8185/health` each returns `200 OK` with `{"role":"<role>","ok":true}` (`OBSERVABILITY-CONTRACT.md` v0.1.1 § 11) | Non-zero exit, log: "<role> /health probe failed" |
| journald retention configured | `/etc/systemd/journald.conf.d/dev-assist.conf` exists with `SystemMaxUse=1G` and `MaxRetentionSec=30d` (FR-OBS-09a, c) | Non-zero exit, log: "journald drop-in missing or misconfigured" |
| No secrets in journal | `journalctl -u devassist-* -u omniroute -u devassist-web` since last verify run scanned for known secret env-var values | Non-zero exit, log: "possible secret leak in journal" (only the env-var name is logged, never the value) |

The verify script must produce a human-readable summary at the end:

```
verify-self: PASS  (12/12 invariants)
```

or

```
verify-self: FAIL  (10/12 invariants)
  - Telegram reachable: FAIL
  - devassist-web unit inactive: FAIL
  See /srv/devassist/logs/self-deploy.log for details.
```

The verify script must NOT print secret values in any failure path. Failure messages reference env-var names only.

## 9. Rollback Behavior

`scripts/rollback-self.sh`:

1. Stops `devassist.target` (graceful: SIGTERM with 30-second deadline, then SIGKILL).
2. Identifies the most recent state-store backup under `/srv/devassist/state/backups/` (file pattern `operational-<timestamp>.db`). Aborts with non-zero exit if no backup exists.
3. Restores `operational.db` from that backup (atomic: copies to `operational.db.new`, fsyncs, renames).
4. Identifies the corresponding runtime-state backup tarball; restores `memories/`, `sessions/`, `cron/` per runtime.
5. Flips `releases/current` symlink back to the target of `releases/previous`.
6. Runs `systemctl daemon-reload`.
7. Runs `scripts/verify-self.sh` against the restored release.
8. Starts `devassist.target` if and only if verify passes.
9. Logs every step with timestamps to `/srv/devassist/logs/self-deploy.log`.

If verify fails after rollback, the script does NOT auto-retry. It stops with non-zero exit and a clear human-readable instruction telling the Founder which invariants failed and what to inspect.

Rollback is itself idempotent: running it twice in a row restores the same backup; it never destroys the backup it just restored from.

## 10. Secrets Handling

A single file holds all self-deployment secret values:

```
/srv/devassist/secrets/SELF-DEPLOY.env
mode 0600, owner devassist:devassist
```

Required env vars (the file must define all of these; missing values fail verify):

| Env var | Source | Used by |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | @BotFather | Orchestrator runtime only (§ 10.1) |
| `TELEGRAM_ALLOWED_USERS` | Founder | Orchestrator runtime only — **must be a comma-separated list of numeric Telegram user IDs** (e.g., `7977379217`). Placeholder values (e.g., `YOUR_USER_ID`) cause the bot to reject all messages. ADR-014 Correction 7. |
| `GITHUB_TOKEN` | Founder PAT or GitHub App token | Executor runtime |
| `FIREWORKS_API_KEY` | Fireworks.ai | All runtimes — used as OmniRoute auth key (`model.api_key` in Hermes config) when OmniRoute is remote. Also used by OmniRoute as upstream credential when OmniRoute is local. Replaces the prior `OMNIROUTE_API_KEY` assumption. ADR-014 Correction 3. |
| `OMNIROUTE_BASE_URL` | Founder / ops | All runtimes — the full base URL for OmniRoute (e.g., `https://omniroute.infinitycore.space:8443/v1`). Defaults to `http://127.0.0.1:20128` for local OmniRoute. ADR-014 Correction 1. |
| `OPENROUTER_API_KEY` | OpenRouter (backup) | All runtimes; fallback chain |
| `HERMES_DEVASSIST_REPO_URL` | Founder | All runtimes (clone target for the project repo) |
| `HERMES_DEVASSIST_REPO_BRANCH` | Founder, default `main` | All runtimes |
| `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` | Founder | Orchestrator runtime only (escalation surface) |

### 10.1 Secret-Segregation Pattern (defense in depth)

All five units load the same `EnvironmentFile=/srv/devassist/secrets/SELF-DEPLOY.env` because it is operationally simpler than rendering five different env files. The secret-segregation guarantee comes from **config-level skill loadout, not env-level segregation**:

- `TELEGRAM_BOT_TOKEN` is technically present in every runtime's environment, but only the Orchestrator's `config.yaml` enables `gateway.enabled: true` and loads the `telegram-gateway` skill (`MULTI-HERMES-CONTRACT.md` § 4, § 5.1). A specialist runtime cannot reach the Telegram API because no skill in its loadout knows how to use the token.
- `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` is similarly available everywhere but consumed only by the Orchestrator's escalation-surface skill.
- `GITHUB_TOKEN` is consumed only by the Executor runtime's `dev-assist-github-workflow` skill; no other runtime loads that skill.

This is **not** equivalent to env-level segregation: a compromised specialist runtime that could call arbitrary Python or arbitrary HTTP could still read its own environment and reach Telegram or GitHub. Defense-in-depth is provided by:

- The `HERMES-SKILL-ALLOWLIST.md` deny-by-default policy: every runtime's `config.yaml` lists exactly the skills in `MULTI-HERMES-CONTRACT.md` § 5; new tool calls outside that loadout fail at Hermes' approval-policy hook.
- The `dev-assist-escalation-policy` plugin's deterministic rule blocking arbitrary outbound HTTP from non-Orchestrator runtimes (`ESCALATION-POLICY.md` § 4).
- The systemd unit's `BindReadOnlyPaths=` and `ReadOnlyPaths=` (§ 5.2) preventing cross-runtime config tampering at the filesystem layer.

TKT-021 includes a startup config-level check that, for non-Orchestrator runtimes, asserts the `telegram-gateway` skill is **not** in the loaded set; mismatch is a fatal-startup error.

Forbidden patterns:

- Secrets MUST NOT appear in any committed repository file.
- Secrets MUST NOT appear in `journalctl` output. Hermes logs are scrubbed for known secret env-var values; if a leak is detected, the verify invariant fails.
- Secrets MUST NOT appear in PR artifacts, review artifacts, or progress reports.
- Secrets MUST NOT appear in `~/.bash_history` or any shell history accessible to non-`devassist` users.

## 11. Failure Modes And Recovery

| Failure | Detection | Recovery |
| --- | --- | --- |
| Hermes install fails mid-way | `install-self.sh` non-zero exit | Re-run install (idempotent); if the partial install is unrecoverable, run `rollback-self.sh` |
| One runtime unit fails to start | `verify-self.sh` invariant fails | Inspect `journalctl -u devassist-<role>.service`; fix root cause; `systemctl restart devassist-<role>.service` |
| State store corruption | `verify-self.sh` schema/quick_check fails | Run `rollback-self.sh` to restore last good `operational.db` |
| Secret missing or rotated | Verify connectivity invariant fails for Telegram/GitHub/OmniRoute | Update `/srv/devassist/secrets/SELF-DEPLOY.env`; restart affected unit; re-run verify |
| Upgrade verify fails after staging | `upgrade-self.sh` step 6 returns non-zero | Script stops at activation gate; Founder runs `rollback-self.sh` to restore the previous release |
| Founder rejects upgrade activation | Founder does not run `--activate` | The new release stays staged; `releases/current` still points at the previous release; Founder may inspect `/srv/devassist/releases/<new-release-id>/` and `state-<timestamp>.db` backup at leisure |
| Disk full | Install/upgrade fails on `cp` or `tar` | Free space; retry. State backups are rotated by the script keeping the last 7 backups by default |
| Docker unavailable | Executor or Reviewer unit fails | Verify Docker daemon; restart `docker.service`; restart affected runtime unit |

## 12. Validation Of This Contract

Before merging this contract, the Architect confirmed:

- The contract aligns with `PRD-001.md` § 12 (self-deployment) and § 12.5 (three approval gates).
- The contract aligns with `PRD-001.md` § 13.2 (multi-Hermes preserved across rollback/upgrade).
- The contract does not introduce a paid third-party service as a hard runtime dependency (no Modal, Daytona, Vercel sandbox, hosted Postgres, hosted vector store, hosted Letta).
- The contract uses only standard Ubuntu 22.04 LTS tooling (`bash`, `systemctl`, `journalctl`, `sqlite3`, `tar`, `curl`, `git`) plus the already-required Hermes Agent, Docker, Python 3.11, and Node.js 22.
- The verify invariant set is connectivity-only per `PRD-001.md` § 10 Q12 recommendation.

Implementation is split into TKT-020 (bootstrap, systemd, install/verify/rollback) and TKT-022 (state-store schema additions referenced by verify and upgrade). Implementation tickets enforce that scripts are tested for idempotency and rollback paths before merge.

## 13. Cross-References

- `PRD-001.md` v0.2.1 § 12, § 12.5, § 13 (product mandate)
- `ARCH-001.md` v0.3.0 § 14 (architectural shape), § 23 (observability summary), § 24 (web interface architecture)
- `MULTI-HERMES-CONTRACT.md` (per-runtime layout)
- `OPERATIONAL-STATE-STORE.md` v0.3.0 (operational.db schema including `work_items`, `escalations`, `errors`, `llm_calls`, `llm_calls_daily`)
- `OBSERVABILITY-CONTRACT.md` v0.1.1 § 11 (per-runtime health endpoints; ports 8181..8185), § 14 (ObservabilityManager), FR-OBS-09a/b/c (journald + SQLite retention)
- `MODEL-CATALOG.md` v0.2.0 § 4.1 (catalog identifiers probed at install) and § 4.2 (FIREWORKS_API_KEY in OmniRoute state DB only)
- `ESCALATION-POLICY.md` v0.1.1 § 4.5 (`net:public_endpoint_exposure` deterministic rule), § 4.6 (paid third-party gate)
- `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0 (distinct surface)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0 § 3 (Hermes version pin, deployment assumptions)
- `docs/architecture/adr/ADR-004-deployment-mechanism.md` (alternatives considered)
- `docs/architecture/adr/ADR-010-observability-shape.md` (observability shape; `dev-assist-cli` and journald)
- `docs/architecture/adr/ADR-011-routing-layer.md` (OmniRoute as the seventh unit; binding to 127.0.0.1:20128)
- `docs/architecture/adr/ADR-013-web-interface.md` (web surface as the eighth unit; binding to 127.0.0.1:8180)
- `docs/tickets/TKT-020.md` (install/verify/rollback bootstrap), `docs/tickets/TKT-026.md` (model-probe CLI used by the OmniRoute model-probe invariant), `docs/tickets/TKT-027.md` (`dev-assist-cli` and `serve-web` subcommand), `docs/tickets/TKT-031.md` (per-runtime `GET /health` endpoints)
