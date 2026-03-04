---
description: "Add Anthropic tool_use to the Slack bot so it can perform structured vault operations (search, stats, queue status) instead of relying on prompt-injected context alone."
type: development
status: planned
created: 2026-03-04
---

# Slack Bot Tool Calling

Give the Slack bot programmatic access to vault operations via the Anthropic Messages API `tool_use` feature. Currently the bot gets a static system prompt with cached vault context and produces free-text responses. With tool calling, it can dynamically query the vault mid-conversation.

---

## Motivation

| Problem | Impact |
|---------|--------|
| Bot context is a static snapshot refreshed every 5 min | Stale answers about queue state, recent claims, processing status |
| Cannot search notes or claims | User must switch to Claude Code for any vault query |
| Skill routing relies on regex + intent extraction hacks | Fragile, no structured output, hard to extend |
| No way to look up specific claims or hypotheses | Bot can only speak in generalities about research goals |

Tool calling solves all four by letting Claude decide when to call a vault function and how to interpret the structured result.

---

## Architecture

### Current flow

```
Slack message -> build_thread_context() -> build_system_prompt() -> messages.create() -> text response -> say()
```

### Proposed flow

```
Slack message -> build_thread_context() -> build_system_prompt()
  -> messages.create(tools=VAULT_TOOLS)
  -> while response has tool_use blocks:
       execute tool -> append tool_result -> messages.create(tools=VAULT_TOOLS)
  -> final text response -> say()
```

### Key decision: tool execution happens in-process

Tools are Python functions that read vault state. No shell calls, no subprocess, no Claude Code invocation. The bot process already has filesystem access to the vault. Tools are read-only by default; mutative tools require the existing confirmation flow.

---

## Tool Catalog

### Phase 1 -- Read-only (no confirmation needed)

| Tool name | Description | Parameters | Returns |
|-----------|-------------|------------|---------|
| `search_notes` | Full-text search across notes/ | `query: str`, `limit: int = 10` | List of `{title, description, path}` |
| `get_note` | Read a specific note by title or path | `title: str` | `{frontmatter, body}` |
| `vault_stats` | Current vault metrics | (none) | `{note_count, hypothesis_count, inbox_count, queue_depth}` |
| `queue_status` | Processing queue state | (none) | `{pending, in_progress, completed_today}` |
| `list_goals` | Active research goals | (none) | List of `{name, scope, status}` |
| `search_hypotheses` | Search hypotheses by keyword | `query: str` | List of `{title, elo, status}` |
| `get_reminders` | Active reminders | (none) | List of `{text, due}` |

### Phase 2 -- Mutative (requires confirmation)

| Tool name | Description | Parameters |
|-----------|-------------|------------|
| `create_reminder` | Add a reminder to ops/reminders.md | `text: str`, `due: str` |
| `queue_skill` | Queue a skill for daemon execution | `skill: str`, `args: str` |

Mutative tools reuse the existing `_handle_skill_request` confirmation flow. When Claude returns a mutative tool_use block, the bot asks for confirmation before executing.

---

## Implementation Plan

### 1. Define tool schemas

New file: `_code/src/engram_r/slack_tools.py`

```python
VAULT_TOOLS = [
    {
        "name": "search_notes",
        "description": "Search vault notes by keyword. Returns matching note titles, descriptions, and paths.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results", "default": 10},
            },
            "required": ["query"],
        },
    },
    # ... remaining tools
]
```

### 2. Implement tool executors

Same file. Each tool is a function `(vault_path: Path, **params) -> dict`:

```python
def execute_tool(vault_path: Path, tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call and return JSON result string."""
    executors = {
        "search_notes": _search_notes,
        "get_note": _get_note,
        "vault_stats": _vault_stats,
        "queue_status": _queue_status,
        "list_goals": _list_goals,
        "search_hypotheses": _search_hypotheses,
        "get_reminders": _get_reminders,
    }
    fn = executors.get(tool_name)
    if fn is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})
    try:
        result = fn(vault_path, **tool_input)
        return json.dumps(result, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
```

### 3. Modify `_call_claude` to handle tool use loop

```python
def _call_claude(self, messages, system) -> str:
    response = self.anthropic_client.messages.create(
        model=self.config.model,
        max_tokens=self.config.max_response_tokens,
        system=system,
        messages=messages,
        tools=VAULT_TOOLS,
    )

    # Tool use loop (max 5 iterations to prevent runaway)
    iterations = 0
    while response.stop_reason == "tool_use" and iterations < 5:
        iterations += 1
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(
                    self.config.vault_path, block.name, block.input
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages = messages + [
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ]
        response = self.anthropic_client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_response_tokens,
            system=system,
            messages=messages,
            tools=VAULT_TOOLS,
        )

    # Extract final text
    return "\n".join(b.text for b in response.content if hasattr(b, "text"))
```

### 4. Update system prompt

Remove the `<skill-intent>` detection block. Replace with natural language guidance:

> You have access to vault tools. Use them to answer questions about notes, hypotheses, goals, and queue state. Do not guess -- look it up.

### 5. Deprecate intent extraction

The `slack_skill_router.extract_skill_intent()` regex hack becomes unnecessary for read operations. Keep `detect_explicit_command()` for `/command` syntax as a shortcut, but tool calling handles the semantic routing.

### 6. Tests

- Unit tests for each tool executor with a fixture vault
- Integration test for the tool use loop with a mocked Anthropic client
- Regression test: existing skill routing still works for mutative commands

---

## Configuration

Add to `ops/daemon-config.yaml` under `bot:`:

```yaml
bot:
  tool_calling:
    enabled: true
    max_iterations: 5        # tool use loop cap
    read_tools: true         # phase 1
    mutative_tools: false    # phase 2, off by default
```

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Tool use loop runs away (cost) | Hard cap at 5 iterations per message |
| Tool returns too much data (token bloat) | Truncate tool results to 4000 chars, limit search results |
| Mutative tools executed without confirmation | Mutative tools gated behind existing confirmation flow + config flag |
| Latency increase from multi-turn API calls | Acceptable for Slack (users expect ~3-5s); can add typing indicator |
| Search quality depends on simple text matching | Start with filename + frontmatter search; upgrade to embeddings later if needed |

---

## Out of Scope

- Embedding-based semantic search (future enhancement, separate doc)
- Running full skills (reduce, reflect) via tool calling (too complex, keep in daemon)
- Multi-modal tools (image/plot generation via Slack)

---

## Success Criteria

- Bot can answer "how many notes do I have?" without stale cached stats
- Bot can answer "what claims do I have about p-tau217?" with actual search results
- Bot can answer "what's in my queue?" with live queue state
- No regression in existing skill routing for mutative commands
- Tool use adds < 3s average latency to responses
