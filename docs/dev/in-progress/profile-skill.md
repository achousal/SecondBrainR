# /profile Skill: Conversational Domain Profile Generator

Development tracking document for the `/profile` skill -- conversational interview that generates a complete domain profile directory for any research field.

Last updated: 2026-03-04

---

## Status: Implemented

All files created and integrated. No new Python code -- relies on existing `domain_profile.py` entry points.

---

## Architecture Overview

```
User invokes /profile
    |
    v
Mode routing (SKILL.md)
    |--- (empty)        -> 6-turn interview -> generation
    |--- --list          -> profile-query fork (haiku)
    |--- --show {name}   -> profile-query fork (haiku)
    |--- --activate {name} -> apply_profile_config() + merge_profile_palettes()
```

### Interview Flow (empty mode)

```
Turn 1: Domain Identity
    |   name, description, purpose, focus_areas
    |   collision check via discover_profiles()
    v
Turn 2: Data Layers + Heuristics
    |   data_layers, file_extensions, tool_references
    |   fires profile-suggest fork in background
    v
Turn 3: Technical Confounders
    |   web-searched suggestions presented
    |   user confirms/edits per layer
    |   biological_confounders, data_reality_signals
    v
Turn 4: PII Patterns
    |   column regex patterns, species column
    v
Turn 5: Literature + Palettes
    |   primary/fallback/sources, env vars
    |   lab palette (hex), semantic palettes
    v
Turn 6: Review + Confirm
    |   formatted summary, yes/edit/cancel
    v
Generation Phase
    |--- profile-generate fork (sonnet) -> writes 5 YAML files
    |--- profile-validate fork (haiku) -> load_profile() check
    |--- optional --activate -> apply to ops/config.yaml
```

---

## File Structure

```
.claude/skills/profile/
  SKILL.md                         # main orchestrator (main context, sonnet)
  sub-skills/
    profile-suggest.md             # fork (haiku): web search confounders/tools
    profile-generate.md            # fork (sonnet): write all YAML files
    profile-validate.md            # fork (haiku): run load_profile() validation
    profile-query.md               # fork (haiku): --list and --show modes
  reference/
    file-schemas.md                # YAML schemas + constraints for each output file
    literature-backends.md         # supported sources, env vars, routing rules
    domain-examples.md             # 3 worked examples (materials-science, social-epi, neuroscience)
    interview-prompts.md           # exact prompts for each conversation turn
```

---

## Generated Profile Output

Each profile creates `_code/profiles/{name}/` with:

| File | Required Keys | Consumer |
|------|--------------|----------|
| `profile.yaml` | name, description, version, config_overrides.data_layers, config_overrides.research, config_overrides.literature | /onboard Turn 3, domain_profile.py |
| `confounders.yaml` | top-level keys = data_layer names, biological_confounders, data_reality_signals | /init Phase 3b |
| `heuristics.yaml` | file_extensions, tool_references (values = data_layer names) | /onboard scan |
| `pii_patterns.yaml` | column_patterns (regex strings) | pii_filter.py |
| `palettes.yaml` | labs dict, semantic dict | plot_theme.py via merge_profile_palettes() |

---

## Python Entry Points (no new code)

All in `_code/src/engram_r/domain_profile.py`:

- `discover_profiles()` -- list available profile names
- `load_profile(name)` -- load and validate a profile
- `apply_profile_config(profile, config_path)` -- merge overrides into ops/config.yaml
- `merge_profile_palettes(profile, palettes_path)` -- merge palettes into styles/palettes.yaml

---

## Integration Points

| Consumer | How it uses profiles |
|----------|---------------------|
| `/onboard` Turn 3 | Matches scan domain against profiles, suggests activation |
| `/init` Phase 3b | Reads confounders.yaml for auto-draft confounder claims |
| `/eda` | Uses data_layers for analysis type detection |
| `/plot` | Uses palettes via merge_profile_palettes() |
| `/literature` | Uses literature sources and routing from profile |
| `/learn` | Uses research primary/fallback routing |

---

## Modifications to Existing Files

1. **`.claude/skills/onboard/SKILL.md` line 265** -- "no match" branch now suggests `/profile`
2. **`docs/manual/skills.md`** -- `/profile` entry added before `/onboard` in reference section

---

## Verification Checklist

- [x] `discover_profiles()` returns existing profiles (bioinformatics)
- [x] All 17 `test_domain_profile.py` tests pass
- [x] `/profile` registered in skill list
- [ ] End-to-end: create a test profile via interview
- [ ] End-to-end: `--list` shows created profile
- [ ] End-to-end: `--show {name}` displays profile details
- [ ] End-to-end: `--activate {name}` updates ops/config.yaml
- [ ] Generated profile loads via `load_profile()`
- [ ] `/onboard` suggests `/profile` when no match found

---

## Design Decisions

1. **No new Python code** -- all entry points exist in `domain_profile.py`. The skill calls them via `uv run`, same pattern as `/onboard`.

2. **Background confounder search** -- Turn 2 fires `profile-suggest` (haiku) in background while collecting data layers. Results arrive by Turn 3 without blocking the interview.

3. **Wong 2011 default palette** -- if user skips palette selection, the colorblind-safe 8-color set is used automatically.

4. **Validation before activation** -- `profile-validate` fork calls `load_profile()` to catch structural issues before the profile is offered for activation.

5. **6-turn interview** -- balances thoroughness (confounders, PII, literature routing) with user patience. Each turn collects a coherent group of related settings.

---

## Future Considerations

- Profile versioning and migration when schema changes
- Profile sharing/export between vaults
- Profile templates for common sub-domains (e.g., clinical-genomics as bioinformatics variant)
- Automated confounder suggestion improvements via domain-specific databases
