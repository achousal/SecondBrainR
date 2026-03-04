---
type: "reference"
slug: "{{slug}}"
resource_type: "{{resource_type}}"
scheduler: "{{scheduler}}"
institution: "{{institution}}"
created: "{{date}}"
tags: [compute, "{{slug}}"]
---

# {{cluster_name}} -- Practical Reference

Parent: [[{{institution_slug}}]]

## Access

- Host: `{{hostname}}`
- User: `{{username}}`
- Auth: {{auth_method}}
- Login nodes: {{login_nodes}}
- Support: {{support_contact}}
- Docs: {{docs_url}}

## Filesystem

| Path | Quota | Backup | Purge | Use |
|------|-------|--------|-------|-----|
| {{home_path}} | {{home_quota}} | {{home_backup}} | {{home_purge}} | {{home_use}} |
| {{work_path}} | {{work_quota}} | {{work_backup}} | {{work_purge}} | {{work_use}} |
| {{scratch_path}} | {{scratch_quota}} | {{scratch_backup}} | {{scratch_purge}} | {{scratch_use}} |
| {{project_path}} | {{project_quota}} | {{project_backup}} | {{project_purge}} | {{project_use}} |

- Check quota: `{{quota_command}}`
- Archival: {{archival_method}}
- Transfer: {{transfer_method}}

## {{scheduler_name}} Scheduler

### Commands

| Command | Purpose |
|---------|---------|
{{commands_table}}

### Queues

| Queue | Max Walltime | Notes |
|-------|-------------|-------|
{{queues_table}}

- Default memory: {{default_memory}}
- Walltime format: {{walltime_format}}
- Required flags: {{required_flags}}
- Default allocation: {{default_allocation}}

## Job Templates

### Interactive session

```bash
{{interactive_template}}
```

### Batch script

```bash
{{batch_template}}
```

### GPU job (single GPU)

```bash
{{gpu_template}}
```

## Environment Management

{{environment_section}}

## Resource Inventory

{{resource_inventory}}

## Best Practices

{{best_practices}}
