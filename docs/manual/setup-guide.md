---
description: "Installation, environment configuration, dependency setup, and vault initialization"
type: manual
created: 2026-02-21
---

# Setup Guide

Step-by-step instructions for setting up a new EngramR vault.

---

## Prerequisites

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/) installed
- **Git** installed and configured
- **Claude Code** CLI installed
- (Optional) **[Obsidian](https://obsidian.md/)** for vault browsing and graph visualization
- (Optional) **R 4.x+** for statistical plots
- (Optional) **tmux** for running the research daemon

## Quick Start

```bash
# From the EngramR repo:
cd _code
uv run python scripts/init_vault.py ~/MyResearchVault --name "My Lab"
```

This creates a fully structured vault at `~/MyResearchVault` with all templates, skills, hooks, config files, and the Python/R code library.

## Step-by-Step

### 1. Scaffold the vault

```bash
# Full setup (all skills):
uv run python scripts/init_vault.py /path/to/vault --name "Lab Name"

# Starter mode (core skills only, easier onboarding):
uv run python scripts/init_vault.py /path/to/vault --name "Lab Name" --starter

# Skip git init:
uv run python scripts/init_vault.py /path/to/vault --no-git
```

The scaffolder creates:

| Directory | Purpose |
|-----------|---------|
| `_code/` | Python + R library (note builder, validators, Elo, plotting) |
| `_code/templates/` | Note templates (claim, hypothesis, literature, etc.) |
| `.claude/skills/` | Claude Code skills for the co-scientist pipeline |
| `.claude/hooks/` | Automation hooks (auto-commit, validation, session capture) |
| `ops/` | Configuration, scripts, daemon runner |
| `self/` | Agent identity and methodology |
| `_code/styles/` | Plot theme and palette configuration |
| `docs/` | Documentation |
| `notes/` | Empty -- your knowledge graph grows here |
| `inbox/` | Empty -- drop sources here for processing |
| `_research/` | Empty -- hypotheses, tournaments, etc. created by skills |

### 2. Configure environment variables

```bash
cd /path/to/vault
cp .env.example .env
```

Edit `.env` with API keys for your domain. Which keys you need depends on your configured profile -- see [_code/README.md](../../_code/README.md#environment-variables) for the full environment variables table.

> **Domain profiles:** After setup, select a domain profile in `ops/config.yaml` under `domain.name` to enable domain-specific search backends, data layers, and confounders. See `_code/profiles/` for available profiles.

### 3. Install Python dependencies

```bash
cd /path/to/vault/_code
uv sync
```

Verify the installation:

```bash
uv run pytest tests/ -v --cov=engram_r
```

All tests should pass with high coverage.

### 4. (Optional) Open as an Obsidian vault

If you use Obsidian for vault browsing:

1. Open Obsidian
2. "Open folder as vault" > select your vault path
3. (Optional) Install the **Local REST API** community plugin for MCP integration
4. (Recommended) Install **Dataview** for dynamic queries

### 5. Start Claude Code

```bash
cd /path/to/vault
claude
```

On first session, run two setup skills in sequence:

```
/onboard
/init
```

`/onboard` bootstraps your lab integration: scans for projects, creates data inventory, links hypotheses to goals. `/init` then seeds your knowledge graph with orientation claims, confounders, and assumption inversions using the artifacts /onboard created.

### 6. (Optional) Start the research daemon

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

## Starter Skills

If you used `--starter`, these core skills are installed:

| Skill | What it does |
|-------|-------------|
| `/onboard` | Bootstrap lab integration |
| `/init` | Seed foundational knowledge claims |
| `/reduce` | Extract claims from inbox sources |
| `/reflect` | Find connections between notes |
| `/reweave` | Update old notes with new connections |
| `/verify` | Quality-check notes (description + schema + links) |
| `/validate` | Schema validation for frontmatter |
| `/seed` | Queue a source file for processing with duplicate detection |
| `/next` | Get the most valuable next action |
| `/stats` | Show vault statistics |
| `/graph` | Interactive graph analysis |
| `/tasks` | View and manage the task stack |

The full skill set adds the remaining skills for the co-scientist pipeline (hypothesis generation, tournaments, literature search, experimental design, etc.). Re-run the scaffolder without `--starter` to add them later.

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

### 7. MCP Servers

EngramR uses [MCP servers](https://modelcontextprotocol.io/) to connect Claude Code
to external services. Servers are configured in `.mcp.json` at the project root.

### Obsidian (optional)

The mcp-obsidian server gives Claude programmatic access to vault content --
reading files, writing notes, searching, and listing directories -- through the
Obsidian Local REST API. This is **not required** for normal operation (Claude
Code reads/writes files directly); it is useful for Obsidian-specific features
like search and graph queries.

Add to `.mcp.json` (or verify it was created by the scaffolder):

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

After setup, verify everything works. See [_code/README.md](../../_code/README.md) for the full set of test, lint, and format commands.

```bash
cd _code && uv run pytest tests/ -v   # tests pass
```

Start Claude Code (`claude`) -- the session orient hook should print vault state. Run `/health` to check vault integrity. A fresh vault should report all green.

## Troubleshooting

**Tests fail with import errors** -- Run `uv sync` in the `_code/` directory to install dependencies.

**Daemon won't start** -- Check that tmux is installed (`brew install tmux` on macOS).

**Hooks don't fire** -- Verify `.claude/hooks/` exists and scripts are executable (`chmod +x .claude/hooks/*.sh`).

**"Cannot find source vault"** -- Run init_vault.py from within the EngramR repo, or pass `--source /path/to/repo`.
