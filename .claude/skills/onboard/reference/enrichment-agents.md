# Enrichment Agent Prompts

Reference file for the /onboard orchestrator's Turn 1b context enrichment phase.
Each section is a complete agent prompt template. The orchestrator substitutes `{variables}` and launches via the Agent tool.

All agents use WebSearch/WebFetch directly and return structured output. No inbox files are created.

---

## A1: Lab Profile Enrichment

**Agent config:** subagent_type: "onboard-enrich-lab"
**Condition:** Always runs. WebFetch step requires a lab website URL; web search runs regardless.

**Prompt template:**

```
You are enriching lab-level context during /onboard. Your job has two parts -- run both.

PART 1: Lab website (if URL provided)

WebFetch the URL: {lab_website_url}
Prompt: "Extract from this lab website:
1. Research focus areas and themes
2. Current group members (name, role: faculty/postdoc/student/staff)
3. Active projects or research programs
4. Key publications or highlighted papers
5. Lab resources, tools, or databases maintained by the lab
6. Collaborations mentioned
Return as structured sections. Omit any section with no content."

PART 2: Broader lab context via web search

Run two WebSearch calls:
  1. WebSearch query: "{PI Name} {Institution Name} lab research focus publications"
  2. WebSearch query: "{PI Name} {Institution Name} collaborations grants research program"

Extract relevant details from the search results. If a result page looks especially informative,
use WebFetch to get the full content.

COMBINE AND RETURN exactly this format (no extra text):

RESEARCH_THEMES:
- [theme or focus area]

GROUP_MEMBERS:
- name: [name]
  role: [faculty|postdoc|student|staff|unknown]

ACTIVE_PROJECTS:
- [project name and brief description]

KEY_PUBLICATIONS:
- [citation or title]

LAB_RESOURCES:
- [tool, database, or resource maintained by the lab]

COLLABORATIONS:
- [collaborator or institution]

LAB_WEBSITE_URL: {url or "not provided"}
SOURCE: [website|search|both] (indicate which sources contributed)

Merge findings from both parts. Deduplicate. If WebFetch and web search disagree, include both with source attribution. If WebFetch fails (timeout, 403), proceed with web search results only.
```

---

## A2: Department and Center Enrichment

**Agent config:** subagent_type: "onboard-enrich-quick"
**Condition:** Departments or Centers show "--" in scan results.

**Prompt template:**

```
You are enriching institutional context during /onboard. Your job:

1. Run two WebSearch calls:
   WebSearch query: "{PI Name} {Institution Name} faculty profile departments affiliations"
   WebSearch query: "{PI Name} {Institution Name} research centers institutes programs"

2. If a result page looks especially informative (e.g., a faculty profile page), use WebFetch to get the full content.

3. From the results, extract:
   - Department names: formal department affiliations (e.g., "Department of Neurology")
   - For each department, classify its type:
     basic_science (fundamental research, e.g., Oncological Sciences, Neuroscience)
     clinical (patient-facing, e.g., Neurology, Dermatology, Pathology)
     translational (bridging basic and clinical)
     computational (data/AI, e.g., Artificial Intelligence and Human Health)
   - Center affiliations: research centers, institutes, or programs
   - External affiliations: institutions outside the primary one

4. Return EXACTLY this format (no extra text):

DEPARTMENTS:
- name: [department name]
  type: [basic_science|clinical|translational|computational]

CENTERS:
- [center or institute name]

EXTERNAL_AFFILIATIONS:
- [institution name]

If web search returns no useful results, return:
DEPARTMENTS: none found
CENTERS: none found
EXTERNAL_AFFILIATIONS: none found
```

---

## A3: Institutional Resources

**Agent config:** subagent_type: "onboard-enrich-quick"
**Condition:** Scan produced thin infrastructure (few platforms, no core facilities).

**Prompt template:**

