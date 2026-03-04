---
name: onboard
description: "Bootstrap EngramR integration for a lab. Hybrid scan + interview creates project notes, data inventory, research goals, and vault wiring. Triggers on /onboard, /onboard [path], /onboard --update."
version: "2.0"
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
  - Skill
  - WebFetch
  - Agent
argument-hint: "[lab-path] -- path to lab directory; --update for incremental mode"
---

## EXECUTE NOW

**Target: $ARGUMENTS**

You are the /onboard orchestrator. You run in main context -- natural conversation turns, no AskUserQuestion needed. Sub-skills handle computation in fork context; you handle all user interaction.

**Architecture:** This skill coordinates three fork sub-skills via the Agent tool (subagent_type: general-purpose). Each agent Reads its sub-skill file from `sub-skills/` and executes its instructions in isolation:
- `onboard-scan` -- filesystem scan, convention mining, institution lookup
- `onboard-generate` -- artifact creation (project notes, symlinks, data inventory)
- `onboard-verify` -- schema and link validation

Detailed instructions for each phase live in `reference/` files that sub-skill agents Read on demand.

---

## Phase 1: SETUP

### Parse arguments

| Input | Mode |
|-------|------|
| (empty) | Ask user for lab path in conversation |
| `~/projects/Lab_Name/` | Full onboard for that lab |
| `~/projects/` (root with multiple labs) | Multi-lab: detect subdirs |
| `--update` | Re-scan registered lab paths for new projects |

If no path provided, ask: "Which lab directory should I scan? Paste the path (e.g., ~/projects/My_Lab/)."

### Depth-first loading

If the user provides a multi-lab root, onboard ONE lab first. After completion, suggest the rest for later sessions. Comprehension before coverage -- the user's understanding compounds with each layer.

### Display roadmap

```
=== Onboarding Roadmap ===

4 phases, ~3 interactions from you:

  1. SCAN       Discover projects, mine conventions, look up institution.
                (Automatic -- no input needed.)

  2. REVIEW     Present findings for your correction.
                (Your main interaction -- confirm/adjust.)

  3. GENERATE   Create all vault artifacts after your approval.
                (One approval, then automatic.)

  4. SUMMARY    Verify and present results. Suggest /init.

=== Let's begin ===
```

---

## Phase 2: SCAN

Launch a scan agent using the Agent tool:

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "onboard scan")
Prompt: "Read and execute .claude/skills/onboard/sub-skills/onboard-scan.md with target: {lab-path}. Return the structured SCAN RESULTS output as specified in the sub-skill's Step 6."
```

Parse the structured output (Lab Profile, Infrastructure, Projects table, etc.).

---

## Phase 3: REVIEW (2-3 conversation turns)

Present scan results in focused stages. Each is a natural conversation turn.

### Turn 1: Institution and Infrastructure

Present the lab profile and infrastructure in a readable format:

```
=== Institution and Infrastructure ===

Lab Profile:
  PI:          {name}                    (from {source})
  Institution: {name}                    (confirmed)
  Departments: {list}
  Centers:     {list}

Lab Infrastructure:
  Compute:     {cluster / scheduler}
  Platforms:   {list}
  Facilities:  {list}

