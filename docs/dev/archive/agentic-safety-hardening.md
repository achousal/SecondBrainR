---
status: archived
---

# Agentic Safety Hardening

Development considerations for strengthening EngramR against the failure modes documented in "Agents of Chaos" (Shapira et al., 2026; arXiv:2602.20021v1). That paper red-teamed autonomous LLM agents deployed with persistent memory, shell access, email, and multi-party communication. This document maps their findings to our architecture and identifies what is applicable, what we already mitigate, and what needs work.

---

## Context

The paper's core finding: **the dominant attack surface for agentic systems is social, not technical.** Ordinary language, identity ambiguity, emotional manipulation, and contextual framing produce serious failures when agents have real tools and persistent state. No gradient attacks, no poisoned training data -- just conversation.

Three structural deficits they identify in current agent architectures:

1. **No stakeholder model** -- agents cannot reliably distinguish who they serve from who they interact with.
2. **No self-model** -- agents take high-autonomy actions with low self-awareness of competence boundaries.
3. **No private deliberation surface** -- agents leak sensitive information through artifacts, cross-channel posts, and tool outputs even when chain-of-thought is hidden.

---

## Threat Mapping to EngramR

### What we share with their setup

| Property | Their agents | EngramR | Risk level |
|---|---|---|---|
| Persistent memory | Markdown workspace files, daily logs | Vault files (self/, ops/, notes/), session logs | Same |
| Self-modifiable config | Agent edits its own SOUL.md, MEMORY.md | Agent edits self/identity.md, self/goals.md, ops/ | Same |
| Shell access | Unrestricted sudo | Bash tool (sandboxed by Claude Code) | Lower |
| File system writes | Unrestricted | Gated by validate_write.py hook + schema validation | Lower |
| Multi-party communication | Discord + email + Moltbook | Slack bot + federation sync | Comparable |
| Autonomous operation | Heartbeats + cron jobs | Daemon (daemon.sh + daemon_scheduler.py) | Comparable |
| Tool access | Unrestricted tools | Skill-scoped allowed-tools lists | Lower |

### What we already mitigate

| Paper failure | EngramR mitigation | Status |
|---|---|---|
| Disproportionate response (Case 1) | Skill-level tool restrictions; validate_write.py blocks destructive writes to notes/ | Partial |
| Unrestricted file modification | Boundary layer (schema_validator.py) + pipeline compliance + hook blocking | Strong |
| No input validation on writes | YAML safety pre-parse, title sanitization, Unicode NFC normalization | Strong |
| PII leakage in data outputs (Case 3) | pii_filter.py auto-redaction in /eda pipeline; `redact_text()`/`scrub_outbound()` on federation exports and Slack responses (Gap Fix 1-3, 2026-03-01) | **Strong** |
| Runaway daemon loops (Cases 4-5) | Metabolic governor: QPR/CMR thresholds suppress generative tasks | Strong |
| Uncontrolled resource consumption | Daemon cooldown intervals, consecutive-skip idle fallback | Moderate |
| Identity confusion in shared channels | Single-operator design; no multi-user Discord server | Low risk currently |

### What we have mitigated (P0-P5 sprint, 2026-02-28)

Previously listed under "What we do NOT yet mitigate." All items addressed during the P0-P5 implementation sprint.

| Paper failure | Mitigation | Status |
|---|---|---|
| Self-modifiable identity (Case 10) | Integrity manifest + validate_write.py identity protection (P0) | **Mitigated** |
| Indirect prompt injection via external docs (Case 10) | Federation imports quarantined, HTML stripped, NFC normalized; quarantine enforced in export filter, skills, and decision engine signal (P1) | **Mitigated** |
| Disproportionate concessions under social pressure (Case 7) | Explicit escalation ceilings in CLAUDE.md; per-invocation confirmation for system-affecting actions; mechanical enforcement via validate_write.py (P4) | **Mitigated** |
| Cross-session memory as attack surface (Cases 1, 10) | ops/config.yaml and ops/methodology/_compiled.md now covered by integrity manifest (P0); ops/reminders.md and ops/sessions/ remain unprotected (low risk, frequently modified) | **Partial** |
| Federated claim propagation (Case 9-10 analog) | Federation imports routed through builders, quarantine enforced, HTML stripped, audit logged (P1) | **Mitigated** |
| Slack bot authority confusion | User ID-based authorization with owner/allowed/public levels, per-user rate limiting (P2) | **Mitigated** |
| Daemon autonomous override | UNATTENDED_OVERRIDE disables user-approval tools; structured audit trail with decision ceiling and skill backoff (P3) | **Mitigated** |

