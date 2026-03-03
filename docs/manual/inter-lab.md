---
description: "Multi-lab wiring, vault registry, federation sync, trust model, and cross-lab synergy edges"
type: manual
created: 2026-02-21
---

# Multi-Lab Integration Guide

How to manage multiple research labs within a single vault and federate across independent vault instances.

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Lab and Project Structure](#lab-and-project-structure)
4. [Multi-Vault Operations](#multi-vault-operations)
5. [Federation](#federation)
6. [Guardrails and Safety](#guardrails-and-safety)
7. [API Reference](#api-reference)
8. [Common Pitfalls](#common-pitfalls)

---

## Overview

The multi-lab system solves three problems:

1. **Internal wiring** -- labs need entity nodes, linked projects, navigable graph edges, and shared palettes.
2. **Multi-vault tooling** -- multiple vault instances need a registry, portable daemon, and decoupled hooks.
3. **Federation** -- independent vaults exchange claims and hypotheses with trust-based import policies and separate Elo tracks.

### Architecture Principles

- **File-based exchange** -- no server infrastructure. Peers share a directory (git repo, shared drive, or mounted volume).
- **Separate Elo tracks** -- local and federated rankings never interfere.
- **Quarantine by default** -- imported content requires human review unless the source peer has `full` trust.
- **Wiki-links are vault-internal** -- exports strip all `[[wiki links]]` to plain text. Imports create local links as appropriate.

---

## Getting Started

`/onboard` is the single entry point for new labs and users. It handles both vault scaffolding (creating missing directories and config) and content population (scanning lab data, interviewing the user, creating project notes).

```
/onboard                          # interactive -- asks for lab path
/onboard ~/projects/LabName/      # full onboard for a specific lab
/onboard --update                 # re-scan all registered labs for new projects
/onboard ~/projects/LabName/New/  # add one project to an existing lab
```

**What `/onboard` creates:**

| Artifact | Description |
|----------|-------------|
| Lab entity node | `projects/{lab}/_index.md` with `type: lab` schema |
| Project notes | `projects/{lab}/{tag}.md` per discovered project |
| Data inventory entries | Rows in `_research/data-inventory.md` |
| Research goal links | Wires projects to relevant goals and hypotheses |
| Dev symlinks | `_dev/{tag}` -> project path (for Obsidian transclusion) |
| Vault structure | Creates missing directories if running against a bare vault |

After onboarding, verify with:
- `/health` -- check schema compliance and link health
- `/stats` -- confirm project and lab counts

---

## Lab and Project Structure

### Lab Entity Nodes

Each lab gets an `_index.md` under `projects/{lab}/` with `type: lab` frontmatter.

```yaml
---
type: lab
lab_slug: "lab-name"
pi: "PI Name"
institution: "University"
hpc_cluster: "cluster-name"
hpc_scheduler: "slurm"
research_focus: "Brief description"
created: 2026-01-15
updated: 2026-02-23
tags: [lab]
---

## Projects
## Datasets
## Research Focus
## HPC Environment
```

**Required fields:** `lab_slug`, `pi`, `created`, `updated`. Validated by `schema_validator.validate_note()`.

**Code:** `note_builder.build_lab_note()` produces lab notes from keyword arguments.

### Project Registration

Each tracked dataset gets a project note under `projects/{lab}/`.

**Required fields:** `title`, `project_tag`, `lab`, `status`, `project_path`, `created`, `updated`.

**Status values:** `active`, `maintenance`, `archived`.

**Optional fields:** `language`, `hpc_path`, `scheduler`, `linked_goals`, `linked_hypotheses`, `linked_experiments`, `has_claude_md`, `has_git`, `has_tests`.

**Code:** `note_builder.build_project_note()` produces project notes.

### Cross-Lab Synergy Edges

When labs share datasets, methodologies, or platforms, express synergies as wiki-links between lab nodes, project nodes, and hypothesis nodes. Create dedicated claim notes for each synergy -- prose links in inventory tables are not graph edges.

**Example:** If Lab A has longitudinal data and a hypothesis involves temporal patterns, create a claim note linking the project to the hypothesis and both lab nodes.

### Externalized Palettes

`_code/styles/palettes.yaml` is the single source of truth for all color palettes. Both Python and R load it at import time with hardcoded fallbacks.

```yaml
semantic:
  sex:
    Male: "#377EB8"
    Female: "#E41A1C"
  dx:
    "P-": "#4DAF4A"
    "P+": "#E41A1C"
  # ... binary, direction, sig palettes

diverging: "RdBu_r"
sequential: "Blues"

labs:
  lab-name: ["#hex1", "#hex2", ...]   # add new labs here
```

**Adding a new lab palette:** Add a key under `labs:` with a list of hex colors. Both languages pick it up automatically.

**Python:**
```python
from engram_r.plot_theme import get_lab_palette
colors = get_lab_palette("lab-name")        # full palette
colors = get_lab_palette("lab-name", n=4)   # first 4
```

**R:**
```r
source("_code/R/palettes.R")
lab_palette("lab-name")
scale_color_lab("lab-name")   # ggplot2 scale
```

---

## Multi-Vault Operations

### Vault Registry

A YAML registry at `~/.config/engramr/vaults.yaml` maps vault names to paths, API URLs, and keys.

```yaml
vaults:
  - name: main
    path: ~/MainVault
    api_url: https://127.0.0.1:27124
    api_key: ""                          # falls back to OBSIDIAN_API_KEY env var
    port: 27124
    default: true
  - name: collab
    path: ~/CollabVault
    port: 27125
```

**Python API (`vault_registry.py`):**

```python
from engram_r.vault_registry import (
    VaultConfig,        # frozen dataclass
    load_registry,      # -> list[VaultConfig]
    get_vault,          # (name) -> VaultConfig
    get_default_vault,  # -> VaultConfig | None
    get_vault_path,     # (name=None) -> Path | None
)
```

**Resolution priority for `get_vault_path()`:** named vault > default vault > `VAULT_PATH` env var > `None`.

**Backward compatibility:** If no registry file exists, all functions fall back gracefully. Existing `from_env()` behavior is unchanged.

**Obsidian Client integration:**
```python
client = ObsidianClient.from_vault("main")   # uses registry
client = ObsidianClient.from_env()            # existing behavior
```

### Multi-Vault Daemon

The daemon accepts `--vault <name>` to resolve paths via the registry.

```bash
bash ops/scripts/daemon.sh                    # detect from CWD
bash ops/scripts/daemon.sh --vault main       # named vault
bash ops/scripts/daemon.sh --dry-run          # print what would run
bash ops/scripts/daemon.sh --once             # one task, exit
```

### Hook Decoupling

Hooks find the vault root via `.arscontexta` directory marker, falling back to git root. This allows vaults that are not at the git repository root.

- `ops/scripts/lib/vault-env.sh` -- shared `find_vault_root()` sourced by all shell hooks.
- Python hooks use the same walk-up logic with git fallback.

### Self-Documenting Config

`ops/config.yaml` and `ops/daemon-config.yaml` contain extensive inline comments. `ops/config-reference.yaml` documents every valid value for all dimensions, feature flags, processing settings, provenance, research tools, and daemon tuning.

---

## Federation

### How It Works

Independent vaults exchange claims and hypotheses through a shared filesystem directory. No server process is required.

```
exchange_dir/
  {vault_id}/
    claims.yaml
    hypotheses.yaml
    manifest.yaml
  {other_vault_id}/
    claims.yaml
    hypotheses.yaml
    manifest.yaml
```

The exchange directory can be a git repo, NFS mount, shared drive, or any synced folder.

### Configuration (`ops/federation.yaml`)

```yaml
identity:
  vault_id: ""              # unique ID (e.g., "lab-alpha")
  display_name: ""
  institution: ""

enabled: false              # master switch

sync:
  frequency_hours: 24
  exchange_dir: ""          # path to shared exchange directory

export:
  claims:
    enabled: true
    filter_confidence: [established, supported]
    max_per_sync: 50
  hypotheses:
    enabled: true
    min_elo: 1250
    max_per_sync: 20

import:
  default_trust: untrusted
  quarantine:
    enabled: true
    auto_accept_after_days: 0   # 0 = manual review required
  hypotheses:
    allow_federated_tournament: true
    starting_elo: 1200

peers: {}
#  peer-slug:
#    vault_id: "peer-id"
#    display_name: "Partner Lab"
#    trust: full               # full | verified | untrusted
```

If `ops/federation.yaml` is missing, federation is simply inactive. No error is raised.

### Trust Model

| Level | Claims | Hypotheses | Quarantine | Federated Tournament |
|-------|--------|------------|------------|---------------------|
| `full` | Accept | Accept | No | Yes |
| `verified` | Accept | Accept | Yes | Yes |
| `untrusted` | Reject | Reject | N/A | No |

**Resolution:** Named peer in `peers:` section uses configured trust. Unknown peers use `default_trust` (default: `untrusted`).

**Quarantine behavior:** `full` trust skips quarantine. `verified` trust adds `quarantine: true` to frontmatter -- human must review before content enters the knowledge graph. `untrusted` peers are rejected entirely.

### Claim Exchange

**Export:** Filters claims by confidence level and caps count. Strips all wiki-links.

```python
from engram_r.claim_exchange import export_claims, export_to_yaml, import_claims

claims = export_claims(vault_path, source_vault="main",
                       filter_confidence=["established", "supported"],
                       max_count=50)
yaml_str = export_to_yaml(claims)
```

**Import:** Writes claims as notes with `source_vault`, `quarantine`, and `imported` frontmatter fields.

```python
created = import_claims(vault_path, claims, quarantine=True, overwrite=False)
```

### Hypothesis Exchange

**Export:** Filters by minimum Elo and caps count. Extracts Statement, Mechanism, Testable Predictions, Assumptions, and Limitations sections. Strips wiki-links.

```python
from engram_r.hypothesis_exchange import export_hypotheses, import_hypotheses

hyps = export_hypotheses(vault_path, source_vault="main", min_elo=1250, max_count=20)
```

**Import:** Creates `type: foreign-hypothesis` notes with separate federated Elo fields:

```yaml
---
type: foreign-hypothesis
elo_federated: 1200         # starting federated rating
elo_source: 1350            # original Elo from source vault (read-only)
matches_federated: 0
matches_source: 8           # informational
source_vault: partner-lab
imported: "2026-02-23T12:00:00+00:00"
---
```

### Federated Elo System

Each hypothesis carries two independent Elo ratings:

| Field | Updated By | Purpose |
|-------|-----------|---------|
| `elo` | Local `/tournament` | Ranking within this vault |
| `elo_federated` | `/tournament --federated` | Ranking across vaults |

When a local hypothesis first enters a federated match, `elo_federated` initializes to its current `elo`. Foreign hypotheses start at 1200 (configurable). The two tracks never interfere -- a hypothesis can rank #1 locally and #5 in federated competition.

### Sync Workflow

The `/federation-sync` skill (also triggered by daemon at priority P3.5) executes:

1. Read `ops/federation.yaml` -- exit if disabled.
2. Validate exchange directory is writable.
3. **Export:** Filter and write claims/hypotheses to `exchange_dir/{vault_id}/`.
4. **Import:** Read peer directories, check trust, import per trust rules.
5. **Log:** Write sync summary to `ops/daemon-inbox.md`.

**Daemon priority cascade:**
```
P1:   Research Cycle
P2:   Knowledge Maintenance
P2.5: Inbox Processing
P3:   Background Tasks
P3.5: Federation Sync
P4:   Idle
```

---

## Guardrails and Safety

### Export Safety

- Never export quarantined notes (`quarantine: true` stays local).
- Never export notes outside configured `notes_dir` and `hyp_dir`.
- Strip all wiki-links -- they cannot resolve in another vault.
- Respect `max_per_sync` caps.

### Import Safety

- Never import from untrusted peers.
- Always quarantine verified-peer imports (unless quarantine is globally disabled or trust is `full`).
- Never overwrite existing notes (`overwrite=False` default).
- Log every import and export action for provenance.

### Filesystem Safety

- Safe filenames via `_safe_filename()` -- replaces `/\:*?"<>|.+[](){}^` with hyphens.
- Directory creation with `mkdir(parents=True, exist_ok=True)`.
- `_dev/` is in `.gitignore` -- symlink targets are machine-local.

### Data Integrity

- Every imported note includes `source_vault:` provenance.
- Every exported item includes `exported:` ISO timestamp.
- Round-trip preservation: export -> YAML -> load -> import preserves all content (verified by integration tests).

---

## API Reference

### `note_builder`
| Function | Purpose |
|----------|---------|
| `build_lab_note(**kwargs)` | Produce lab entity note markdown |
| `build_project_note(**kwargs)` | Produce project note markdown |

### `vault_registry`
| Function | Purpose |
|----------|---------|
| `load_registry()` | Parse `~/.config/engramr/vaults.yaml` |
| `get_vault(name)` | Look up vault by name |
| `get_default_vault()` | Get the default vault |
| `get_vault_path(name=None)` | Resolve vault path (registry > env > None) |

### `claim_exchange`
| Function | Purpose |
|----------|---------|
| `export_claim(markdown, title, source_vault)` | Single claim export |
| `export_claims(vault_path, source_vault, **filters)` | Bulk export with filters |
| `export_to_yaml(claims)` | Serialize to YAML |
| `load_exported_claims(yaml_str)` | Deserialize from YAML |
| `import_claims(vault_path, claims, quarantine, overwrite)` | Write claims as notes |

### `hypothesis_exchange`
| Function | Purpose |
|----------|---------|
| `export_hypothesis(markdown, id, source_vault)` | Single hypothesis export |
| `export_hypotheses(vault_path, source_vault, **filters)` | Bulk export with Elo filter |
| `import_hypotheses(vault_path, hypotheses, overwrite)` | Write as foreign-hypothesis notes |

### `federation_config`
| Function | Purpose |
|----------|---------|
| `load_federation_config(path)` | Parse `ops/federation.yaml` (returns defaults if missing) |
| `config.get_peer_trust(peer)` | Resolve trust level for a peer |
| `config.can_import_from(peer)` | Check if import is allowed |
| `config.should_quarantine(peer)` | Check if quarantine applies |

### `schema_validator`
| Function | Purpose |
|----------|---------|
| `validate_note(content, note_type)` | Validate `lab` and `project` schemas |

---

## Common Pitfalls

**Federation enabled but exchange_dir empty.** Sync will not fire. Both `enabled: true` and a valid `exchange_dir` path are required.

**Unknown peers default to untrusted.** If a new vault appears in the exchange directory but is not listed in `peers:`, their content is rejected. Add them to `peers:` with at least `verified` trust.

**Wiki-links in exported content.** If you see `[[brackets]]` in exchange YAML files, something bypassed the export pipeline. Always use the export functions -- never manually copy notes to the exchange directory.

**Quarantined imports invisible to the graph.** Quarantined notes exist as files but are excluded from `/reflect`, `/reweave`, and topic map updates until a human removes the `quarantine: true` flag.

**Federated Elo starting bias.** Foreign hypotheses start at 1200 regardless of their source Elo. A hypothesis rated 1400 in another vault starts fresh in yours. This is intentional -- trust is earned through local competition.

**Palette not loading.** Both Python and R fall back to hardcoded defaults if `_code/styles/palettes.yaml` is missing or malformed. Check YAML syntax if a newly added lab palette doesn't appear.

**Stale dev symlinks.** After renaming or moving project paths, run `/onboard --update` to refresh symlinks. Stale symlinks (pointing to moved targets) produce warnings but are not auto-deleted.