Also detected: {conventions summary}
```

Then ask:

"Does this look right? Correct any fields, add missing facilities or resources.

Also -- do you have a lab website URL? (optional -- helps fill in research themes, group members, and active projects)"

Wait for user response. Apply corrections.

### Turn 1b: Context Enrichment (automatic)

After user confirms Turn 1, enrich context before presenting projects. Goal: fill maximum institutional context without redundant lookups.

Read `reference/enrichment-agents.md` for the full agent prompt templates referenced below. Each agent uses WebSearch/WebFetch and returns structured output directly. No inbox files are created.

#### Institution-Aware Gate

Before launching any enrichment agents, check the scan output for an existing institution profile:

1. If scan reports `Institution Profile: ops/institutions/{slug}.md` (profile exists):
   - Read the profile. Populate Turn 1 fields (departments, centers, compute, facilities) FROM the existing profile.
   - **Skip A2** (departments already known) and **A3** (infrastructure already known).
   - **Skip B1** unless user corrected departments in Turn 1 or added new ones.
   - **Always run A1** (lab-specific: website + /learn for THIS lab's profile, which differs per PI).
   - After Turn 1 confirmation, check if user added departments or centers not in the profile. If so, run the **merge step** (see `reference/institution-lookup.md`, "Merge into existing profile").

2. If scan reports no existing profile (first lab at this institution):
   - Run full enrichment (A1 + A2 + A3 + B1) as below.

3. If `--refresh` flag is set:
   - Ignore existing profile. Run full enrichment and overwrite the profile.

#### Cross-Lab Detection

After loading the scan results, grep for other labs at the same institution:

```
Grep pattern: "institution:.*{Institution Name}" path: projects/ glob: "*/_index.md"
```

If other labs found, present inline in the Merge and Present block:

```
Also at {Institution Name}: {other lab names} (already onboarded)
```

#### Phase A (parallel)

Launch all available enrichment steps simultaneously via a single message with multiple tool calls. Respect the institution-aware gate above -- skip agents whose data is already in the profile.

- **A1. Lab profile** (always runs; URL optional): Launch agent using A1 template from `reference/enrichment-agents.md`. Does WebFetch of lab URL (if provided) + WebSearch for broader lab context. Substitute `{PI Name}`, `{Institution Name}`, `{lab_website_url}`.
- **A2. Departments** (skip if profile loaded; run if Departments show "--" and no profile): Launch agent using A2 template from `reference/enrichment-agents.md`. Substitute `{PI Name}` and `{Institution Name}`.
- **A3. Institutional resources** (skip if profile loaded; run if thin infrastructure and no profile): Launch agent using A3 template from `reference/enrichment-agents.md`. Substitute `{Institution Name}` and `{domain}`.

#### Phase B (sequential, after Phase A)

- **B1. Department-specific resources** (only if A2 returned NEW departments not in existing profile): Parse department names from A2 output. Launch agent(s) using B1 template from `reference/enrichment-agents.md`. Limit to 2 most relevant departments. Run in parallel if multiple.

- **B2. Compute resource reference** (only if A3 returned COMPUTE entries): Parse COMPUTE entries from A3 output. For each resource (cap 2), launch agent using B2 template from `reference/enrichment-agents.md`. Substitute `{cluster_name}`, `{resource_type}`, `{scheduler}`, `{institution_name}`, `{alloc_names}`, `{hpc_paths}`, `{username}`. Run in parallel if multiple resources.

  After B2 returns, for each compute resource:
  1. Write `ops/{cluster-slug}.md` using the `_code/templates/compute-reference.md` structure populated with B2 output + scan-local facts.
  2. Update institution profile: add `Practical reference: [[{cluster-slug}]]` line under the Compute Resources section if not already present.

#### Merge and Present

Merge enrichment results into scan data. Deduplicate against filesystem-detected infrastructure and existing institution profile.

If an existing institution profile was loaded and new departments or resources were discovered, update the profile (see `reference/institution-lookup.md`, "Merge into existing profile").

```
=== Context Enrichment ===

{if profile loaded}: Institution profile loaded: ops/institutions/{slug}.md ({N} departments, {N} facilities).
{if lab website}: Lab website: {N} research themes, {N} group members, {N} projects found.
{if departments NEW}: New departments: {list with types}. Merged into institution profile.
{if departments LOADED}: Departments: {list with types} (from profile). Centers: {list}.
{if external}: External affiliations: {list}.
{if institutional NEW}: Infrastructure: {N} compute, {N} core facilities, {N} platforms, {N} shared resources.
{if dept-specific}: Department resources: {summary per department}.
{if compute-ref}: Compute reference: ops/{slug}.md created ({scheduler} scheduler, {N} queues, {N} GPU types).
{if cross-lab}: Cross-lab: {other labs at same institution}.

