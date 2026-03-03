---
name: federation-sync
description: Synchronize claims and hypotheses with peer vaults via shared exchange directory
context: fork
allowed-tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Write
---

# /federation-sync -- Cross-Vault Federation Agent

Synchronize claims and hypotheses between peer vaults using a shared
exchange directory. Respects trust levels and quarantine policies.

## Architecture

Implements file-based federation exchange as described in ops/federation.yaml.
No server infrastructure required -- peers share a directory (git repo,
shared drive, or mounted volume).

## Vault paths

- Config: `ops/federation.yaml`
- Claims: `notes/` (export source), imported claims also go here
- Hypotheses: `_research/hypotheses/` (export + import)
- Exchange dir: configured in `ops/federation.yaml` under `sync.exchange_dir`

## Code

- `_code/src/engram_r/claim_exchange.py` -- `export_claims()`, `import_claims()`
- `_code/src/engram_r/hypothesis_exchange.py` -- `export_hypotheses()`, `import_hypotheses()`
- `_code/src/engram_r/federation_config.py` -- `load_federation_config()`

## Exchange directory structure

```
exchange_dir/
  {vault_id}/
    claims.yaml          -- exported claims from this vault
    hypotheses.yaml      -- exported hypotheses from this vault
    manifest.yaml        -- vault identity + export timestamp
```

## Workflow

1. Read `ops/federation.yaml` to get federation config.
2. If federation is disabled, exit with message.
3. Validate exchange directory exists and is writable.

### Export phase
4. Export claims from `notes/` according to export policy:
   - Filter by confidence levels in `export.claims.filter_confidence`
   - Limit to `export.claims.max_per_sync`
   - Strip wiki-links (not portable across vaults)
5. Export hypotheses from `_research/hypotheses/` according to export policy:
   - Filter by `export.hypotheses.min_elo`
   - Limit to `export.hypotheses.max_per_sync`
6. Write exports to `exchange_dir/{vault_id}/claims.yaml` and `hypotheses.yaml`.
7. Write a `manifest.yaml` with vault identity and export timestamp.

### Import phase
8. List peer directories in the exchange dir (any dir that is not this vault's).
9. For each peer:
   a. Read their `manifest.yaml` to identify the peer.
   b. Check trust level in `federation.yaml` peers config.
   c. If untrusted (and default trust is untrusted), skip with log message.
   d. If verified or full:
      - Import claims: `import_claims()` with quarantine based on trust level.
      - Import hypotheses: `import_hypotheses()` with federated Elo fields.
10. Write sync summary to `ops/daemon-inbox.md`:
    - Claims exported / imported per peer
    - Hypotheses exported / imported per peer
    - Peers skipped (untrusted)

## Trust levels

| Level | Claims | Hypotheses | Quarantine | Federated Tournament |
|-------|--------|------------|------------|---------------------|
| full | Accept | Accept | No | Yes |
| verified | Accept | Accept | Yes | Yes |
| untrusted | Reject | Reject | N/A | No |

## Safety rules

- NEVER import from peers whose trust level blocks import.
- ALWAYS quarantine verified-peer imports (unless quarantine is disabled globally).
- NEVER overwrite existing notes during import (use overwrite=False).
- NEVER export private/quarantined notes.
- Log every import/export action for provenance.

## Federated Elo

Imported hypotheses get:
- `elo_federated: 1200` (starting federated rating)
- `elo_source: {original_elo}` (informational, from source vault)
- `matches_federated: 0`
- `matches_source: {original_matches}`

The `/tournament --federated` mode updates `elo_federated` (not `elo`),
keeping local and federated rankings separate.

## Daemon integration

The daemon scheduler checks `ops/federation.yaml` for:
- `enabled: true` -- master switch
- `sync.exchange_dir` -- must be non-empty

When both conditions are met, the scheduler includes federation-sync
in the P3.5 priority tier (after background tasks, before idle).
