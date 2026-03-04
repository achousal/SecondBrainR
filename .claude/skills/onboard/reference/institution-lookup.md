# Institution Resource Lookup

Reference file for the onboard skill. Extracted from the main onboard SKILL.md Step 2g.

---

## Architecture: Scan vs Orchestrator Split

This reference serves two consumers with different responsibilities:

| Step | Owner | Context | Why |
|------|-------|---------|-----|
| Auto-detect institution signals | onboard-scan (fork) | Non-interactive | No wasted lookups on wrong institution |
| Check for existing profile | onboard-scan (fork) | Non-interactive | Load existing data, skip redundant lookups |
| Confirm institution with user | orchestrator (main) | Conversational | User-in-the-loop |
| Ask for lab website URL | orchestrator (main) | Conversational | User provides URL |
| Institution-aware gate | orchestrator (main) | Before enrichment | Skip A2/A3 if profile exists |
| Cross-lab detection | orchestrator (main) | Before enrichment | Grep for other labs at same institution |
| WebSearch for departments | enrichment agents (fork) | After confirmation | Only if no existing profile |
| WebSearch for institutional resources | enrichment agents (fork) | After confirmation | Only if no existing profile |
| Create institution profile | orchestrator (main) | After enrichment | First lab at this institution |
| Merge into existing profile | orchestrator (main) | After enrichment | Second+ lab: append new departments/centers |

The scan agent reads sections marked **[SCAN]** below. The orchestrator reads sections marked **[ORCHESTRATOR]**.

---

## Institution Resource Lookup

Use WebSearch/WebFetch (via enrichment agents) to fetch the institution's resource catalog (HPC, core facilities, platforms, shared resources). This supplements filesystem-based detection with publicly available institutional information.

### Determine institution [SCAN]

1. Check scan identity signals for institution name (from CLAUDE.md, email domains, HPC cluster names).
2. Output detected institution with evidence sources. Do NOT ask the user -- the orchestrator handles confirmation.
3. If no signals found, output "institution: not detected" so the orchestrator can ask.

### Determine departments and affiliations [ORCHESTRATOR]

Runs in the orchestrator's Turn 1b enrichment, after user confirms institution and PI.

1. The A2 enrichment agent (see `reference/enrichment-agents.md`) performs WebSearch for faculty profile, departments, and center affiliations.
2. From the results, extract:
   - **Department names** -- formal department affiliations (e.g., "Department of Neurology", "Department of Oncological Sciences").
   - **Center affiliations** -- research centers, institutes, or programs (e.g., "Tisch Cancer Institute", "Alzheimer's Disease Research Center").
   - **External affiliations** -- institutions outside the primary one (e.g., "James J. Peters VA Medical Center").
3. For each department found, infer the department `type` at the institution level using these categories:
   - `basic_science` -- fundamental research departments (e.g., Oncological Sciences, Neuroscience, Microbiology)
   - `clinical` -- patient-facing or clinical departments (e.g., Neurology, Dermatology, Pathology). Primarily relevant for academic medical centers; non-biomedical domains may not have this type.
   - `translational` -- bridging basic and applied (e.g., Translational Medicine). Primarily relevant for biomedical research; other domains may use `applied` or similar.
   - `computational` -- computational or data science (e.g., Artificial Intelligence and Human Health)
4. Results are merged into scan data and shown in the Turn 1b enrichment summary.
5. If web search returns no useful results, the orchestrator asks the user directly.

Store confirmed values as DEPARTMENTS, CENTER_AFFILIATIONS, and EXTERNAL_AFFILIATIONS.

### Confirm detected values [ORCHESTRATOR]

Handled by the orchestrator in Review Turn 1. The scan agent outputs detected values with evidence; the orchestrator presents them to the user for confirmation.

### Lab website lookup (optional) [ORCHESTRATOR]

Runs in the orchestrator's Turn 1b enrichment, after user provides URL in Turn 1.

1. The orchestrator asks for the lab website URL in Turn 1 (alongside "Does this look right?").
2. If user provides a URL, the orchestrator invokes WebFetch directly:
   ```
   WebFetch URL={user URL}
   Prompt: "Extract the following from this lab website:
   1. Research focus areas and themes
   2. Current group members (faculty, postdocs, students)
   3. Active projects or research programs
   4. Key publications or highlighted papers
   5. Lab resources, tools, or databases
   6. Collaborations mentioned
   Return as structured sections. Omit any section with no content."
   ```
