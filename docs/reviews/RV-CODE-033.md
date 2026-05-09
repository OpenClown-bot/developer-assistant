---
id: RV-CODE-033
version: 0.1.0
status: complete
ticket: TKT-034 v0.2.0
branch: rv/rv-code-033
reviewer_model: Kimi K2.6 / Qwen 3.6 Plus rubric, Devin substitution
date: 2026-05-09
---

# RV-CODE-033: Review of PR #135 (TKT-034 — Interactive installer and operator hygiene)

## Verdict: fail

PR #135 is not ready to ratify as a completed TKT-034 iter-1 implementation. The PR is correctly scoped to the six allowed files and the interactive prompt path is substantially implemented, but two acceptance-criteria-bearing paths do not match the ticket/architecture contract: shared skills are not actually populated when the `shared-skills/` source tree is absent, and `verify-self.sh` does not re-check the full VPS prereq baseline promised by AC-8/AC-10. These are functional review blockers, not documentation nits.

---

## Findings

| # | Severity | Category | Finding | Status |
|---|----------|----------|---------|--------|
| 1 | High | AC-2 / Architecture | `render_shared_skills_manifest()` records `absent_at_install_time` when `${repo_root}/shared-skills/<skill>/SKILL.md` is missing, and `check_shared_skills_manifest_match()` treats that sentinel as pass. This satisfies manifest shape tests but does not populate `/srv/devassist/shared-skills/` with reviewed custom skill content required by TKT-034 A.iv and MULTI-HERMES § 5.0. Evidence: `scripts/install-self.sh:1292-1305`, `scripts/verify-self.sh:471-479`, `MULTI-HERMES-CONTRACT.md:90-110`. | Blocker |
| 2 | High | AC-8 / AC-10 | `verify-self.sh`'s `check_prereq_baseline()` only checks CLI presence plus Python version in real mode. It omits OS Ubuntu 22.04, sudo/root posture, api.github.com network reachability, `/srv` disk threshold, Docker daemon/socket/group checks, and gh version; the install script has the fuller `verify_prereqs()` but the verify invariant does not. Evidence: `scripts/install-self.sh:1090-1190` vs `scripts/verify-self.sh:582-610`; TKT-034 AC-8/AC-10 requires the verify invariant baseline. | Blocker |
| 3 | Medium | AC-8 security hygiene | `check_gh_cli_authenticated()` redirects `gh auth status` stderr to `/dev/null`, so it cannot enforce AC-8(2)'s failure condition when stderr contains `embedded credential`. Evidence: `scripts/verify-self.sh:369-385`, TKT-034 AC-8(2). | Needs change |
| 4 | Low | Spec drift | TKT-034 says 14 custom skills in prose, while MULTI-HERMES § 5.0 enumerates 15. Executor chose 15, matching the authoritative table. | Accepted / note |
| 5 | Low | Spec drift | TKT-034 says 13→21 verify invariants in AC-8(h), while the actual baseline is 11→19. The executor's Q-TKT-034-01 is valid and non-blocking once the eight named invariants are implemented correctly. | Accepted / note |

---

## Scope Compliance Assessment

**Within allowed TKT-034 § 5 files:**
- `scripts/install-self.sh`
- `scripts/verify-self.sh`
- `tests/test_self_deployment_scripts.py`
- `tests/test_install_interactive_prompts.py`
- `tests/fixtures/self-deploy.env.fixture`
- `docs/tickets/TKT-034-interactive-installer-and-operator-hygiene.md`

`git diff --name-only 8bc5288..61a51abc` shows exactly those six paths. No systemd templates, architecture docs, prompts, source runtime code, or infrastructure files were modified. Scope compliance passes.

---

## Architecture Compliance Assessment

| Requirement | Assessment |
|---|---|
| MULTI-HERMES § 5.0 shared skills | Partial/fail. The implementation lists the 15 table entries, but it does not require or install actual `SKILL.md` content when the `shared-skills/` tree is absent; it records a passing sentinel instead. |
| SELF-DEPLOYMENT-CONTRACT § 6.1 install gate | Partial. Interactive and non-interactive install flows are present, no runtime auto-start was observed in dry-run tests, and env rendering remains in the install path. Shared-skills materialization remains incomplete. |
| SELF-DEPLOYMENT-CONTRACT § 8 verify gate | Partial/fail. The verify script reports 19 invariants, but one of the new invariants is materially weaker than the ticket's prereq-baseline contract. |
| SELF-DEPLOYMENT-CONTRACT § 10 secrets | Pass. Real install path writes `/srv/devassist/secrets/SELF-DEPLOY.env` as `0400 devassist:devassist`, dir `0710 root:devassist`; fixture mode relaxes file mode only for tests. |
| ADR-014 Correction 1 | Pass. Interactive default for `OMNIROUTE_BASE_URL` is the remote endpoint; local default remains only as legacy/fallback variable default. |
| ADR-014 Correction 3 | Pass. Prompting uses `FIREWORKS_API_KEY` as the OmniRoute auth key and mirrors it to `OMNIROUTE_API_KEY` for compatibility. |
| ADR-014 Correction 5 | Pass. Installer creates/configures `/home/devassist` and writes gh/git state under that home. |
| ADR-014 Correction 7 | Pass. `TELEGRAM_ALLOWED_USERS` validation enforces comma-separated numeric Telegram IDs. |

