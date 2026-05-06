---
id: SELF-DEPLOYMENT-CONTRACT
version: 0.1.0
status: draft
---

# Self-Deployment Contract

## 1. Purpose

This document defines the v0.1 contract for **self-deployment** of `developer-assistant` onto a Founder-owned Ubuntu 22.04 LTS VPS. It satisfies `PRD-001.md` § 12 (self-deployment as a v0.1 prerequisite) and § 12.5 (three approval gates: `install`, `start`, `upgrade`). It is distinct from `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md`, which governs deployment of projects the assistant generates for the Founder.

The contract is a boundary specification: it states what the install, verify, rollback, and upgrade entry points must do, what filesystem layout they create, what systemd units they manage, and what Founder-visible behavior they exhibit. It does not include shell-script source code (Executors implement that under TKT-020).

## 2. Scope

In scope for v0.1:

- One-command **install** that lays down the multi-Hermes runtime layout, installs the Hermes Agent foundation once, configures five per-runtime `HERMES_HOME` directories, renders systemd unit templates, runs preflight checks, and stops without starting any runtime.
- One-command **verify** that runs the connectivity-only health invariant set and returns non-zero on failure.
- One-command **rollback** that restores the last `state.db` backup and the last known-good runtime config tarball, then restarts units that were running prior to rollback.
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
│   │       ├── state.db -> /srv/devassist/state/state.db        (symlink)
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
│   ├── state.db                               # the SQLite operational store; mode 0640
│   └── backups/                               # rotating snapshots; mode 0700
│       └── state-YYYYMMDD-HHMMSS.db
├── secrets/
│   └── SELF-DEPLOY.env                        # mode 0600, owner devassist:devassist
├── releases/
│   ├── current -> /srv/devassist/releases/<release-id>/  (symlink)
│   ├── previous -> ...                                    (symlink)
│   └── <release-id>/                          # snapshot of repo + shared-skills + shared-plugins
└── logs/
    └── self-deploy.log                        # install/verify/rollback/upgrade trace
```

Notes:

- Per-runtime `HERMES_HOME` directories share the SQLite operational store via the symlink to `/srv/devassist/state/state.db`. This is the explicit mechanism that lets all five runtimes see the same `work_items` and `escalations` tables (`MULTI-HERMES-CONTRACT.md` § 6).
- The `.env` symlink to `/srv/devassist/secrets/SELF-DEPLOY.env` makes each runtime see the same secret values (Telegram bot token, GitHub PAT, OmniRoute API key, etc.) without duplicating the secrets file.
- Per-runtime `memories/`, `sessions/`, `cron/`, and `logs/` directories are NOT shared. Memory isolation between runtimes is physical per `ARCH-001.md` § 11.1.
- The `releases/current` symlink is the activation surface. Upgrade flips it from the previous release to the new one **only** after the Founder approves.

## 5. systemd Units

Six unit files are written by the install script:

```
/etc/systemd/system/devassist.target
/etc/systemd/system/devassist-orchestrator.service
/etc/systemd/system/devassist-planner.service
/etc/systemd/system/devassist-architect.service
/etc/systemd/system/devassist-executor.service
/etc/systemd/system/devassist-reviewer.service
```

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

[Service]
Type=simple
User=devassist
Group=devassist
WorkingDirectory=/srv/devassist/runtimes/<role>
Environment=HERMES_HOME=/srv/devassist/runtimes/<role>/.hermes
Environment=HERMES_DEVASSIST_ROLE=<role>
EnvironmentFile=/srv/devassist/secrets/SELF-DEPLOY.env
ExecStart=/usr/local/bin/hermes gateway run
Restart=on-failure
RestartSec=10s
StartLimitIntervalSec=300
StartLimitBurst=5

# Sandboxing
NoNewPrivileges=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/srv/devassist/runtimes/<role> /srv/devassist/state /srv/devassist/logs
PrivateTmp=true

[Install]
WantedBy=devassist.target
```

Per-runtime overrides applied by the install script:

- Orchestrator: `ExecStart` runs the gateway in Telegram polling mode; the runtime is the only one that loads the `telegram-gateway` skill.
- Executor and Reviewer: `Supplementary` group `docker` is added so the Hermes terminal Docker backend can talk to the local Docker socket.
- Reviewer: read-only mount of the project repo into the Docker terminal sandbox (`HERMES-SKILL-ALLOWLIST.md` § 4.6).

The install script does NOT run `systemctl enable` for any unit by default. Auto-start on reboot is opt-in per `PRD-001.md` § 10 Q13 (default: manual). The Founder enables it later with `systemctl enable devassist.target` if and when desired.

