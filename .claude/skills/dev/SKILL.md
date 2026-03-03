---
name: dev
description: "Code section health checks. Runs tests, lint, build, and coverage across codebase sections defined in ops/sections.yaml. Triggers on \"/dev\", \"code health\", \"section checks\", \"check code\"."
version: "1.0"
generated_from: "arscontexta-v1.6"
user-invocable: true
context: fork
model: sonnet
allowed-tools: Read, Grep, Glob, Bash
argument-hint: "[section | --changed | --affected <section>] -- all sections, single section, git-changed, or dependents"
---

## EXECUTE NOW

**Target: `$ARGUMENTS`** (if blank or empty -> DEFAULT)

**STRICT ROUTING -- follow exactly, no exceptions:**
1. If target names a specific section (e.g., `core-lib`, `r-lib`, `skills`) -> run that section only (verbose output).
2. If target is `--changed` -> auto-detect sections touched by recent git changes.
3. If target is `--affected <section>` -> run section + all sections that depend on it.
4. **DEFAULT** -- if target is empty, blank, missing, or does not match any rule above -> run all sections, show summary.

**START NOW.** Run section checks and collect module metrics.

---

## Philosophy

**Code health is vault health.**

The knowledge system depends on reliable infrastructure. Without section checks, the user cannot tell whether tests pass, lint is clean, or builds succeed. /dev provides a snapshot that makes code health tangible -- pass/fail indicators that catch problems and metrics that reveal coverage gaps.

The output should make the user feel informed, not overwhelmed. A healthy codebase gets green checks and summary metrics. Failures get actionable drill-down suggestions.

---

## Step D1: Run Section Checks

```bash
# All sections
bash ops/scripts/section-check.sh 2>&1

# Single section (verbose)
bash ops/scripts/section-check.sh core-lib 2>&1

# Changed sections only
bash ops/scripts/section-check.sh --changed 2>&1

# Section + dependents
bash ops/scripts/section-check.sh --affected core-lib 2>&1
```

Capture and display the output directly. The script handles formatting, colors, and exit codes.

## Step D2: Collect Module Metrics

After running checks, gather quick metrics for the summary:

```bash
# Python module count + total lines
PY_MODULES=$(find _code/src/engram_r -name '*.py' -not -name '__*' | wc -l | tr -d ' ')
PY_LINES=$(cat _code/src/engram_r/*.py 2>/dev/null | wc -l | tr -d ' ')

# Test count + total lines
TEST_FILES=$(find _code/tests -name 'test_*.py' | wc -l | tr -d ' ')
TEST_LINES=$(cat _code/tests/test_*.py 2>/dev/null | wc -l | tr -d ' ')

# Test:code ratio
if [[ "$PY_LINES" -gt 0 ]]; then
  RATIO=$(echo "scale=1; $TEST_LINES / $PY_LINES" | bc)
else
  RATIO="N/A"
fi

# R module count
R_MODULES=$(find _code/R -name '*.R' -not -path '*/tests/*' 2>/dev/null | wc -l | tr -d ' ')
R_TESTS=$(find _code/R/tests -name 'test_*.R' 2>/dev/null | wc -l | tr -d ' ')

# Skill count
SKILL_COUNT=$(find .claude/skills -name 'SKILL.md' | wc -l | tr -d ' ')

# Site components
SITE_COMPONENTS=$(find site/src -name '*.astro' 2>/dev/null | wc -l | tr -d ' ')

# Script count
SCRIPT_COUNT=$(find ops/scripts -name '*.sh' | wc -l | tr -d ' ')
```

## Step D3: Format Dev Output

```
--=={ dev }==--

  Codebase
  ========
  Python modules:  [PY_MODULES] ([PY_LINES] lines)
  Python tests:    [TEST_FILES] ([TEST_LINES] lines, [RATIO]:1 test:code)
  R modules:       [R_MODULES] + [R_TESTS] tests
  Skills:          [SKILL_COUNT]
  Site components: [SITE_COMPONENTS]
  Scripts:         [SCRIPT_COUNT]

  Section Health
  ==============
  [section-check.sh output here]

  Generated with EngramR v0.7
```

## Step D4: Dev Interpretation Notes

| Condition | Note |
|---|---|
| Any section FAIL | "[section] needs attention -- run `/dev [section]` for details" |
| RATIO < 1.0 | "Test:code ratio below 1:1 -- core logic may be undertested" |
| section-check.sh exits non-zero | "Run failing section checks individually for verbose output" |

## Relationship to /health

`/health` checks **vault** health (schema compliance, orphans, link integrity).
`/dev` checks **code** health (tests pass, lint clean, builds work).

They are complementary. A healthy project has both green. Recommend running both before releases:

```
/health  # vault integrity
/dev     # code integrity
```
