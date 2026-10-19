# Pipelines sheet

[Report guide](../README.md) › [Workbook](README.md) › Pipelines

**One row per:** build pipeline, YAML or classic. Classic releases are on the [Releases sheet](releases.md).
**Use it to:** see what each pipeline does, how often it runs, and how hard it is to rebuild in GitLab.
**Data:** `build/definitions` (list, plus the full definition in deep mode), `build/builds` (run history), the YAML file and its templates (deep), and the timeline of the last good run (deep).

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Pipeline | pipeline name | definition `name` |
| ID | definition ID | definition `id` |
| Kind | `YAML` or `Classic build` | definition process type (2 = YAML) |
| Folder | folder the pipeline is in | definition `path` |
| Repo | repository the pipeline builds | definition `repository` (can be another project's repo, or GitHub/Git/TFVC) |
| YAML path | the YAML file (YAML only) | definition `process.yamlFilename` |
| Enabled | `no` if the pipeline is paused or disabled | definition `queueStatus` |
| Depth | `deep` or `inventory` | whether the full definition was read ([concepts](../concepts.md#inventory-vs-deep-mode)); YAML steps are only known in deep mode |
| Pools | agent pools (queues) the jobs run on, or the hosted image | job pool / queue name, or `vmImage` |
| Demands | capabilities required from the agent, for example `msbuild` | job and definition demands |
| Triggers | what starts the pipeline | see the trigger format below |
| Variable groups | variable groups the pipeline uses | YAML `- group:` at any level; groups linked to a classic definition |
| Service connections | connections the pipeline uses | task inputs containing a connection's ID or name; YAML container and repository resources; the connection behind a Key Vault variable group |
| Steps | number of enabled steps | counted after inlining YAML templates and classic task groups; scripts and checkouts included |
| Distinct tasks | number of different tasks used | distinct `Name@major` among enabled task steps (YAML `script`/`checkout` shortcuts not counted) |
| Unmapped tasks | tasks with no GitLab mapping yet | tasks with no entry in `rules/task_mapping.yaml` |
| Task groups | classic task groups used, including nested ones **(deep only)** | task groups expanded from `distributedtask/taskgroups` |
| Templates | number of YAML template includes resolved **(deep only)** | `template:` and `extends:` references, including other repos at their pinned ref |
| Last run | when the pipeline last ran | newest of the definition's latest build (finish time, or queue time if still running) and the newest run in the history window |
| Runs | completed runs in the history window | `build/builds` since `collection.history_days` ago |
| Runs 90d | completed runs in the last 90 days | same runs |
| Success % | share of runs that passed | (succeeded + partially succeeded) ÷ (succeeded + partially succeeded + failed); canceled runs ignored |
| p50 min | median run duration, in minutes | start → finish of the runs in the window |
| p95 min | 95th-percentile run duration | same |
| Queue p95 min | 95th-percentile time waiting for an agent | queued → started |
| Activity | Active, Dormant, Dead or Never | from Last run ([activity status](../concepts.md#activity-status)) |
| Fingerprint | code shared by pipelines with the same task sequence | [fingerprint](../concepts.md#pipeline-fingerprint-and-clones) |
| Score | complexity points | [complexity score](../concepts.md#complexity-score) |
| Complexity | Low, Medium or High | Score vs the thresholds |
| Score reasons | each contribution to the score, for example `Classic build +4, task groups +2` | the scoring rules that matched |
| Warnings | problems met while reading the definition, for example "task group … not resolved" or "YAML file not found" | normalization |
| URL | link to the pipeline in Azure DevOps | definition web link |

## Trigger format

Each trigger is shown as `<kind> [(UI override)] [from <source>] [branches …] [excl …] [paths …] [schedule] [batched]`.

| Kind | Meaning |
|---|---|
| `ci` | runs on push. A YAML file with no `trigger:` key shows `ci branches *`, which is Azure DevOps' default: every branch |
| `pr` | PR trigger. Azure Repos ignores YAML `pr:`, because PR builds come from [branch policies](branch-policies.md) |
| `schedule` | scheduled run: cron for YAML, days and time for classic |
| `pipeline` | starts when another pipeline finishes (YAML `resources.pipelines`) |
| `build_completion` | the classic equivalent of `pipeline` |
| `gated` | TFVC gated check-in |
| `webhook` | YAML webhook resource |

`(UI override)` means the trigger is set in the pipeline's settings and overrides the YAML file. Look for it: it's invisible in the repo.

## Notes

- **YAML pipelines in inventory mode** show only settings made in the UI. Steps, tasks, templates and groups appear after a deep `analyze`.
- **YAML conditional logic** (`${{ if }}`): every branch is included, so Steps and the task columns can be a superset of what really runs. The repo's [dossier](../repo-dossier.md) shows "Last good run vs static analysis" for each pipeline, comparing these with the tasks that ran.