---

## Acceptance Criteria Assessment

| AC | Status | Evidence / rationale |
|---|---|---|
| AC-1 diagnosis | Pass | §10 execution log re-verifies the seven branch-cut observations at `docs/tickets/TKT-034-...md:393-403`. |
| AC-2 operator hygiene | Fail | A.i/A.ii/A.iii are implemented, but A.iv does not populate actual shared-skill content when source skills are missing (`scripts/install-self.sh:1292-1305`). |
| AC-3 one-command bootstrap | Pass | Usage/flags are documented and parsed (`scripts/install-self.sh:565-624`); dry-run install tests pass. |
| AC-4 interactive prompts | Pass | 11 prompt functions, secret `read -rs`, retry/default behavior, and env-var-only abort tests are covered by 31 PTY/unit tests. |
| AC-5 TTY detection | Pass | `detect_install_mode()` implements CLI flag > env > TTY > non-interactive, covered by `TestDetectInstallMode`. |
| AC-6 credential storage | Pass | Real path chmod/chown in `render_self_deploy_env()` (`scripts/install-self.sh:368-375`) plus verify ACL check (`scripts/verify-self.sh:498-544`). |
| AC-7 re-run idempotency | Pass | Prompt-phase skip checks all required env vars (`scripts/install-self.sh:990-1007`); second-run dry-run tests pass. |
| AC-8 verify-self extensions | Fail | Eight functions exist and are called (`scripts/verify-self.sh:627-635`), but `check_prereq_baseline()` is incomplete and `check_gh_cli_authenticated()` ignores the stderr condition. |
| AC-9 cleanup detection | Pass | Prior deploy detection and `--force-reinstall` skip are implemented (`scripts/install-self.sh:1064-1085`) and tested. |
| AC-10 VPS prereq verification | Partial | Install-time `verify_prereqs()` implements the eight ordered checks (`scripts/install-self.sh:1090-1190`), but verify-time baseline does not. |
| AC-11 test strategy | Pass with gap | Added tests are offline-only; however, tests do not catch the shared-skills absent sentinel or full verify-prereq omissions. |
| AC-12 security | Pass with one medium gap | No real token patterns found; fixture is placeholder-only; secret prompts disable echo. gh-auth stderr embedded-credential detection remains missing. |
| AC-13 docs/PR template | Pass | `python3 scripts/validate_docs.py` passes locally and CI validate-docs passed on PR #135. |

---

## Security Assessment (AC-12)

| Control | Status | Evidence |
|---|---|---|
| No secret echo from prompts | Pass | `prompt_secret()` uses silent read and tests assert no echo. |
| Abort messages name env var only | Pass | `abort_install()` and `TestAbortMessages` cover rejected-value redaction. |
| gh auth token via stdin | Pass | `gh auth login --with-token` uses here-string/stdin; no token-bearing URL pattern found (`scripts/install-self.sh:1238-1244`). |
| Origin URL token-free | Pass | Verify rejects `https://*@*` origin URLs (`scripts/verify-self.sh:416-445`). |
| Fixture cleanliness | Pass | `tests/fixtures/self-deploy.env.fixture` contains placeholder/test/example values only. |
| Secret file ACL | Pass | Real mode enforces `0400 devassist:devassist`; secrets dir `0710 root:devassist`. |
| Token-shape scan | Pass | Local scan found no `ghp_`, `github_pat_`, Telegram bot token, or `sk-*` literal secret in implementation files, except the safe comment mention of `--token`. |

---

## Q-TKT Assessment

- **Q-TKT-034-01** (`13 → 21` vs `11 → 19` invariants): valid informational clerical issue. It should not block ratification by itself, but does not excuse the incomplete `check_prereq_baseline()` implementation.
- **Q-TKT-034-02** (13 pre-existing full-suite failures on branch cut): valid informational issue. My targeted TKT-034 suite passes locally after installing missing local tools; the broader frozen-surface failures are outside this ticket's write zone.

---

## Validation Evidence

- `python3 scripts/validate_docs.py` → pass.
- `python3 -m unittest tests.test_self_deployment_scripts tests.test_install_interactive_prompts` → 91 tests OK.
- `shellcheck scripts/install-self.sh scripts/verify-self.sh` → 13 current findings; baseline `8bc5288` has 15 findings, so no net-new shellcheck finding from PR #135. Shellcheck still exits 1 due warnings/info/style findings.
- PR #135 CI: `validate-docs` and PR-Agent checks both passed.

---

## Merge / Ratification Recommendation

Do not ratify PR #135 as satisfying TKT-034 iter-1 yet. Dispatch an iter-2 Executor fix that either adds the real `shared-skills/<skill>/SKILL.md` source tree and makes absent skills fail, or formally amends the architecture/ticket to use the existing `src/developer_assistant/hermes_skills/` package as the source of truth; then strengthen `verify-self.sh check_prereq_baseline()` to match the eight AC-10 prereqs and add tests for those real-mode branches.
