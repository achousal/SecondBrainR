---
name: profile
description: "Create, list, show, and activate domain profiles. Conversational interview generates a complete profile directory for any research domain. Triggers on /profile, /profile --list, /profile --show {name}, /profile --activate {name}."
version: "1.1"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: main
model: sonnet
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - WebSearch
  - Agent
  - AskUserQuestion
argument-hint: "[--list | --show {name} | --activate {name}]"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

You are the /profile orchestrator. You run in main context -- natural conversation turns. Sub-skills handle computation in fork context via the Agent tool (subagent_type: general-purpose); you handle all user interaction.

**Architecture:** This skill coordinates four fork sub-skills via the Agent tool:
- `profile-suggest` -- web search for confounder/tool suggestions (haiku)
- `profile-generate` -- write all profile YAML files (sonnet)
- `profile-validate` -- run load_profile() validation (haiku)
- `profile-query` -- handle --list and --show modes (haiku)

Detailed schemas and prompts live in `reference/` files that sub-skill agents Read on demand.

---

## Phase 0: MODE ROUTING

### Step 0: Detect active profile

Before routing, check if a profile is already active:
```bash
cd "$(pwd)" && uv run --directory _code python -c "
import sys; sys.path.insert(0, 'src')
from engram_r.domain_profile import get_active_profile
p = get_active_profile('../ops/config.yaml')
if p:
    print(f'ACTIVE:{p.name}:{p.description}')
else:
    print('NONE')
"
```

Store the result as `active_profile_name` (or None).

### Parse arguments

| Input | Mode |
|-------|------|
| (empty) | Active-profile gate (see below), then interview |
| `--list` | List available profiles |
| `--show {name}` | Display profile summary |
| `--activate {name}` | Activate with switch/reload detection |

---

### Mode: (empty) -- Active-profile gate

If `active_profile_name` is not None:

Present to user:
```
Profile '{active_profile_name}' is currently active.

What would you like to do?
1. Create a new profile (starts the interview)
2. Show the current profile (/profile --show {active_profile_name})
3. List all available profiles (/profile --list)
```

Use AskUserQuestion with these three options. Route accordingly:
- Option 1: proceed to Phase 1 (interview)
- Option 2: execute --show mode with active_profile_name
- Option 3: execute --list mode

If `active_profile_name` is None: proceed directly to Phase 1 (interview).

---

### Mode: --list

Launch the `profile-query` sub-skill:

```
Read .claude/skills/profile/sub-skills/profile-query.md
```

Then spawn an Agent (subagent_type: general-purpose, model: haiku) with prompt:
```
Read and execute .claude/skills/profile/sub-skills/profile-query.md with arguments: --list
```

Present the returned list to the user. Done.

---

### Mode: --show {name}

Launch the `profile-query` sub-skill:

Spawn an Agent (subagent_type: general-purpose, model: haiku) with prompt:
```
Read and execute .claude/skills/profile/sub-skills/profile-query.md with arguments: --show {name}
```

Present the returned profile summary to the user. Done.

---

### Mode: --activate {name}

1. Verify the profile exists:
```bash
cd "$(pwd)" && uv run --directory _code python -c "
import sys; sys.path.insert(0, 'src')
from engram_r.domain_profile import load_profile
p = load_profile('{name}')
print(f'Found: {p.name} -- {p.description}')
"
```

2. **Edge case: already active.** If `active_profile_name == {name}`:
   - Tell user: "Profile '{name}' is already active."
   - Ask: "Reload it? This re-applies config overrides and palette merges. (yes/no)"
   - If no: done. If yes: proceed to step 3.

3. **Edge case: switching profiles.** If `active_profile_name` is not None and `active_profile_name != {name}`:
   - Tell user: "Switching from '{active_profile_name}' to '{name}'."
   - Proceed to step 4 (no blocking confirmation -- switching is normal).

4. Apply:
```bash
cd "$(pwd)" && uv run --directory _code python -c "
import sys; sys.path.insert(0, 'src')
from engram_r.domain_profile import load_profile, apply_profile_config, merge_profile_palettes
p = load_profile('{name}')
apply_profile_config(p, '../ops/config.yaml')
merge_profile_palettes(p, 'styles/palettes.yaml')
print('Profile activated.')
print(f'  domain.name = {p.name}')
print(f'  domain.profile = {p.profile_dir}')
"
```

5. Present confirmation. Done.

---

## Phase 1: INTERVIEW (6 turns)

Read the interview prompts reference:
```
Read .claude/skills/profile/reference/interview-prompts.md
```

Read the domain examples for context:
```
Read .claude/skills/profile/reference/domain-examples.md
```

### State tracking

Maintain these variables across turns (in conversation memory):
- `profile_name`: string
- `profile_description`: string
- `agent_purpose`: string
- `focus_areas`: list[str]
- `data_layers`: list[str]
- `file_extensions`: dict[str, str]
- `tool_references`: dict[str, str]
- `confounders`: dict[str, list[str]]
- `biological_confounders`: list[str]
- `data_reality_signals`: dict
- `pii_patterns`: list[str]
- `literature_primary`: str
- `literature_fallback`: str
- `literature_sources`: list[str]
- `env_vars_required`: dict[str, str]
- `env_vars_optional`: dict[str, str]
- `lab_palette`: list[str]
- `semantic_palettes`: dict