Enriched fields will inform project registration and goal creation.
```

Proceed to Turn 2.

### Turn 2: Projects and Goals

Present the project table and suggested goals together in one review turn:

```
=== {Lab Name} ({N} projects) ===

| # | Project | Status | Domain | Languages | Data Layers | Data Access | Research Q |
|---|---------|--------|--------|-----------|-------------|-------------|------------|
{rows from scan}

Fields marked -- could not be auto-detected.

=== Suggested Research Goals ===

Based on your projects, here are suggested research goals:

{numbered list, each with:
  - suggested goal title (prose, not a label)
  - one-line scope
  - linked projects from the scan}
```

Auto-derive suggested research goals from the scan results: group projects by shared research themes, data types, or biological questions.

Then ask: "Adjust projects or goals as needed. You can correct project fields, edit/add/remove/merge goals, or deselect projects. Anything else I should know?"

Wait for user response. Apply all corrections and goal edits.

**Quality bar for goal suggestions:** Each goal should be specific enough to generate hypotheses from, but broad enough to span multiple projects. Prefer "vascular contributions to cognitive decline" over "vascular biology". Ground suggestions in the actual projects, data, and methods detected in the scan.

Proceed to Turn 3.

### Turn 3: Domain Profile and Generate Approval

After projects and goals are confirmed, detect and activate a domain profile, then present the artifact list for approval.

#### Domain Profile Detection

1. Read scan results for domain signals (project languages, data layers, tool references).
   Use the domain inference from the scan (Research Domain field).

2. Call discover_profiles() to list available profiles:
   ```
   uv run --directory _code python -c "
   import json, sys; sys.path.insert(0, 'src')
   from engram_r.domain_profile import discover_profiles
   print(json.dumps(discover_profiles()))
   "
   ```

3. Match scan-detected domain against available profiles (substring match on profile name
   or description). If a match is found, present it as a suggestion:

   ```
   Domain detected: {scan domain} -> Profile match: {profile.name} ({profile.description})

   Apply this domain profile? It configures:
   - Literature sources: {profile.config_overrides.literature.sources}
   - Research backends: {profile.config_overrides.research}
   - Data layers: {len(profile.config_overrides.data_layers)} types
   ```

   If no match: print "No domain profile matches your scan. Run `/profile` to create one, or continue with base config." If user declines a match: skip profile activation, proceed with base config.

4. On confirmation, apply the profile:
   ```
   uv run --directory _code python -c "
   import sys; sys.path.insert(0, 'src')
   from engram_r.domain_profile import load_profile, apply_profile_config, merge_profile_palettes
   p = load_profile('{profile_name}')
   apply_profile_config(p, '../ops/config.yaml')
   merge_profile_palettes(p, 'styles/palettes.yaml')
   "
   ```

5. After activation, check literature readiness:
   ```
   uv run --directory _code python -c "
   import json, sys; sys.path.insert(0, 'src')
   from engram_r.search_interface import check_literature_readiness
   print(json.dumps(check_literature_readiness('../ops/config.yaml')))
   "
   ```

6. If `result.ready` is True: print "Literature search: ready." and proceed to Generate Approval.

7. If `result.ready` is False:
   a. Read `.claude/skills/literature/reference/setup-flow.md`
   b. Present the setup status block with profile-specific guidance (Steps 1-2 from reference)
   c. Show export commands for missing required vars only (Step 3)
   d. Ask: "Open _code/.env in your editor and fill in the missing values. The file already has placeholder lines. It is gitignored. Say 'done' when saved, or 'skip' to configure later via /literature --setup."
   e. On "done": re-check with `set -a && source _code/.env 2>/dev/null && set +a` prefix (Step 4)
   f. On "skip" or after "check" succeeds: proceed to Generate Approval
   g. Store the final `result.ready` state for use in the Phase 5 summary

#### Generate Approval

After domain profile is resolved, present the artifact list and wait for approval:

```
Ready to create:
- projects/{lab}/{tag}.md (per NEW project)
- projects/{lab}/_index.md (lab entity)
- _dev/{tag} symlinks
- _research/goals/{slug}.md ({N} goals from your review)
- projects/_index.md updates
- _research/data-inventory.md entries
- self/goals.md thread updates
{if compute-ref}: - ops/{cluster-slug}.md (compute reference -- already created during enrichment)