---

## Development Priorities

### P0: Integrity of self-modifiable files -- COMPLETE

**Problem:** The paper's Case 10 ("Agent Corruption") showed that an externally editable document linked from agent memory became a persistent indirect prompt injection vector. Our self/ directory is the equivalent -- it shapes every session via session_orient.py auto-loading. If an agent session corrupts self/identity.md or self/methodology.md (through social pressure, prompt injection in ingested content, or a bug in a skill), every subsequent session inherits the corruption.

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| Core module | `_code/src/engram_r/integrity.py` | `PROTECTED_PATHS` constant (6 files), `compute_hash()` (SHA-256), `seal_manifest()`, `verify_manifest()`, CLI (`seal`/`verify`/`status`) |
| Detection layer | `_code/scripts/hooks/session_orient.py` | `_check_integrity()` runs before `[Session Orient]`; prepends `### Integrity` section with `INTEGRITY WARNING:` on drift |
| Prevention layer | `_code/scripts/hooks/validate_write.py` | Blocks writes to protected files; override with `ENGRAMR_IDENTITY_UNLOCK=1` env var or `identity_protection: false` in config |
| Config toggle | `ops/config.yaml` | `identity_protection: true` (default) |
| Manifest file | `ops/integrity-manifest.yaml` | Generated by `seal`; stores SHA-256 hashes and timestamp |
| Tests | `_code/tests/test_integrity.py` | 14 tests (hash, seal, verify, CLI) |
| Tests | `_code/tests/test_session_orient.py` | 4 integrity tests added |
| Tests | `_code/tests/test_validate_write.py` | 4 protected-path tests added |

**Protected files:** `self/identity.md`, `self/methodology.md`, `ops/config.yaml`, `ops/daemon-config.yaml`, `ops/methodology/_compiled.md`, `CLAUDE.md`

**Design decisions:**
- Hardcoded protected set (not config-driven) -- config is itself protected; prevents agent from removing a file from the set.
- Env var override (`ENGRAMR_IDENTITY_UNLOCK=1`) -- session-scoped, requires deliberate human action; breaks the circular dependency of config protecting itself.
- `seal` is manual -- the manifest is a human-endorsed snapshot, not auto-generated.
- `self/goals.md` and `ops/reminders.md` are NOT protected -- frequently modified during normal operation.
- No manifest = no check -- new vaults skip integrity checks silently until first `seal`.

**Activation:** `cd _code && uv run python -m engram_r.integrity seal --vault ..`

### P1: Federation trust boundary hardening -- COMPLETE

**Problem:** The paper's multi-agent findings (Cases 9-10) show that knowledge transfer between agents propagates vulnerabilities alongside capabilities. Our federation layer (claim_exchange.py, hypothesis_exchange.py) is the equivalent channel. The boundary maturation plan already identified that claim_exchange.py bypasses build_claim_note (Tier-1 issue). Beyond that, imported content could contain:
- Malicious markdown (script injection if rendered by Obsidian plugins)
- Subtly misleading claims that poison the knowledge graph
- Wiki-link references that resolve to local files (path traversal via link resolution)

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| HTML stripping | `schema_validator.py` | `strip_html()` via stdlib `html.parser`; strips all tags, unescapes entities, short-circuits when no `<` |
| Claim-family schemas | `schema_validator.py` | `claim`, `evidence`, `methodology`, `contradiction`, `pattern`, `question` types require `description` field |
| Hypothesis builder | `note_builder.py` | `build_foreign_hypothesis_note()` applies `sanitize_title`, `normalize_text`, `strip_html` on all fields |
| Import refactoring | `hypothesis_exchange.py` | `import_hypotheses()` delegates to builder; adds `quarantine` parameter |
| Export quarantine filter | `claim_exchange.py` | `filter_quarantined` parameter skips quarantined notes on export |
| Audit logging | `claim_exchange.py`, `hypothesis_exchange.py` | INFO-level structured logs for import/export events via stdlib `logging` |
| Quarantine detection | `daemon_scheduler.py` | `quarantine_count` in `VaultState`; scans `notes/*.md` for `quarantine: true` |
| Quarantine signal | `decision_engine.py` | `quarantine_review` signal at `multi_session` speed when count > 0 |
| Skill guards | `reflect/SKILL.md`, `reweave/SKILL.md`, `tournament/SKILL.md` | Quarantine Guard sections: skip notes with `quarantine: true` frontmatter |
| Dead field annotation | `federation_config.py` | `quarantine_auto_accept_days` marked as parsed-but-not-yet-implemented |