---

### Turn 1: Domain Identity

Use the prompt from reference/interview-prompts.md Turn 1.

After user responds:
1. Validate name is machine-safe (lowercase, hyphens, alphanumeric)
2. Check for name collision:
```bash
cd "$(pwd)" && uv run --directory _code python -c "
import sys; sys.path.insert(0, 'src')
from engram_r.domain_profile import discover_profiles
profiles = discover_profiles()
print(','.join(profiles) if profiles else 'NONE')
"
```
3. If collision:
   - If colliding name == active_profile_name: ask "A profile named '{name}' already exists and is currently active. Overwrite it, or choose a different name?"
   - If colliding name != active_profile_name: ask "A profile named '{name}' already exists. Overwrite it, or choose a different name?"
   - On "overwrite": proceed (existing profile directory will be overwritten in Phase 2)
   - On "different name": ask for a new name and re-validate
4. Store: profile_name, profile_description, agent_purpose, focus_areas

---

### Turn 2: Data Layers + Heuristics

Use the prompt from reference/interview-prompts.md Turn 2. Adapt examples based on the domain from Turn 1.

After user responds:
1. Store: data_layers, file_extensions, tool_references
2. Fire `profile-suggest` fork in background:

Spawn an Agent (subagent_type: general-purpose, model: haiku, run_in_background: true) with prompt:
```
Read and execute .claude/skills/profile/sub-skills/profile-suggest.md with arguments:
domain_name={profile_name} data_layers={comma-separated layers}
```

Proceed to Turn 3 (the background agent will provide suggestions).

---

### Turn 3: Technical Confounders

Wait for profile-suggest results if not yet ready. Present the web-searched suggestions using the prompt from reference/interview-prompts.md Turn 3.

After user responds:
1. Store: confounders (per layer), biological_confounders, data_reality_signals

---

### Turn 4: PII Patterns

Use the prompt from reference/interview-prompts.md Turn 4.

After user responds:
1. Convert user-provided column names into regex patterns (add word boundaries)
2. Store: pii_patterns, update data_reality_signals with species column if provided

---

### Turn 5: Literature + Palettes

Read the literature backends reference:
```
Read .claude/skills/profile/reference/literature-backends.md
```

Use the prompt from reference/interview-prompts.md Turn 5. Use the domain recommendations table to suggest appropriate backends.

After user responds:
1. Determine required/optional env vars based on selected backends:
   - pubmed selected -> require NCBI_EMAIL, optional NCBI_API_KEY
   - openalex selected -> require OPENALEX_API_KEY
   - semantic_scholar selected -> optional S2_API_KEY
   - enrichment enabled -> require LITERATURE_ENRICHMENT_EMAIL
2. Store: literature_primary, literature_fallback, literature_sources, env_vars_required, env_vars_optional, lab_palette, semantic_palettes

---

### Turn 6: Review + Confirm

Use the prompt from reference/interview-prompts.md Turn 6 to present the full summary.

On "yes" or approval: proceed to Phase 2.
On "edit": ask which section, loop back to that turn.
On "cancel": abort with message "Profile creation cancelled. No files were written."

---

## Phase 2: GENERATION

### Step 1: Generate profile files

Spawn an Agent (subagent_type: general-purpose, model: sonnet) with prompt:
```
Read and execute .claude/skills/profile/sub-skills/profile-generate.md with the following data:
name={profile_name}
description={profile_description}
purpose={agent_purpose}
focus_areas={focus_areas}
data_layers={data_layers}
file_extensions={file_extensions}
tool_references={tool_references}
confounders={confounders}
biological_confounders={biological_confounders}
data_reality_signals={data_reality_signals}
pii_patterns={pii_patterns}
literature_primary={literature_primary}
literature_fallback={literature_fallback}
literature_sources={literature_sources}
env_vars_required={env_vars_required}
env_vars_optional={env_vars_optional}
lab_palette={lab_palette}
semantic_palettes={semantic_palettes}
```

### Step 2: Validate

Spawn an Agent (subagent_type: general-purpose, model: haiku) with prompt:
```
Read and execute .claude/skills/profile/sub-skills/profile-validate.md with arguments: {profile_name}
```

If validation fails: report the error and attempt to fix. Re-run validation.

### Step 3: Activate (optional)

Ask the user: "Activate this profile now? This updates ops/config.yaml and merges palettes. (yes/no)"

If yes:
```bash
cd "$(pwd)" && uv run --directory _code python -c "
import sys; sys.path.insert(0, 'src')
from engram_r.domain_profile import load_profile, apply_profile_config, merge_profile_palettes
p = load_profile('{profile_name}')
apply_profile_config(p, '../ops/config.yaml')
merge_profile_palettes(p, 'styles/palettes.yaml')
print('Profile activated.')
"
```

### Step 4: Present summary

```
Profile '{profile_name}' created successfully.

Location: _code/profiles/{profile_name}/
Files: profile.yaml, confounders.yaml, heuristics.yaml, pii_patterns.yaml, palettes.yaml
Status: {activated/not activated}

Next steps:
- /profile --show {profile_name}  -- view the profile
- /profile --activate {profile_name}  -- activate later (if not activated now)
- /onboard  -- bootstrap lab integration with this profile
```
