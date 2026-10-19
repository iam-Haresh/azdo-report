# Releases sheet

[Report guide](../README.md) › [Workbook](README.md) › Releases

**One row per:** classic release definition (Pipelines → Releases in Azure DevOps). YAML deployment stages are part of their YAML pipeline; see [Release Stages](release-stages.md).
**Use it to:** see which releases deploy what, where they need approvals or gates, and how hard they are to rebuild.
**Data:** `release/definitions` (list, plus the full definition in deep mode) and `release/deployments` (history window).

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Release | release definition name | definition `name` |
| ID | definition ID | definition `id` |
| Folder | folder the release is in | definition `path` |
| Enabled | `no` if the definition is disabled or deleted | definition `isDisabled` / `isDeleted` |
| Depth | `deep` or `inventory` | whether the full definition was read ([concepts](../concepts.md#inventory-vs-deep-mode)) |
| Artifacts | what the release deploys, as `alias (type: source)`, for example `_legacy-web-CI (Build: legacy-web-CI)` | definition `artifacts`; types include Build, Git, GitHub, AzureContainerRepository and package feeds |
| Triggers | what creates a release | definition `triggers`: `artifact` (continuous deployment when a new artifact arrives, with branch filters), `release_schedule`, `pull_request`, `container_image`, `package`, `sourceRepo` |
| Stages | number of stages (environments) | definition `environments` |
| Approvals | stages with manual approvals, as `<stage> (pre)` / `<stage> (post)` | each stage's pre/post-deployment approvals, ignoring automatic ones; plus approval checks on connections and variable groups the release uses |
| Gates | enabled gates, as `<stage>: <gate name>` | each stage's pre/post-deployment gates (only when gates are enabled); plus non-approval checks on resources used |
| Deployment groups | deployment groups the release deploys to | stages' deployment-group jobs (shown as `#<id>` when deployment groups couldn't be read) |
| Variable groups | variable groups linked to the release or to its stages | definition and stage `variableGroups` |
| Service connections | connections the release uses | task inputs (stages and gates) containing a connection's ID or name; the connection behind a Key Vault group |
| Distinct tasks | number of different tasks across all stages | as on the [Pipelines sheet](pipelines.md) |
| Unmapped tasks | tasks with no entry in `rules/task_mapping.yaml` | as on the Pipelines sheet |
| Last deployment | most recent release activity | newest of the latest deployment in the history window and the creation date of the latest release |
| Deployments | deployments of any stage in the history window | `release/deployments` since `collection.history_days` ago |
| Activity | Active, Dormant, Dead or Never | from Last deployment ([activity status](../concepts.md#activity-status)) |
| Score | complexity points | [complexity score](../concepts.md#complexity-score) (base 4 for a classic release) |
| Complexity | Low, Medium or High | Score vs the thresholds |
| Score reasons | each contribution to the score | the scoring rules that matched |
| URL | link to the release definition in Azure DevOps | definition web link |

## Notes

- Per-stage detail (triggers, approvers, queue policy, deploy tasks, deployments) is on the [Release Stages sheet](release-stages.md).
- A release is linked to repos through its Build artifacts. See the [Tracker](tracker.md) for how repos and pipelines are linked.