**Design decisions:**
- `strip_html()` uses stdlib only (no new dependency); placed in `schema_validator.py` alongside existing sanitization.
- Builder pattern for hypotheses mirrors `build_claim_note()` -- centralizes all sanitization in one function.
- Quarantine enforcement is dual-layer: Python code (export filter + VaultState signal) for automated workflows; skill instructions for interactive workflows.
- Trust guard (`can_import_from()`) NOT added inside import functions -- kept as calling convention per existing pattern.
- `quarantine_auto_accept_days` deferred until federation is in active use.
- Logging via stdlib -- structured log lines at INFO/DEBUG; no separate audit file.

### P2: Slack bot authority model -- COMPLETE

**Problem:** The paper's Cases 2-3 showed agents complying with non-owner requests for sensitive information. Our slack_bot.py responds to any message in configured channels with no sender verification. Case 8 showed display-name spoofing; Cases 4-5 showed DoS via message loops.

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| Authority config | `daemon_config.py` | `AuthorityConfig` dataclass (owner_ids, allowed_ids, public_access, rate limits); nested under `BotConfig` |
| Rate limiter | `slack_bot.py` | `RateLimiter` class -- sliding 60s window per user with denial cooldown |
| Auth constants | `slack_bot.py` | `AUTH_OWNER`, `AUTH_ALLOWED`, `AUTH_PUBLIC`, `AUTH_DENIED` levels |
| Authorization gate | `slack_bot.py` | `_authorize()` method on `SlackBot`; checked in `_process_event` before processing |
| Config parsing | `slack_bot.py` | `SlackBotConfig.from_env()` reads `bot.authority` section from daemon-config.yaml |
| YAML config | `ops/daemon-config.yaml` | `authority:` sub-section under `bot:` with commented defaults |
| Tests | `tests/test_slack_bot.py` | `TestRateLimiter` (6 tests), `TestAuthorize` (7 tests) |
| Tests | `tests/test_daemon_config.py` | `TestDaemonConfigBotAuthority` (2 tests) |

**Design decisions:**
- Default config preserves current open-access behavior (`public_access: true`, empty owner/allowed lists) -- no breaking change.
- Slack user IDs (not display names) as trust anchor -- per Case 8 display-name spoofing finding.
- Sliding-window rate limiter with configurable cooldown prevents DoS/loop patterns (Cases 4-5).
- Auth levels are checked before any processing (rate limiter, Claude API call, vault context).
- Authority config is frozen (dataclass) and loaded once from YAML -- not modifiable at runtime.

### P3: Daemon audit trail -- COMPLETE

**Problem:** The daemon operates autonomously with UNATTENDED_OVERRIDE, which disables AskUserQuestion and EnterPlanMode. The paper's discussion identifies that agents operating at L4 autonomy with L2 self-awareness is a structural risk. Our daemon has metabolic governors (P0 from boundary maturation), but its decisions are logged descriptively, not against a policy spec.

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| Audit log writer | `_code/src/engram_r/audit.py` | `RuleEvaluation` and `AuditEntry` dataclasses; `append_audit_entry()` for atomic JSONL append to `ops/daemon/logs/audit.jsonl` |
| Skill backoff | `_code/src/engram_r/_daemon_backoff.py` | `read_backoff()`, `record_failure()`, `record_success()`, `skill_in_backoff()` -- per-skill failure tracking with exponential cooldown |
| Decision ceiling | `daemon_scheduler.py` | `DAEMON_ALLOWED_SKILLS` frozenset (14 skills); `_validate_task_skill()` raises ValueError for disallowed skills |
| Audited selection | `daemon_scheduler.py` | `select_task_audited()` builds audit trail during cascade evaluation; `SelectionResult` dataclass bundles task + audit |
| Backward compat | `daemon_scheduler.py` | `select_task()` rewritten as one-liner wrapper around `select_task_audited()` |
| CLI audit write | `daemon_scheduler.py` | `main()` writes audit entry to JSONL (best-effort, try/except) |
| Shell backoff | `ops/scripts/daemon.sh` | `skill_in_backoff()`, `record_skill_success()`, `record_skill_failure()` functions delegating to Python module |
| Shell integration | `ops/scripts/daemon.sh` | Backoff check before execution, success/failure recording on completion/gave-up |
| Tests | `_code/tests/test_audit.py` | 10 tests: serialization, file creation, multi-line append, temp cleanup |
| Tests | `_code/tests/test_skill_backoff.py` | 14 tests: failure counting, threshold activation, escalation, cap, success reset, expiry |
| Tests | `_code/tests/test_daemon_scheduler.py` | `TestDaemonAllowedSkills` (4 tests), `TestSelectTaskAudited` (10 tests) |

