# Releases sheet

[Report guide](../README.md) › [Workbook](README.md) › Releases

**One row per:** classic release definition (Pipelines → Releases in Azure DevOps). YAML deployment stages are part of their YAML pipeline; see [Release Stages](release-stages.md).
**Use it to:** see which releases deploy what, where they need approvals or gates, and how hard they are to rebuild.
**Data:** `release/definitions` (list, plus the full definition in deep mode) and `release/deployments` (history window).
**What the tool identifies:** the same 158 technology patterns and 32 kinds of findings as build pipelines, 6 release trigger types, and every stage's approvals, gates and jobs; see [What the tool identifies in classic releases](#what-the-tool-identifies-in-classic-releases).

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

## What the tool identifies in classic releases

Release tasks and scripts are matched with the same 158 technology patterns as build pipelines; for releases, the [deploy targets](../archetype-values.md#deploy-targets) matter most. The same 32 kinds of findings apply, including the release-heavy ones: approvals, gates, manual interventions, agentless jobs, deployment groups, config transforms and internal-only targets. All counts are on the [Pipelines page](pipelines.md#what-the-tool-identifies-in-pipelines-and-releases).

**What it reads from each release definition (deep `analyze`):**
- **Artifact sources** (Build, Git, GitHub, container registries, package feeds), each with its default-version rule and branch, and which one is primary.
- **6 trigger types:** `artifact` (continuous deployment, with branch filters and tags), `release_schedule`, `pull_request`, `container_image`, `package` and `sourceRepo`.
- **Release name format, process parameters, retention**, and whether scripts can use the OAuth token.
- **Stages, in order**, each with:
  - its trigger: after release, after another stage, artifact filters, or manual ([Release Stages](release-stages.md))
  - pre- and post-deployment approvals: who approves, how many, whether the creator can approve, and the timeout
  - gates and their settings (sampling interval, stabilization time, timeout)
  - jobs: agent, deployment group (with tags and parallelism) or agentless (manual intervention, delay, REST call)
  - the tasks of every job, with task groups expanded
  - queue policy (`N at a time, all in sequence`, `N at a time, latest only` or `unlimited parallel`), schedules, stage variables and variable groups
- **Deployment history:** deployments, last deployment and success rate per stage ([Release Stages](release-stages.md)).

**Limits:**
- **Full detail needs `analyze`.** An `inventory` run reads the definition list and deployment history only.
- **Gates and approvals are read, not evaluated.** A gate's success criteria (e.g. what a REST call must return) and approval rules kept outside the definition aren't checked.
- **Runtime values aren't resolved,** such as variables that scripts set while running.
