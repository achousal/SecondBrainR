---
description: "External integrations -- Slack (notifications, bot, schedules), Obsidian, MCP servers"
type: manual
created: 2026-03-01
---

# Integrations

EngramR connects to external services via Slack (team notifications and
interactive bot), Obsidian (vault browsing), and MCP servers (Claude Code
plugins).

---

## Slack integration

Two complementary Slack surfaces: outbound notifications and an interactive
vault-aware bot.

### Notifications (slack_notify.py)

All outbound notifications are:
- Threaded under a daily parent message per channel (state in
  `ops/daemon/slack-threads.json`, auto-pruned after 7 days)
- PII-scrubbed via `scrub_outbound()` before sending
- Wrapped in try/except -- they never crash the session
- Routed to channels by event type (alerts -> alerts channel, daemon events ->
  daemon channel, rest -> default)

Notification events: session start/end, daemon task completion, daemon alerts,
tournament results, meta-review completion, items queued for human review,
inbound message summaries.

### Interactive bot (slack_bot.py)

A `slack_bolt` Socket Mode bot that provides two-way Claude-powered
conversation grounded in vault context:

- **Vault context** -- reads `self/identity.md`, `self/methodology.md`,
  `self/goals.md`, and `ops/reminders.md` into the system prompt; refreshes
  every 5 minutes
- **Authority model** -- 4 levels: owner (full skill access), allowed
  (configured list), public (any user when enabled), denied
- **Rate limiting** -- sliding 60-second window per user
- **Skill routing** -- detects `/command args` syntax or extracts skill intent
  from Claude responses; mutative skills require explicit `yes`/`no`
  confirmation in-thread (5-minute TTL)
- **Thread context** -- maintains conversation history from Slack thread
  replies (capped at configurable max messages)

### Scheduled notifications (schedule_runner.py)

Periodic DM delivery without invoking an LLM:

| Schedule type | Content |
| --- | --- |
| **Weekly project update** | Role-adaptive DM (lead/contributor see full detail; observer sees counts). Projects, experiments, hypotheses, reminders. |
| **Stale project alert** | Projects with no experiment/hypothesis activity beyond a threshold |
| **Experiment reminder** | Upcoming deadlines and blocking pre-analysis gates |

Configured in `ops/daemon-config.yaml` under `schedules:`. Cadence options:
daily, weekly (by weekday), monthly (by day number). Idempotent via marker keys.

### Environment variables (Slack)

| Variable | Purpose |
| --- | --- |
| `SLACK_BOT_TOKEN` | Bot OAuth token (xoxb-...) |
| `SLACK_APP_TOKEN` | App-level token for Socket Mode (xapp-...) |
| `SLACK_BOT_CHANNEL` | Default channel for bot posts |
| `SLACK_DEFAULT_CHANNEL` | Fallback channel for notifications |
| `SLACK_TEAM_ID` | Workspace team ID |
| `ANTHROPIC_API_KEY` | Claude API key for bot responses |

See the [Setup Guide](setup-guide.md) for step-by-step Slack app creation and
MCP server configuration.

---

## Obsidian

EngramR vault files are standard markdown. Opening the vault directory in
[Obsidian](https://obsidian.md/) gives you a browsable knowledge graph with
backlink navigation, search, and the graph view -- no configuration required.

For programmatic access, `obsidian_client.py` wraps the
[Local REST API plugin](https://github.com/coddingtonbear/obsidian-local-rest-api).
It provides CRUD operations on notes, search, and frontmatter updates via
stdlib `urllib` (handles self-signed SSL). The client is **not a runtime
dependency** -- vault access in normal operation uses direct filesystem I/O
via Claude Code's Read/Write tools.

```python
from engram_r.obsidian_client import ObsidianClient

client = ObsidianClient.from_env()          # reads OBSIDIAN_API_URL, OBSIDIAN_API_KEY
content = client.get_note("notes/my-claim.md")
results = client.search("some query")
client.update_frontmatter("notes/my-claim.md", "confidence", "established")
```

Multi-vault support: `ObsidianClient.from_vault("lab-name")` looks up
credentials in `~/.config/engramr/vaults.yaml`.

---

## MCP servers

EngramR extends through [MCP servers](https://modelcontextprotocol.io/) --
standardized plugins that give Claude Code access to external services.
`.mcp.json` ships with the Slack MCP server for channel interaction alongside
the custom notification stack.

See the [Setup Guide](setup-guide.md) for step-by-step MCP server
configuration.

---

## Domain profiles

EngramR is domain-agnostic. Domain-specific behavior is configured via profile
directories in `_code/profiles/`. A profile bundles:

| File | What it configures |
| --- | --- |
| `profile.yaml` | Search backend priority chain, recognized data layers, required env vars |
| `identity.yaml` | Agent identity seed -- purpose statement, domain, focus areas |
| `confounders.yaml` | Auto-drafted confounder claims per data layer (e.g., batch effects for transcriptomics, ion suppression for metabolomics; or survey bias for social science, instrument drift for physical sciences) |
| `heuristics.yaml` | File extension and tool-name to data-layer inference rules (e.g., `.bam` -> Genomics, DESeq2 -> Transcriptomics; `.fits` -> Astronomy, scikit-learn -> ML) |
| `pii_patterns.yaml` | Domain-specific PII column patterns added to the base filter |
| `palettes.yaml` | Lab and semantic color palettes |
| `styles/PLOT_DESIGN.md` | Domain-specific plot geometry overrides |
| `styles/{lab}.md` | Per-lab accent colors and palette policies |

The default `bioinformatics` profile enables PubMed + arXiv search, recognizes
8 omics modalities (Genomics, Transcriptomics, Proteomics, Metabolomics,
Epigenomics, Metagenomics, Clinical/EHR, scRNA-seq), and ships with confounder
templates for each.

To adapt EngramR to a different research domain, copy the `bioinformatics/`
directory, edit `profile.yaml`, and set `domain.name` in `ops/config.yaml`.

---

## See Also

- [Setup Guide](setup-guide.md) -- full installation and configuration instructions
- [Configuration](configuration.md) -- ops/config.yaml reference
- [Administration](administration.md) -- daemon and notification scheduling