**Design decisions:**
- Decision ceiling is hardcoded (`DAEMON_ALLOWED_SKILLS` frozenset), not config-driven -- prevents agent from widening its own ceiling via config edits. Follows the same pattern as `PROTECTED_PATHS` in integrity.py.
- Scheduler stays pure/stateless -- `audit.py` handles disk I/O; backoff state lives in the shell layer via `_daemon_backoff.py`.
- `select_task()` wrapper preserves backward compat -- existing 170+ tests pass unchanged.
- Audit is best-effort -- filesystem errors do not block task selection.
- Backoff tracks at skill level -- if tournament fails across different goals, tournament backs off entirely.
- Escalation: 30 min after 3 consecutive failures, 60 min after 6, capped at 2 h. Success resets.
- JSONL format -- one entry per decision cycle, queryable with `jq`, no rotation built in.

**Allowed skills:** experiment, tournament, meta-review, landscape, rethink, reflect, reduce, remember, reweave, federation-sync, notify-scheduled, validate, verify, ralph.

**Not allowed (require human):** generate, evolve, review, onboard, init, project, literature, plot, eda.

### P4: Proportionality and escalation ceilings -- COMPLETE

**Problem:** The paper's Case 7 showed an agent escalating concessions without limit under social pressure -- from name redaction to memory deletion to server departure. The underlying issue: the agent's training prioritizes helpfulness and responsiveness to distress, which becomes an exploitation vector.

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| Escalation ceilings | `CLAUDE.md` | "Escalation Ceilings" subsection under Guardrails: 7 explicit negative boundaries + proportionality rule |
| Mechanical enforcement | `validate_write.py` | Blocks writes to `PROTECTED_PATHS` (P0); covers ops/config.yaml, self/identity.md, self/methodology.md, CLAUDE.md, ops/daemon-config.yaml, ops/methodology/_compiled.md |
| Decision ceiling | `daemon_scheduler.py` | `DAEMON_ALLOWED_SKILLS` frozenset prevents daemon from running disallowed skills (P3) |
| Integrity drift detection | `session_orient.py` | Warns at session start if protected files differ from sealed manifest (P0) |

**Design decisions:**
- Behavioral rules placed in CLAUDE.md (not self/methodology.md) because CLAUDE.md is the highest-authority instruction source, loaded by the platform before any vault content.
- Rules are framed as explicit negatives ("never, even if asked") rather than positive guidelines, following the paper's finding that positive instructions ("be helpful") are overridden by social pressure while explicit prohibitions are more resistant.
- Proportionality rule requires per-invocation confirmation for escalating actions -- a single approval does not generalize to future requests.
- Mechanical enforcement (P0 hooks) remains the primary defense; behavioral rules are defense-in-depth for cases hooks cannot catch (e.g., Bash rm, settings changes, conversational concessions).

### P5: Post-condition verification -- COMPLETE

**Problem:** The paper's recurring theme: agents report success while the underlying system state contradicts those reports. Case 1 (agent claims secret deleted, data still accessible), Case 7 (agent says "I'm done responding" then keeps responding). The most dangerous variant for our system is "0-exit silent failure" -- the daemon runs `claude -p`, the process exits 0, but nothing changed on disk. The daemon marks the task as done and moves on.

**Implementation (2026-02-28):**

