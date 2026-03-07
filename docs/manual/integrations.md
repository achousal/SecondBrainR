---
description: "External integrations -- Slack, Obsidian, MCP servers, research daemon, multi-vault"
type: manual
created: 2026-03-01
updated: 2026-03-07
---

# Integrations

EngramR connects to external services for team notifications, vault browsing,
and plugin extensibility. All integrations are optional -- the core system
works without any of them.

**Prerequisites:** [Getting Started](getting-started.md)

---

## Slack

### Overview

Two complementary Slack surfaces: outbound notifications and an interactive
vault-aware bot.

#### Notifications (slack_notify.py)

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

#### Interactive bot (slack_bot.py)

A `slack_bot` Socket Mode bot that provides two-way Claude-powered
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

#### Scheduled notifications (schedule_runner.py)

Periodic DM delivery without invoking an LLM:

| Schedule type | Content |
| --- | --- |
| **Weekly project update** | Role-adaptive DM (lead/contributor see full detail; observer sees counts). Projects, experiments, hypotheses, reminders. |
| **Stale project alert** | Projects with no experiment/hypothesis activity beyond a threshold |
| **Experiment reminder** | Upcoming deadlines and blocking pre-analysis gates |

Configured in `ops/daemon-config.yaml` under `schedules:`. Cadence options:
daily, weekly (by weekday), monthly (by day number). Idempotent via marker keys.

### Setup

#### Step 1: Create a Slack app