```
You are enriching institutional context during /onboard. Your job:

1. Run two WebSearch calls:
   WebSearch query: "{Institution Name} research computing HPC clusters GPU resources"
   WebSearch query: "{Institution Name} core facilities shared resources platforms biobanks"

2. If a result page looks especially informative (e.g., a research computing page), use WebFetch to get the full content.

3. From the results, extract infrastructure organized by category:
   - Compute: HPC clusters, GPU resources, cloud accounts (include scheduler type if mentioned)
   - Core facilities: shared instrumentation and service labs relevant to {domain}
   - Platforms: data management, clinical, and research platforms
   - Shared resources: biobanks, repositories, registries, shared datasets

4. Return EXACTLY this format (no extra text):

COMPUTE:
- name: [cluster/resource name]
  type: [HPC|cloud|GPU]
  scheduler: [LSF|SLURM|PBS|unknown]
  notes: [access notes if any]

CORE_FACILITIES:
- [facility name and brief description]

PLATFORMS:
- [platform name and brief description]

SHARED_RESOURCES:
- [resource name and brief description]

If web search returns no useful results, return the categories with "none found".
```

---

## B1: Department-Specific Resources

**Agent config:** subagent_type: "onboard-enrich-quick"
**Condition:** A2 returned departments. Run AFTER Phase A completes.
**Limit:** Top 2 departments most relevant to the lab's research domain.

**Prompt template:**

```
You are enriching department-level context during /onboard. Your job:

1. Run a WebSearch call:
   WebSearch query: "{Institution Name} {Department Name} research laboratories core facilities resources"

2. If a result page looks especially informative (e.g., a department research page), use WebFetch to get the full content.

3. From the results, extract department-specific resources:
   - Labs: named research labs within the department
   - Instrumentation: specialized equipment or platforms
   - Programs: training programs, consortia, or collaborative initiatives
   - Resources: databases, tools, or services specific to this department

4. Return EXACTLY this format (no extra text):

DEPARTMENT: [department name]

LABS:
- [lab name and PI if mentioned]

INSTRUMENTATION:
- [equipment or platform]

PROGRAMS:
- [program name and brief description]

RESOURCES:
- [resource name and brief description]

If web search returns no useful results, return the categories with "none found".
```

---

## B2: Compute Resource Reference

**Agent config:** subagent_type: "onboard-enrich-lab"
**Condition:** A3 returned COMPUTE entries. Runs in Phase B (sequential after Phase A). Cap: 2 resources.

**Prompt template:**

```
You are building a practical compute resource reference during /onboard. Your job:

CONTEXT (from scan):
  Cluster name: {cluster_name}
  Resource type: {resource_type}
  Scheduler: {scheduler}
  Institution: {institution_name}
  Detected allocation names: {alloc_names}
  Detected HPC paths: {hpc_paths}
  Username: {username}

1. Run WebSearch calls to find official documentation:
   WebSearch query: "{cluster_name} {institution_name} HPC user guide documentation"
   WebSearch query: "{cluster_name} {scheduler} queues filesystems GPU resources"

2. If a result page looks especially informative (e.g., a user guide or getting started page),
   use WebFetch to get the full content.

3. From the official docs and search results, extract information for each section below.
   Merge scan-detected facts (allocation names, HPC paths, username) into the output
   even if web search returns limited results.

4. Return EXACTLY this format (no extra text):

ACCESS:
  hostname: [login hostname]
  auth: [authentication method]
  login_nodes: [comma-separated list or "unknown"]
  support: [support email or URL]
  docs_url: [official documentation URL]

FILESYSTEM:
- path: [filesystem path]
  quota: [quota limit]
  backup: [yes|no]
  purge: [purge policy or "none"]
  use: [intended purpose]

COMMANDS:
- command: [command name]
  purpose: [what it does]

QUEUES:
- name: [queue name]
  max_walltime: [max walltime]
  notes: [usage notes]

TEMPLATES:
  interactive: |
    [interactive session command]
  batch: |
    [batch script template with scheduler directives]
  gpu: |
    [GPU job template with scheduler directives]

ENVIRONMENT:
  module_system: [lmod|modules|none|unknown]
  package_manager: [conda|mamba|pip|spack|unknown]
  notes: [environment management notes]

GPU_FLEET:
- model: [GPU model name]
  queue: [associated queue(s)]
  notes: [count or other details]

BEST_PRACTICES:
- [practical tip or important caveat]

SOURCE: [docs_url|search|both]

If web search returns no useful results for a section, populate it with scan-detected
facts where possible and mark unknown fields as "unknown". Always include detected
allocation names in TEMPLATES and detected paths in FILESYSTEM.
```
