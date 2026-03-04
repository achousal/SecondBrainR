---
name: profile-suggest
description: "Web search for domain-specific confounders and tool suggestions per data layer. Internal sub-skill -- not user-invocable."
version: "1.0"
user-invocable: false
context: fork
model: haiku
allowed-tools:
  - WebSearch
  - WebFetch
  - Read
---

## EXECUTE NOW

**Target: $ARGUMENTS**

You are a research assistant gathering confounder suggestions for a new domain profile. You receive a domain name and list of data layers.

### Step 1: Parse Input

Extract from $ARGUMENTS:
- `domain_name`: the research domain
- `data_layers`: list of data layer names

### Step 2: Web Search Confounders

For each data layer, search for common technical confounders:

Query pattern: `"{data_layer}" common confounders bias artifacts {domain_name} research`

Extract 3-5 concise confounder phrases per layer. Focus on:
- Measurement artifacts and biases
- Batch effects and technical variability
- Pre-analytical factors
- Known sources of systematic error

### Step 3: Web Search Tools

For each data layer, search for commonly used analysis tools:

Query pattern: `"{data_layer}" analysis software tools {domain_name}`

Extract 2-4 tool names per layer.

### Step 4: Return Results

Return a structured summary:

```
CONFOUNDER SUGGESTIONS:
{LayerName}:
  - "confounder 1"
  - "confounder 2"
  - "confounder 3"

TOOL SUGGESTIONS:
{LayerName}:
  - ToolName1
  - ToolName2
```

Keep suggestions concise (1 phrase each). Do not editorialize -- the user will review and edit.
