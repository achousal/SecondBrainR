---
description: "Optional integrations and technical reference -- Obsidian, Slack, MCP servers, daemon, multi-vault"
type: manual
created: 2026-02-21
---

# Setup Guide

This is a technical reference for optional integrations and advanced configuration. If you are just starting out, you do not need this page -- clone the repo, open it with Claude Code, and follow the prompts.

Come back here when you want to connect Obsidian, Slack, or MCP servers, run the research daemon, or manage multiple vaults.

---

## What Claude sets up automatically

When you open the vault for the first time and run `/onboard` followed by `/init`, Claude handles:

- Python dependency installation
- Vault structure (notes/, inbox/, ops/, self/, _research/, projects/)
- Configuration files (ops/config.yaml, ops/derivation.md)
- Note templates and skill hooks
- Initial knowledge graph seeding

---

## Optional: Obsidian

If you use Obsidian for vault browsing:

1. Open Obsidian
2. "Open folder as vault" > select your vault path
3. (Optional) Install the **Local REST API** community plugin for MCP integration
4. (Recommended) Install **Dataview** for dynamic queries

## Optional: Research daemon

The daemon runs autonomous synthesis and maintenance in the background:

```bash
tmux new -s daemon 'bash ops/scripts/daemon.sh'
```

Or for multi-vault setups:

```bash
bash ops/scripts/daemon-all.sh
```

## Configuration

### Knowledge architecture (`ops/config.yaml`)

Key dimensions to review:

| Dimension | Default | When to change |
|-----------|---------|---------------|
| `granularity` | atomic | Almost never -- atomic claims are the foundation |
| `organization` | flat | Switch to `hierarchical` if you prefer folder-based navigation |
| `processing` | heavy | Switch to `light` if you only need note-taking, not co-scientist |
| `automation` | full | Switch to `partial` (no daemon) or `manual` for full control |

See `ops/config-reference.yaml` for all valid values with descriptions.

### Daemon behavior (`ops/daemon-config.yaml`)

Key settings to tune:

| Setting | Default | What it controls |
|---------|---------|-----------------|
| `goals_priority` | `[]` | Which research goals get priority resources |
| `models.tournament_primary` | `opus` | Model quality for primary goal tournaments |
| `cooldowns_minutes.idle` | `30` | How often daemon polls when idle |
| `thresholds.orphan_notes` | `10` | Orphan count that triggers /reflect |

## Multi-Vault Setup

To manage multiple vaults (e.g., one per lab):

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

## Optional: MCP Servers

EngramR uses [MCP servers](https://modelcontextprotocol.io/) to connect Claude Code to external services. Servers are configured in `.mcp.json` at the project root.

### Obsidian MCP

The mcp-obsidian server gives Claude programmatic access to vault content through the Obsidian Local REST API -- useful for Obsidian-specific search and graph queries. Not required for normal operation; Claude Code reads and writes files directly.

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

The API key is the same one from the Local REST API plugin (step 4). The default
host and port match the plugin's defaults -- only change them if you customized
the plugin settings.

To verify: restart Claude Code and check that `mcp-obsidian` appears in the MCP
server list. You can test with a vault search or file read.

### Slack (optional)

Connect Slack so team members can interact with the vault from their workflow.
EngramR uses Slack in two ways: the **MCP server** lets Claude read and write
messages directly, and the **notification system** sends automated alerts for
session events and daemon activity.

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

---

## Verification

Open the vault with `claude`. The session orient hook fires automatically and prints vault state. Run `/health` to check vault integrity -- a fresh vault should report all green.

## Troubleshooting

**Daemon won't start** -- Check that tmux is installed (`brew install tmux` on macOS).

**Hooks don't fire** -- Verify `.claude/hooks/` exists and scripts are executable (`chmod +x .claude/hooks/*.sh`).

**Something went wrong during setup** -- Tell Claude what happened. It can diagnose and fix most setup issues through conversation.