Proceed?
```

Wait for user approval. On approval, proceed to Phase 4 (Generate).

---

## Phase 4: GENERATE

**On approval (from Turn 3):** Write the corrected scan data to a temp file, then launch a generation agent:

```
Agent(subagent_type: "general-purpose", model: "sonnet", description: "onboard generate")
Prompt: "Read and execute .claude/skills/onboard/sub-skills/onboard-generate.md with target: {temp-file-path}. Return the structured ARTIFACTS CREATED output as specified in the sub-skill's Step 5."
```

Parse the output (files created, modified, symlinks).

Then launch a verification agent:

```
Agent(subagent_type: "general-purpose", model: "haiku", description: "onboard verify")
Prompt: "Read and execute .claude/skills/onboard/sub-skills/onboard-verify.md. Return the structured VERIFICATION REPORT as specified in the sub-skill's Step 4."
```

---

## Phase 5: SUMMARY

Present summary:

```
=== /onboard Summary ===

Lab: {name} ({path})
Institution: {name or "none"}
Projects registered: {N}
{list with tags}

Data inventory entries: {N}
Research goals created: {N}
Symlinks created: {N}

=== Quick Orientation ===

Your vault now has {N} projects. Here is how to navigate:

  projects/{lab}/_index.md     Lab profile with project links
  _research/data-inventory.md  Data coverage matrix
  _research/goals/             Research goals (seeded by /init)
  notes/                       Knowledge claims (populated by /init)

The knowledge graph is currently empty. /init will create
your first claims in four layers:

  Orientation   -- what you study
  Methodology   -- how you study it
  Confounders   -- what could fool you
  Inversions    -- what would prove you wrong

=== What's Next ===

>> /init                                          [START HERE]
   Seeds all four claim layers for your research goals.

Then: Add foundational papers to inbox/ -> /seed --all -> /ralph -> /literature -> /ralph -> /research
{if literature setup was skipped during Turn 3}: Note: run /literature --setup to configure missing API keys ({var list}).
{if literature setup was completed during Turn 3}: (Literature search is ready.)
=== End Summary ===
```

If verification found issues, report them inline.

---

## Mode: --update

For incremental mode:
1. Read registered project paths from `projects/*/*.md` frontmatter
2. Re-scan each lab root for new subdirectories
3. Skip review of existing projects
4. Only present NEW discoveries
5. Follow same generate + verify flow for new projects only

## Mode: Handoff

If `--handoff` was included in arguments, append RALPH HANDOFF block after the summary (see reference/conventions.md for format).

---

## Error Handling

| Error | Behavior |
|-------|----------|
| Lab path does not exist | Report error, ask for correct path |
| No projects detected | Report indicators checked, ask if path is correct |
| Sub-skill invocation fails | Report error, offer to retry or proceed manually |
| User wants to skip a phase | Respect the skip, note it in summary |

---

## Skill Graph

Invoked by: user (standalone), /ralph (delegation)
Invokes: onboard-scan, onboard-generate, onboard-verify (via Agent tool)
Suggests next: /init (primary), /literature, /reduce, /reflect
Reads: projects/, _research/data-inventory.md, _research/goals/, self/goals.md, ops/reminders.md, ops/config.yaml, filesystem
Writes: projects/, _research/data-inventory.md, _research/goals/, self/goals.md, ops/reminders.md, projects/_index.md, _dev/ symlinks, ops/institutions/, ops/config.yaml, ops/{cluster-slug}.md