1. Go to [api.slack.com/apps](https://api.slack.com/apps).
2. Click **Create New App** > **From scratch**.
3. Name it something like `EngramR` and select your workspace.

#### Step 2: Configure OAuth and scopes

1. In the left sidebar, go to **OAuth & Permissions**.
2. Scroll to **Bot Token Scopes** and add the following:

| Scope | Purpose | Used by |
|-------|---------|---------|
| `channels:read` | List and discover channels | MCP server |
| `channels:history` | Read channel message history | MCP server, notifications |
| `chat:write` | Post messages and thread replies | MCP server, notifications |
| `reactions:write` | Add emoji reactions to messages | Notifications |
| `users:read` | Resolve user IDs to display names | MCP server, notifications |

These are the minimum scopes EngramR needs. Do not add user token scopes --
everything runs through the bot token.

#### Step 3: Install the app to your workspace

1. Still in **OAuth & Permissions**, scroll up and click **Install to Workspace**.
2. Review the permissions and click **Allow**.
3. Copy the **Bot User OAuth Token** that appears (starts with `xoxb-`). You
   will need this in multiple places below.

#### Step 4: Invite the bot to your channel

The bot can only read and post in channels it has been invited to.

1. Open the Slack channel you want EngramR to use.
2. Type `/invite @EngramR` (or whatever you named the app).
3. Note the **Channel ID**: click the channel name at the top, scroll to the
   bottom of the details panel -- the ID looks like `C0123456789`.

#### Step 5: Find your Team ID

Open Slack in a browser. The URL looks like:
```
https://app.slack.com/client/T0123456789/C0123456789
```
The `T...` segment is your Team ID.

#### Step 6: Configure the MCP server

Add the Slack server to `.mcp.json` at the project root (or merge into the
existing `mcpServers` object):

```json
{
  "mcpServers": {
    "slack": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-slack"],
      "env": {
        "SLACK_BOT_TOKEN": "xoxb-your-token-here",
        "SLACK_TEAM_ID": "T0123456789"
      }
    }
  }
}
```

Restart Claude Code and run `/mcp` to verify the Slack server appears as
connected.

#### Step 7: Enable automated notifications

EngramR can also send notifications for session events, daemon completions, and
alerts. This works independently of the MCP server -- it calls the Slack Web
API directly via the same bot token.

1. Add the following to your `.env` file:

```bash
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_DEFAULT_CHANNEL=C0123456789   # Channel ID from step 4
SLACK_TEAM_ID=T0123456789           # Team ID from step 5
```

2. Configure notification behavior in `ops/daemon-config.yaml`:

```yaml
notifications:
  enabled: true
  level: all          # all | alerts-only | off
  channels:
    default: "C0123456789"
  events:
    session_start: true
    session_end: true
    daemon_task_complete: true
    daemon_alert: true
  inbound:
    enabled: true
    lookback_hours: 24
```

Notifications use daily threading: one parent message per day with all events
as replies underneath.

If `SLACK_BOT_TOKEN` is not set, all notification code silently skips -- no
errors, no crashes.

### Environment variables

| Variable | Purpose |
| --- | --- |
| `SLACK_BOT_TOKEN` | Bot OAuth token (xoxb-...) |
| `SLACK_APP_TOKEN` | App-level token for Socket Mode (xapp-...) |
| `SLACK_BOT_CHANNEL` | Default channel for bot posts |
| `SLACK_DEFAULT_CHANNEL` | Fallback channel for notifications |
| `SLACK_TEAM_ID` | Workspace team ID |
| `ANTHROPIC_API_KEY` | Claude API key for bot responses |

---

## Obsidian

### Overview

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

### Setup

1. Open Obsidian.
2. "Open folder as vault" > select your vault path.
3. Install the **Local REST API** community plugin for MCP integration.

---

## MCP Servers

### Overview

EngramR extends through [MCP servers](https://modelcontextprotocol.io/) --
standardized plugins that give Claude Code access to external services.
`.mcp.json` ships with the Slack MCP server for channel interaction alongside
the custom notification stack.

### Configuration

Servers are configured in `.mcp.json` at the project root. The Slack MCP server
setup is covered above in [Slack > Setup > Step 6](#step-6-configure-the-mcp-server).

#### Obsidian MCP

The mcp-obsidian server gives Claude programmatic access to vault content
through the Obsidian Local REST API -- useful for Obsidian-specific search and
graph queries. Not required for normal operation; Claude Code reads and writes
files directly.

Add to `.mcp.json`:

```json
{
  "mcpServers": {
    "mcp-obsidian": {
      "command": "uvx",
      "args": ["mcp-obsidian"],
      "env": {
        "OBSIDIAN_API_KEY": "your-api-key-from-local-rest-api",
        "OBSIDIAN_HOST": "127.0.0.1",
        "OBSIDIAN_PORT": "27124"
      }
    }
  }
}
```

The API key comes from the Local REST API plugin. The default host and port
match the plugin's defaults -- only change them if you customized the plugin
settings.

To verify: restart Claude Code and check that `mcp-obsidian` appears in the MCP
server list. You can test with a vault search or file read.

---

## Research Daemon

The daemon runs autonomous synthesis and maintenance in the background.

```bash
tmux new -s daemon 'bash ops/scripts/daemon.sh'
```

For daemon configuration, priority cascade, and metabolic self-regulation, see [Administration](administration.md).

---

## Multi-Vault

Multiple vaults (e.g., one per lab) are managed through a central registry.

1. Create the vault registry:

```bash
mkdir -p ~/.config/engramr
cp ~/.config/engramr/vaults.yaml.example ~/.config/engramr/vaults.yaml
```

2. Edit `~/.config/engramr/vaults.yaml`:

```yaml
vaults:
  - name: main
    path: ~/MainVault
    default: true
  - name: collab-lab
    path: ~/CollabVault
    port: 27125
```

3. Start per-vault daemons:

```bash
bash ops/scripts/daemon-all.sh
```

For federation, trust model, and cross-lab operations, see [Inter-Lab Collaboration](inter-lab.md).

---

## Domain Profiles

Domain-specific behavior is configured via profile directories in `_code/profiles/`.
See [Configuration](configuration.md#domain-profiles) for the full profile reference.

---

## Verification

Open the vault with `claude`. The session orient hook fires automatically and
prints vault state. Run `/health` to check vault integrity -- a fresh vault
should report all green.

## Troubleshooting

**Daemon won't start** -- Check that tmux is installed (`brew install tmux` on macOS).

**Hooks don't fire** -- Verify `.claude/hooks/` exists and scripts are executable (`chmod +x .claude/hooks/*.sh`).

**Something went wrong during setup** -- Tell Claude what happened. It can diagnose and fix most setup issues through conversation.

---

## See Also

- [Getting Started](getting-started.md) -- first session walkthrough
- [Configuration](configuration.md) -- ops/config.yaml and domain profiles
- [Administration](administration.md) -- daemon, hooks, decision engine
- [Inter-Lab Collaboration](inter-lab.md) -- federation and multi-vault operations
