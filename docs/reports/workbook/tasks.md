# Tasks sheet

[Report guide](../README.md) › [Workbook](README.md) › Tasks

**One row per:** task used by at least one analysed pipeline or release. Only enabled steps count, after inlining YAML templates and expanding task groups.
**Use it to:** know which tasks to replace in GitLab, how hard each one is, and which marketplace tasks need a decision.
**Data:** the steps of every pipeline, the server's task catalogue (`distributedtask/tasks`), and `rules/task_mapping.yaml`.

| Column | What it shows | Derived from |
|---|---|---|
| Task | the task as `Name@major`, for example `Maven@3` | the task ID in classic definitions, or the task name in YAML, resolved through the server's task catalogue. YAML shortcuts appear as `script`, `bash`, `pwsh`, `powershell`, `checkout`, `download` and `publish`. A task group that couldn't be expanded appears as `TaskGroup:<name>` |
| Name | the task's display name | task catalogue `friendlyName`; for YAML shortcuts, the step type |
| Source | where the task comes from | `builtin` (ships with Azure DevOps) · `extension` (an installed marketplace or private extension) · `unknown` (not in the server's catalogue, e.g. the extension was removed) · `yaml` (a YAML shortcut) |
| Extension | the extension that provides the task | `publisher.extension` from the catalogue's contribution ID |
| Uses | number of steps using the task | counted across all analysed pipelines and releases |
| Pipelines | number of pipelines/releases using it | distinct definitions |
| Repos | number of repos those pipelines belong to | pipeline → repo links (see [Tracker](tracker.md)) |
| Mapped | `yes` if a GitLab mapping exists | an entry in `rules/task_mapping.yaml` for `Name@major` or `Name` |
| GitLab approach | how the step is usually done in GitLab CI | mapping `gitlab` |
| Image hint | suggested job image | mapping `image` |
| Effort | low, medium or high | mapping `effort` |
| Windows | `yes` if it needs a Windows runner | mapping `windows: true`, or the task has only Windows PowerShell handlers in the catalogue |
| Category | build, test, quality, artifact, deploy, infra, security, util, approval or toolchain | mapping `category` |
| Notes | gotchas | mapping `notes` |
| Examples | up to 4 pipelines that use the task | the same steps |

## Tips

- Filter **Mapped = no** and sort by **Uses**, then add entries to `rules/task_mapping.yaml`. The next run picks them up, and the complexity score drops (unmapped tasks add +2 each).
- Rows with **Source = unknown** usually mean the pipeline is already broken in Azure DevOps.