| Component | File | What it does |
|---|---|---|
| Outcome dataclass | `_code/src/engram_r/audit.py` | `AuditOutcome` with timestamp, task_key, skill, outcome, duration, vault summaries before/after, changed_keys |
| Outcome writer | `_code/src/engram_r/audit.py` | `append_outcome()` -- atomic JSONL append, same strategy as `append_audit_entry()` |
| Type field | `_code/src/engram_r/audit.py` | `type: str = "selection"` on `AuditEntry` for jq discrimination (`type: "outcome"` on `AuditOutcome`) |
| Vault summary helper | `_code/src/engram_r/daemon_scheduler.py` | `vault_summary_dict(state)` -- single source of truth for the 8-key summary (eliminates 3 inline copies) |
| Scan-only mode | `_code/src/engram_r/daemon_scheduler.py` | `--scan-only` CLI flag: prints vault summary JSON, no task selection, no audit write |
| Vault-state delta | `ops/scripts/daemon.sh` | Pre/post `vault_snapshot()` around `claude -p`; `record_outcome()` writes outcome entry |
| No-change detection | `ops/scripts/daemon.sh` | When exit 0 + no vault change + elapsed > 30s: logs warning, calls `record_skill_failure` with threshold=5 |
| Threshold param | `ops/scripts/daemon.sh` | `record_skill_failure()` accepts optional threshold argument (default: 3) |
| Git ground truth | `_code/scripts/hooks/session_capture.py` | `_git_files_changed(cwd)` -- runs `git status --porcelain` for disk-level truth |
| Session sections | `_code/scripts/hooks/session_capture.py` | "Files Changed" (git truth) + "Tool Calls" (transcript) replaces single "Files Written" section |
| Tests | `_code/tests/test_audit.py` | 9 new tests: AuditEntryType (3), AuditOutcome (3), AppendOutcome (3) |
| Tests | `_code/tests/test_daemon_scheduler.py` | VaultSummaryDict (4), ScanOnlyMode (4), audit type assertion (1) |
| Tests | `_code/tests/test_session_capture.py` | GitFilesChanged (7), SessionOutputSections (1) |

**Design decisions:**
- `AuditOutcome` is a separate entry type, not merged into `AuditEntry`, because selection and outcome happen at different times and potentially from different processes (Python scheduler vs shell wrapper). The `type` field (`"selection"` vs `"outcome"`) enables jq discrimination.
- No-change detection uses vault-summary comparison (8 scalar counters) rather than file-level diffs -- lightweight, deterministic, and sufficient to catch silent failures.
- No-change tasks are still marked done -- retrying the same prompt is unlikely to produce a different result. The pattern is surfaced via backoff escalation (threshold=5, higher than the normal failure threshold=3).
- `--scan-only` mode enables pre/post snapshots from the shell without coupling the scanner to the task executor.
- Git-based ground truth in session_capture.py provides disk-level verification of what actually changed, independent of what the agent reported via tool calls.
- Skill-level post-condition assertions (e.g., "/reduce must produce >= 1 file") are explicitly deferred -- they would require per-skill config and make the system brittle. The vault-state delta catches the symptom (no change) without encoding per-skill expectations.

### Gap Fixes: Integrity Check Follow-up (2026-03-01)

Post-sprint integrity check compared P0-P5 implementations against the paper's full case table and identified 5 residual gaps. Two were doc-only (private deliberation surface note, provider-values note -- already applied above). Three required code-level fixes:

**Gap 1: Text-level PII scanning**

| Component | File | What it does |
|---|---|---|
| Text PII patterns | `pii_filter.py` | `_TEXT_PII_PATTERNS` list (SSN, email, phone, MRN); `redact_text()` substitutes `[REDACTED]`; `scrub_outbound()` alias for call-site clarity |
| Tests | `test_pii_filter.py` | `TestRedactText` (9 tests): per-pattern, clean passthrough, empty string, multiple patterns, Elo false-positive guard |

Existing `pii_filter.py` only handled DataFrame column detection for /eda. The text-level functions extend coverage to free text in federation exports and Slack responses.

**Gap 2-3: PII gate on federation exports and Slack outbound**

