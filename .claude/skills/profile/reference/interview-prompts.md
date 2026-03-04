# Interview Prompts

Exact prompts for each conversation turn of the /profile interview. The orchestrator uses these verbatim (adapting only the dynamic parts in {braces}).

---

## Turn 1: Domain Identity

```
Let's create a domain profile for your research field.

I need four things to start:

1. **Profile name** -- machine-safe identifier (lowercase, hyphens, no spaces).
   Examples: materials-science, social-epidemiology, neuroscience

2. **Description** -- one sentence describing the domain.

3. **Agent purpose** -- what should the co-scientist focus on in this domain?
   Example: "Co-scientist for structure-property relationship discovery in materials"

4. **Focus areas** -- 2-4 research themes you work on.
   Example: crystal structure prediction, mechanical property optimization
```

After user responds, validate:
- Name is machine-safe (lowercase, hyphens, alphanumeric only)
- Name does not collide with existing profiles (check `discover_profiles()`)
- 2-4 focus areas provided

If name collides, say: "A profile named '{name}' already exists. Choose a different name or use `/profile --show {name}` to see the existing one."

---

## Turn 2: Data Layers + Heuristics

```
Now let's define your data types.

**Data layers** -- what kinds of data do you work with?
List 2-8 types. Examples: {domain-appropriate examples from reference/domain-examples.md}

For each data layer, also tell me:
- **File extensions** you commonly encounter (e.g., .csv, .nii, .shp)
- **Tools/software** you use for analysis (e.g., VASP, Stata, Seurat)
```

After collecting, fire `profile-suggest` fork in background with the domain name and data layers to web-search confounders.

---

## Turn 3: Technical Confounders

Present the web-searched suggestions:

```
Based on your data layers, here are common technical confounders I found:

{For each data layer:}
**{LayerName}:**
- {suggestion 1}
- {suggestion 2}
- {suggestion 3}

Edit this list -- add, remove, or rephrase any items.

Also tell me:
- **Biological confounders** that apply across your data (e.g., age, sex, strain)
- **Data reality signals** -- systematic constraints to flag automatically.
  Format: condition -> claim template.
  Example: "simulation-only" -> "computational predictions require experimental validation"
```

---

## Turn 4: PII Patterns + Data Reality Signals

```
What column names in your datasets might contain personally identifiable information?

Give me regex-friendly patterns. Examples:
- subject_id, participant_name, MRN, date_of_birth
- I'll convert them to regex patterns like: \b(subject|participant)[\\s_]?id\b

Also, does your data have a species/organism column? If so, what is it called?
(This enables automatic "translational gap" flagging.)
```

---

## Turn 5: Literature + Palettes

```
**Literature search backends** -- which databases should /literature search?

Available: pubmed, arxiv, semantic_scholar, openalex
(See the table below for what each covers.)

| Backend | Best for |
|---------|----------|
| pubmed | Biomedical, clinical |
| arxiv | Physics, CS, math, quant-bio |
| semantic_scholar | Cross-domain academic |
| openalex | Cross-domain, open metadata |

Pick:
1. **Primary** (first tried): ___
2. **Fallback** (if primary fails): ___
3. **All sources to enable**: [list]

**Color palette** (optional) -- provide hex colors for your lab palette, or press Enter to use the colorblind-safe Wong 2011 default.

Format: #E69F00, #56B4E9, #009E73, ...

**Semantic palettes** (optional) -- map variable values to colors.
Example: sex -> Male: #377EB8, Female: #E41A1C
```

---

## Turn 6: Review + Confirm

```
Here's your complete profile:

**{name}** -- {description}
Purpose: {purpose}
Focus: {focus_areas joined}

Data layers ({count}): {layers joined}
Confounders: {count per layer} technical, {count} biological
PII patterns: {count} patterns
Literature: primary={primary}, fallback={fallback}, sources=[{sources}]
Palette: {lab palette color count} colors{, semantic mappings if any}

Ready to generate? (yes/edit/cancel)
```

On "yes": proceed to generation phase.
On "edit": ask which section to revise, loop back to that turn.
On "cancel": abort with no files written.
