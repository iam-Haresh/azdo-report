# Summary sheet

[Report guide](../README.md) › [Workbook](README.md) › Summary

**What it is:** the first sheet. It has run details at the top and four small tables.
**Use it to:** get the headline numbers, see the most common problems, and see which tasks and archetypes to tackle first.

## Run details (top of the sheet)

| Field | What it shows |
|---|---|
| Generated | when this report was produced (UTC) |
| Collection | `azdo.collection_url`, or "(offline)" if none is configured |
| GitLab target tier | `analysis.gitlab_tier` |
| Projects | the projects in this report |
| Activity windows | the Active and Dormant thresholds and the run-history window used |

## Projects table (one row per project)

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project name | Projects API |
| Mode | `deep` or `inventory` | how the project's data was collected ([concepts](../concepts.md#inventory-vs-deep-mode)) |
| Repos | number of Git repos, including disabled and hidden ones | `git/repositories?includeHidden=true` |
| Active | repos with recent activity | [activity status](../concepts.md#activity-status) |
| Dormant | repos with no activity within `active_days` but some within `dormant_days` | activity status |
| Dead | repos whose status is Dead or Never | activity status |
| Disabled | repos disabled in Azure DevOps | the repo's `isDisabled` flag |
| YAML | YAML pipeline definitions | build definitions with process type 2 |
| Classic build | classic (designer) build definitions | the other build definitions |
| Classic release | classic release definitions | release definitions |
| Low | repos at this complexity level (disabled repos excluded; a complexity override counts if set) | [complexity score](../concepts.md#complexity-score) |
| Medium | same, Medium | complexity score |
| High | same, High | complexity score |
| Blocker findings | blocker-severity findings in the project | [Findings sheet](findings.md) |
| High findings | high-severity findings in the project | Findings sheet |
| TFVC | `yes` if the project uses TFVC | TFVC changesets under `$/<project>`, or the project's version-control settings |
| Data as of | when the data was fetched from Azure DevOps | the raw cache; earlier than "Generated" when a cached run is reused |

## Findings by type

One row per finding ID across all projects, sorted by severity and then by count.

| Column | What it shows | Derived from |
|---|---|---|
| Finding | finding ID, for example `UNMAPPED_TASK` | [findings catalogue](findings.md#catalogue) |
| Severity | blocker, high, medium, low or info | `rules/findings.yaml` |
| Title | short description | `rules/findings.yaml` |
| Count | how many times it was found | Findings sheet |

## Top unmapped tasks

Up to 15 tasks that pipelines use but `rules/task_mapping.yaml` doesn't cover yet, most used first. YAML shortcuts such as `script` are left out. Adding mappings for these gives the biggest win.

| Column | What it shows | Derived from |
|---|---|---|
| Unmapped task | task as `Name@major`, for example `WhiteSource@21` | [Tasks sheet](tasks.md) |
| Source | `builtin`, `extension` or `unknown` | Tasks sheet |
| Uses | number of steps using it | Tasks sheet |
| Pipelines | number of pipelines/releases using it | Tasks sheet |

## Top archetypes

Up to 10 archetype keys, by number of repos.

| Column | What it shows | Derived from |
|---|---|---|
| Archetype | the key `stack \| build \| deploy \| artifact` | [archetype key](../concepts.md#archetype-key) |
| Name | named archetype, or `custom` | `rules/archetypes.yaml` → `named:` |
| Repos | repos with this key | [Archetypes sheet](archetypes.md) |