| Component | File | What it does |
|---|---|---|
| Export PII gate | `claim_exchange.py` | `sanitize_pii: bool = False` on `export_claim()` / `export_claims()`; when True: clears `verified_who`/`verified_date`, runs `redact_text()` on body/description |
| Export PII gate | `hypothesis_exchange.py` | `sanitize_pii: bool = False` on `export_hypothesis()` / `export_hypotheses()`; when True: runs `redact_text()` on statement, mechanism, predictions, assumptions, limitations |
| Export policy | `federation_config.py` | `redact_pii_on_export: bool = True` on `ExportPolicy`; parsed from `export.redact_pii` in federation.yaml; safe default for federation |
| Slack bot scrub | `slack_bot.py` | `scrub_outbound()` on Claude response text before `_split_message()` -- always on, no toggle |
| Slack notify scrub | `slack_notify.py` | `scrub_outbound()` on notification text; `_scrub_blocks()` helper for section/context/header block types -- always on |
| Tests | `test_claim_exchange.py` | `TestExportPiiSanitization` (4 tests) |
| Tests | `test_hypothesis_exchange.py` | `TestExportPiiSanitization` (3 tests) |
| Tests | `test_federation_config.py` | `TestExportPolicyPiiField` (3 tests) |
| Tests | `test_slack_bot.py` | `TestOutboundScrub` (2 tests) |
| Tests | `test_slack_notify.py` | `TestOutboundScrub` (2 tests) |

Design decisions:
- Federation PII scrub is opt-in per export call (`sanitize_pii=False` default) for backward compat; the federation sync skill reads `ExportPolicy.redact_pii_on_export` (default True) and passes it through.
- Slack PII scrub is always on (no config toggle) -- outbound PII filtering is a non-negotiable security boundary.
- No NER-based name detection -- regex patterns for SSN/email/phone/MRN cover the structured PII surface without ML dependencies or false positives on scientific terms.

**Gap 4: Methodology source file protection**

| Component | File | What it does |
|---|---|---|
| Monitored dirs | `integrity.py` | `MONITORED_DIRS` constant; `_scan_monitored_dirs()` hashes `*.md` excluding `PROTECTED_PATHS`; stored under `monitored_files` key in manifest |
| Seal/verify | `integrity.py` | `seal_manifest()` includes monitored files; `verify_manifest()` checks them; `_cli_status()` shows monitored dir file count |
| Write warning | `validate_write.py` | Warn (not block) on writes to `ops/methodology/*.md` (excluding `_compiled.md` which is blocked as PROTECTED_PATHS) |
| Tests | `test_integrity.py` | `TestMonitoredDirs` (3 tests): seal includes, verify detects drift, separation from protected |
| Tests | `test_validate_write.py` | `TestMethodologySourceWarning` (2 tests): warns but does not block, _compiled.md still blocked |

Design decisions:
- Monitored files are warn-not-block (medium risk, frequently edited during methodology refinement) unlike protected files (high risk, rarely edited).
- Monitored files stored under a separate `monitored_files` manifest key -- keeps the protected/monitored boundary clear.
- `ops/methodology/_compiled.md` remains in `PROTECTED_PATHS` (blocked) -- it is the high-value compilation target.

**Gaps NOT addressed (by design):**
- No NER name detection (false positives, ML dependency).
- No config toggle for Slack scrub (always on -- security boundary).
- No private deliberation surface code (doc-only; single-operator makes it low risk).
- No provider-values mitigation (environmental dependency, outside control surface).
- No inbound Slack message scrubbing (messages come from authenticated users).

---

## What We Can Learn but Don't Need to Build

Some paper findings are informative for awareness but don't require code changes:

**Echo-chamber reinforcement (Case 15).** Two agents validating each other's flawed reasoning. Relevant if we ever deploy multiple EngramR instances in federation with automatic trust. Current mitigation: federation trust defaults to `untrusted` (reject all). Keep this default.

**Identity spoofing via display name (Case 8).** Platform-specific to Discord. Our Slack integration should use user IDs, not display names. Already noted in P2 above.

**Agent self-modification to bypass safety (Case 1, 10).** The paper's agents could modify their own operating instructions. Our agent can modify self/ files. P0 above addresses this. The deeper lesson: any file the agent can write AND that influences its own behavior is a self-modification vector. Inventory these files and gate writes to them.

**Social engineering resistance is shallow (Case 15).** Agents detected social engineering through pattern-matching on surface cues but couldn't reason about whether their verification method was itself compromised. This is a fundamental LLM limitation, not something we can engineer around. Awareness is the mitigation: assume the agent can be socially engineered and design mechanical safeguards (hooks, permission gates) rather than relying on the agent's judgment for security-critical decisions.