## 6. Approval Gates

Three gates per `PRD-001.md` § 12.5.

### 6.1 install gate

`scripts/install-self.sh` runs without Founder approval. It:

1. Validates preflight requirements (Ubuntu 22.04, Docker installed, ≥4GB RAM, sufficient disk).
2. Creates the `devassist` system user/group if missing.
3. Lays down `/srv/devassist/` filesystem layout.
4. Installs Hermes Agent at `/usr/local/lib/hermes-agent/` (idempotent: skips reinstall if already at the pinned version).
5. Lays down per-runtime `HERMES_HOME` directories.
6. Renders systemd unit files.
7. Runs `systemctl daemon-reload`.
8. Runs `scripts/verify-self.sh` (non-zero exit aborts the install).
9. Logs to `/srv/devassist/logs/self-deploy.log`.
10. Prints a final message: "Install complete. Runtimes are NOT started. To start, run: `systemctl start devassist.target`. To verify, run: `scripts/verify-self.sh`."

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
2. Takes a state-store backup (`sqlite3 .backup ...` to `/srv/devassist/state/backups/state-<timestamp>.db`).
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

- `/srv/devassist/state/state.db` (operational store, including `work_items`, `escalations`, project registry, scheduled progress timers, in-flight Hermes run metadata)
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
| OmniRoute reachable | HTTPS GET to OmniRoute health endpoint returns `200 OK` | Non-zero exit, log: "OmniRoute unreachable" |
| State store writable | `sqlite3 /srv/devassist/state/state.db 'PRAGMA quick_check;'` returns `ok` | Non-zero exit, log: "state.db check failed" |
| Schema version | Apply migrations idempotently; final schema version equals expected | Non-zero exit, log: "schema version mismatch" |
| Each unit active | `systemctl is-active devassist-<role>.service` returns `active` for all five | Non-zero exit, log: "<role> unit inactive" |
| No secrets in journal | `journalctl -u devassist-*` since last verify run scanned for known secret env-var values | Non-zero exit, log: "possible secret leak in journal" (only the env-var name is logged, never the value) |

The verify script must produce a human-readable summary at the end:

```
verify-self: PASS  (7/7 invariants)
```

or

```
verify-self: FAIL  (5/7 invariants)
  - Telegram reachable: FAIL
  - reviewer unit inactive: FAIL
  See /srv/devassist/logs/self-deploy.log for details.
```

The verify script must NOT print secret values in any failure path. Failure messages reference env-var names only.

## 9. Rollback Behavior

`scripts/rollback-self.sh`:

1. Stops `devassist.target` (graceful: SIGTERM with 30-second deadline, then SIGKILL).
2. Identifies the most recent state-store backup under `/srv/devassist/state/backups/`. Aborts with non-zero exit if no backup exists.
3. Restores `state.db` from that backup (atomic: copies to `state.db.new`, fsyncs, renames).
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
| `TELEGRAM_BOT_TOKEN` | @BotFather | Orchestrator runtime |
| `TELEGRAM_ALLOWED_USERS` | Founder | Orchestrator runtime |
| `GITHUB_TOKEN` | Founder PAT or GitHub App token | Executor runtime |
| `OMNIROUTE_API_KEY` | OmniRoute | All runtimes |
| `OPENROUTER_API_KEY` | OpenRouter (backup) | All runtimes; fallback chain |
| `HERMES_DEVASSIST_REPO_URL` | Founder | All runtimes (clone target for the project repo) |
| `HERMES_DEVASSIST_REPO_BRANCH` | Founder, default `main` | All runtimes |
| `DEVASSIST_FOUNDER_TELEGRAM_USER_ID` | Founder | Orchestrator runtime (escalation surface) |

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
| State store corruption | `verify-self.sh` schema/quick_check fails | Run `rollback-self.sh` to restore last good `state.db` |
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
- `ARCH-001.md` v0.3.0 § 14 (architectural shape)
- `MULTI-HERMES-CONTRACT.md` (per-runtime layout)
- `OPERATIONAL-STATE-STORE.md` v0.2.0 (state.db schema baseline)
- `GENERATED-PROJECT-DEPLOYMENT-CONTRACT.md` v0.1.0 (distinct surface)
- `HERMES-SKILL-ALLOWLIST.md` v0.1.0 § 3 (Hermes version pin, deployment assumptions)
- `docs/architecture/adr/ADR-004-deployment-mechanism.md` (alternatives considered)
- `docs/tickets/TKT-020.md` (implementation)
