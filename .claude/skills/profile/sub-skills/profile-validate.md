---
name: profile-validate
description: "Validate a generated profile by calling load_profile(). Internal sub-skill -- not user-invocable."
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

Validate a generated domain profile by calling the Python load_profile() function.

### Step 1: Parse Input

Extract `profile_name` from $ARGUMENTS.

### Step 2: Run Validation

```bash
cd "$(git rev-parse --show-toplevel)" && uv run --directory _code python -c "
import sys, json
sys.path.insert(0, 'src')
from engram_r.domain_profile import load_profile, discover_profiles

# Check profile is discoverable
profiles = discover_profiles()
print(f'Discovered profiles: {profiles}')
assert '{profile_name}' in profiles, f'Profile {profile_name} not found in discovered profiles'

# Load and validate
p = load_profile('{profile_name}')
print(f'Name: {p.name}')
print(f'Description: {p.description}')
print(f'Version: {p.version}')
print(f'Data layers: {p.config_overrides.get(\"data_layers\", [])}')
print(f'Confounders keys: {list(p.confounders.keys())}')
print(f'Heuristics keys: {list(p.heuristics.keys())}')
print(f'PII patterns: {len(p.pii_patterns)} patterns')
print(f'Palettes keys: {list(p.palettes.keys())}')
print('VALIDATION: PASS')
"
```

### Step 3: Return Result

If validation passes, return:
```
VALIDATION: PASS
Profile '{profile_name}' loaded successfully.
- {data_layer_count} data layers
- {confounder_key_count} confounder categories
- {pii_pattern_count} PII patterns
- Palettes: {palette_info}
```

If validation fails, return the error message:
```
VALIDATION: FAIL
Error: {error_message}
```
