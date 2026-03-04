---
name: profile-query
description: "List and show domain profiles via discover_profiles() and load_profile(). Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: haiku
allowed-tools:
  - Bash
  - Read
---

## EXECUTE NOW

**Target: $ARGUMENTS**

Handle --list and --show query modes for /profile.

### Parse Mode

Extract mode from $ARGUMENTS:
- `--list`: list all available profiles
- `--show {name}`: show details of a specific profile

---

### Mode: --list

Run:
```bash
cd "$(git rev-parse --show-toplevel)" && uv run --directory _code python -c "
import sys, json
sys.path.insert(0, 'src')
from engram_r.domain_profile import discover_profiles, load_profile

profiles = discover_profiles()
if not profiles:
    print('No domain profiles found.')
    print('Run /profile to create one.')
else:
    print(f'Available profiles ({len(profiles)}):')
    for name in profiles:
        try:
            p = load_profile(name)
            layers = len(p.config_overrides.get('data_layers', []))
            print(f'  {name} -- {p.description} ({layers} data layers, v{p.version})')
        except Exception as e:
            print(f'  {name} -- ERROR: {e}')
"
```

Return the output verbatim.

---

### Mode: --show {name}

Run:
```bash
cd "$(git rev-parse --show-toplevel)" && uv run --directory _code python -c "
import sys, json
sys.path.insert(0, 'src')
from engram_r.domain_profile import load_profile

p = load_profile('{name}')
print(f'Profile: {p.name}')
print(f'Description: {p.description}')
print(f'Version: {p.version}')
print()

identity = p.config_overrides.get('identity', p.identity if hasattr(p, 'identity') else {})
if hasattr(p, 'identity') and p.identity:
    print(f'Purpose: {p.identity.get(\"purpose\", \"N/A\")}')
    print(f'Domain: {p.identity.get(\"domain\", \"N/A\")}')
    focus = p.identity.get('focus_areas', [])
    if focus:
        print(f'Focus areas: {\", \".join(focus)}')
    print()

layers = p.config_overrides.get('data_layers', [])
print(f'Data layers ({len(layers)}): {\", \".join(layers)}')

research = p.config_overrides.get('research', {})
if research:
    print(f'Literature routing: {research.get(\"primary\", \"N/A\")} -> {research.get(\"fallback\", \"N/A\")} -> {research.get(\"last_resort\", \"web-search\")}')

lit = p.config_overrides.get('literature', {})
if lit:
    print(f'Sources: {\", \".join(lit.get(\"sources\", []))}')

print()
print(f'Confounders: {len([k for k in p.confounders.keys() if k not in (\"biological_confounders\", \"data_reality_signals\")])} layer categories')
bio = p.confounders.get('biological_confounders', [])
if bio:
    print(f'Biological confounders: {\", \".join(bio)}')

print(f'PII patterns: {len(p.pii_patterns)}')
print(f'Heuristics: {len(p.heuristics.get(\"file_extensions\", {}))} extensions, {len(p.heuristics.get(\"tool_references\", {}))} tools')

labs = p.palettes.get('labs', {})
semantic = p.palettes.get('semantic', {})
print(f'Palettes: {len(labs)} lab(s), {len(semantic)} semantic mapping(s)')
"
```

Return the output verbatim.