3. Parse WebFetch output into onboard-relevant categories:
   - `research_themes` -- feeds into project registration context and goal creation
   - `group_members` -- enriches lab profile (future: collaboration graph)
   - `active_projects` -- cross-reference against filesystem scan
   - `resources` -- merge with institutional resources from /learn
4. Store parsed results as LAB_WEBSITE_DATA.
5. Store the URL itself as `lab_website_url` for the lab entity node.

**Relationship to enrichment agents:** WebFetch captures the lab's self-presentation (themes, members, active projects). Enrichment agents (A1-A3) capture institutional context via WebSearch. Results are merged in the review presentation.

**Skip conditions (WebFetch only -- web search always proceeds):**
- User provides no URL or says skip: skip WebFetch, proceed with web search.
- WebFetch fails (timeout, 403, etc.): warn the user, proceed with web search results.

### Generate institution slug [SCAN]

Lowercase, hyphens for spaces, no special characters. Example: `mount-sinai`, `memorial-sloan-kettering`. The scan agent generates this from auto-detected institution name; the orchestrator may update it after user confirmation.

### Check for existing profile [SCAN]

1. Check if `ops/institutions/{institution-slug}.md` already exists.
2. If yes: read it, feed into presentation. Inform user:
   ```
   Loaded existing institution profile: ops/institutions/{slug}.md
   To refresh from web: rerun with --refresh
   ```
   Skip to presentation.
3. If no: proceed with /learn lookup.

### Web Lookup [ORCHESTRATOR]

Enrichment agents (A1-A3, B1) in `reference/enrichment-agents.md` handle all web lookups via WebSearch/WebFetch. The orchestrator launches them per Turn 1b instructions in SKILL.md. No inbox files are created -- agents return structured output directly.

### Create institution profile [ORCHESTRATOR]

Written by the orchestrator after all enrichment data is merged. Uses `_code/templates/institution.md`:

```yaml
---
type: "institution"
name: "{Institution Full Name}"
slug: "{institution-slug}"
departments:
  - name: "{department name}"
    type: "{basic_science|clinical|translational|computational}"
centers:
  - "{center or institute name}"
compute:
  - name: "{cluster name}"
    type: "{HPC|cloud|GPU}"
    scheduler: "{LSF|SLURM|PBS|...}"
    notes: "{access notes}"
core_facilities: ["{parsed facilities}"]
platforms: ["{parsed platforms}"]
shared_resources: ["{parsed shared resources}"]
source_urls: ["{urls from /learn sources}"]
last_fetched: "{today}"
created: "{today}"
updated: "{today}"
tags: ["institution"]
---
```

Department type enum: `basic_science` (fundamental research), `clinical` (patient-facing), `translational` (bridging), `computational` (data/AI). Centers are flat strings.

Populate body sections with details from /learn output, organized under the template headings (Compute Resources, Core Facilities, Platforms and Databases, Shared Resources (e.g., biobanks, cohorts, repositories)).

### Merge into existing profile [ORCHESTRATOR]

When onboarding a second (or later) lab at the same institution, the existing profile is loaded but may need updates. This step runs after Turn 1 confirmation if the user corrected or added departments/centers, or if A2 enrichment returned new departments not in the profile.

**Merge rules:**

1. **Departments**: Append any departments not already in the profile's `departments:` list. Match by name (case-insensitive). Do not remove existing departments.
2. **Centers**: Append any centers not already in the profile's `centers:` list. Match by name substring. Do not remove existing centers.
3. **Compute/facilities/platforms**: Only add if genuinely new (not already listed). Infrastructure at the institution level rarely changes between labs.
4. **source_urls**: Append new source URLs from enrichment.
5. **updated**: Set to today's date.
6. **last_fetched**: Only update if new /learn lookups were performed.

**Confirmation**: Before writing the merged profile, present the diff to the user:

```
Institution profile update: ops/institutions/{slug}.md

Adding:
  Departments: + {new department} ({type})
  Centers: + {new center}
  {other additions}

No existing data will be removed. Proceed?
```

Wait for user approval before writing.

**Provenance**: Add a comment in the profile body noting the merge:

```
<!-- Merged from {lab-slug} onboard: {date} -->
```

### Skip conditions

- Institution cannot be determined and user skips the question: skip entirely.
- User says "I'll fill in manually": skip the lookup, create empty profile for manual editing.
- `--refresh` flag not present and profile already exists: load existing, skip lookup (but merge step may still run if new departments found).
