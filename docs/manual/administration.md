---
description: "Administration -- daemon, hooks, decision engine, code section health, helper scripts"
type: manual
created: 2026-03-01
---

# Administration

Operational systems for autonomous processing, session lifecycle, and vault
maintenance.

---

## Research loop daemon

An autonomous background process that reads vault state, selects the
highest-priority task, and executes it via Claude Code. Generative work can
run fully autonomous or queue to `ops/daemon-inbox.md` for human review.

**Safety ceiling.** The daemon can only invoke a hardcoded frozenset of skills
(tournament, meta-review, landscape, reflect, reduce, remember, reweave,
federation-sync, validate, verify, ralph, rethink, experiment,
notify-scheduled). This set is immutable at runtime.

### Priority cascade (P0 highest)

| Tier | Trigger | Example task |
| --- | --- | --- |
| P0 | Health gate failures | Schema violations -> `/validate`, orphans -> `/reflect` |
| P1 | Metabolic alarms | Queue pressure -> `/ralph`, creation overload -> `/reflect` |
| P2 | Maintenance signals | Observations -> `/rethink`, queue backlog -> `/ralph`, unmined sessions -> `/remember` |
| P3 | Research cycle | Under-matched hypotheses -> `/tournament`, stale meta-review -> `/meta-review` |
| P4 | Generative | Stale cycles -> `/landscape`, hypothesis generation |

### Metabolic self-regulation

Five derived indicators govern daemon behavior:

| Indicator | What it measures | Alarm threshold |
| --- | --- | --- |
| QPR (Queue Pressure Ratio) | Days of queue backlog at current processing rate | > 3.0 -- halts generation |
| VDR (Verification Debt Ratio) | % of claims not human-verified | > 80% (informational) |
| CMR (Creation:Maintenance Ratio) | New notes vs maintenance completions (7-day window) | > 10:1 -- redirects to consolidation |
| HCR (Hypothesis Conversion Rate) | % hypotheses with empirical engagement | < 15% -- redirects to SAP support |
| SWR (Session Waste Ratio) | Sessions per useful artifact | > 5.0 -- triggers stub archival |

When metabolic alarms fire, the daemon suppresses P3/P4 (creation) tasks
and redirects to P1/P2 (maintenance). Check indicators via CLI:

```bash
cd _code
uv run python -m engram_r.metabolic_indicators ..
```

### Model assignment

Tournament primary goal uses Opus; meta-review, landscape, reflect, reduce use
Sonnet; verify, validate, remember use Haiku. Configured in
`ops/daemon-config.yaml` under `models:`.

### Starting the daemon

```bash
tmux new -s daemon 'bash ops/scripts/daemon.sh'
```

See [Configuration](configuration.md) for the full daemon-config.yaml
reference including cooldown, retry, and timeout options.

---

## Hooks

Five hooks automate the session lifecycle. All are configured in
`.claude/settings.json` and log errors to stderr (non-blocking). Disable any
hook via `ops/config.yaml`.

| Hook | Event | Mode | What it does |
| --- | --- | --- | --- |
| **Session Orient** | SessionStart | sync | Loads identity, surfaces active goals, leaderboard, meta-review, overdue reminders, vault stats, integrity warnings, methodology directives, Slack inbound messages |
| **Write Validate** | PostToolUse (Write/Edit) | sync | 8-gate schema enforcement on every note write (see [Security](security.md)) |
| **Pipeline Bridge** | PostToolUse (Write) | async | Suggests `/reduce` when new literature notes or hypotheses are written; deduplicates against queue |
| **Auto Commit** | PostToolUse (Write/Edit) | async | Auto-commits every vault change with descriptive messages |
| **Session Capture** | Stop | sync | Persists session summary, files changed, skills invoked, and git status to `ops/sessions/` |

```bash
# Smoke tests
cd _code
uv run python scripts/hooks/session_orient.py
echo '{"tool_name":"Write","tool_input":{"file_path":"...","content":"..."}}' | uv run python scripts/hooks/validate_write.py
```

---

## Decision engine

The `/next` skill and daemon scheduler share a unified decision engine
(`decision_engine.py`) that classifies vault signals by urgency:

- **Session priority**: orphan notes, inbox pressure, pending observations/tensions
- **Multi-session priority**: queue backlog, stale notes, quarantined imports
- **Slow priority**: stale health reports

The engine deduplicates against the last 3 recommendations in `ops/next-log.md`
and checks if the daemon is already running (reads PID from
`ops/daemon/.daemon.pid`).

---

## Code section health

Two complementary health surfaces:

- `/health` -- vault integrity (schema, orphans, links). Scans `notes/`,
  `_research/`, `self/`, `projects/` only.
- `/dev` -- code integrity (tests, lint, build). Scans code sections.

6 sections defined in `ops/sections.yaml`: core-lib, r-lib, skills, ops-infra,
site, docs-templates. Each has paths, checks, and a dependency graph.

```bash
./ops/scripts/section-check.sh                    # all sections (or: /dev)
./ops/scripts/section-check.sh core-lib            # single section, verbose (or: /dev core-lib)
./ops/scripts/section-check.sh --changed           # auto-detect from git diff (or: /dev --changed)
./ops/scripts/section-check.sh --affected core-lib # section + dependents (or: /dev --affected core-lib)
```

---

## Helper scripts

```bash
./ops/scripts/rename-note.sh "old title" "new title"   # safe rename (updates all wiki links)
./ops/scripts/orphan-notes.sh                           # find unlinked claims
./ops/scripts/dangling-links.sh                         # find broken links
./ops/scripts/backlinks.sh "title"                      # count incoming links
./ops/scripts/link-density.sh                           # average links per claim
./ops/scripts/validate-schema.sh                        # check all claims against templates
```

---

## See Also

- [Security](security.md) -- defense-in-depth layers enforced by hooks
- [Configuration](configuration.md) -- daemon-config.yaml and ops/config.yaml reference
- [Troubleshooting](troubleshooting.md) -- diagnosing operational issues