**Provider-level influence on agent behavior (Case 6).** The paper found that Kimi K2.5 silently truncated responses on politically sensitive topics via API-level censorship, invisible to the agent and user. EngramR uses Claude (Anthropic), which has different refusal/bias characteristics. This is an environmental dependency, not a system-level mitigation target -- provider-level behavior is outside our control surface.

**Outbound content review (Case 11).** After identity spoofing, an agent sent defamatory content to an entire email contact list. EngramR does not have email capabilities. Slack commands are gated by P2 auth. Federation exports are gated by trust config. The daemon skill ceiling (P3) prevents autonomous use of communication skills. Interactive sessions rely on user-in-the-loop for outbound actions.

**No private deliberation surface (structural deficit #3).** The paper identifies that agents leak sensitive information through artifacts, cross-channel posts, and tool outputs even when chain-of-thought is hidden. EngramR has no concept of private vs. public deliberation space -- session logs, vault files, and ops/ are all readable. Under the current single-operator design this is low risk (the operator sees everything by definition), but would need addressing if multi-user access is added.

---

## Inventory: Self-Modification Vectors

Files the agent can write that influence its own future behavior:

| File | Influence | Protection | Risk |
|---|---|---|---|
| self/identity.md | Loaded every session; shapes all behavior | Integrity manifest + write block (P0) | **Mitigated** |
| self/methodology.md | Loaded every session; shapes work patterns | Integrity manifest + write block (P0) | **Mitigated** |
| self/goals.md | Loaded every session; drives task selection | None (intentionally unprotected -- modified every session) | Low |
| ops/config.yaml | Controls hooks, validation, pipeline compliance | Integrity manifest + write block (P0) | **Mitigated** |
| ops/daemon-config.yaml | Controls daemon autonomy, model selection, thresholds | Integrity manifest + write block (P0) | **Mitigated** |
| ops/reminders.md | Loaded at session start; drives action | None (intentionally unprotected -- modified every session) | Low |
| ops/methodology/*.md | Source for _compiled.md; shapes behavioral rules | `MONITORED_DIRS` in integrity manifest (drift detection); `validate_write.py` warns on writes (Gap Fix 4, 2026-03-01) | **Monitored** |
| ops/methodology/_compiled.md | Loaded every session via session_orient.py | Integrity manifest + write block (P0) | **Mitigated** |
| CLAUDE.md | Ultimate authority; loaded by Claude Code platform | Integrity manifest + write block (P0) + git-tracked | **Mitigated** |
| .claude/settings.json | Hook configuration; controls what runs | Git-tracked; rarely modified | Medium |
| .claude/skills/*/SKILL.md | Skill definitions; control tool access per skill | Git-tracked | Medium |

**Status (post-Gap Fixes):** All 6 high-risk files are covered by the integrity manifest (drift detection at session start) and validate_write.py (write blocking). Methodology source files (`ops/methodology/*.md`) are now tracked via `MONITORED_DIRS` in the integrity manifest (drift detection) and `validate_write.py` (write warnings), downgrading from medium to monitored. The remaining medium-risk files (`.claude/settings.json`, skill definitions) are git-tracked, providing implicit protection via dirty-state visibility. `self/goals.md` and `ops/reminders.md` are intentionally unprotected because they are modified during normal operation.

---

## Implementation Sequence

1. ~~**P0: Integrity manifest + session-start verification**~~ -- **COMPLETE (2026-02-28)**
2. ~~**P1: Federation trust boundary hardening**~~ -- **COMPLETE (2026-02-28)**
3. ~~**P2: Slack bot authority model**~~ -- **COMPLETE (2026-02-28)**
4. ~~**P3: Daemon audit trail**~~ -- **COMPLETE (2026-02-28)**
5. ~~**P4: Escalation ceilings in CLAUDE.md**~~ -- **COMPLETE (2026-02-28)**
6. ~~**P5: Post-condition verification**~~ -- **COMPLETE (2026-02-28)**
7. ~~**Gap fixes: Text PII scanning, federation/Slack PII gates, methodology monitoring**~~ -- **COMPLETE (2026-03-01)**

---

## References

- Shapira, N. et al. (2026). "Agents of Chaos." arXiv:2602.20021v1.
- EngramR boundary maturation plan: docs/development/boundary-maturation-plan.md
- Federation trust model: ops/federation.yaml
- Daemon configuration: ops/daemon-config.yaml
- Metabolic indicators: _code/src/engram_r/metabolic_indicators.py
