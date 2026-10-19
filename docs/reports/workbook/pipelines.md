# Pipelines sheet

[Report guide](../README.md) › [Workbook](README.md) › Pipelines

**One row per:** build pipeline, YAML or classic. Classic releases are on the [Releases sheet](releases.md).
**Use it to:** see what each pipeline does, how often it runs, and how hard it is to rebuild in GitLab.
**Data:** `build/definitions` (list, plus the full definition in deep mode), `build/builds` (run history), the YAML file and its templates (deep), and the timeline of the last good run (deep).
**What the tool identifies:** 158 technology patterns, 32 kinds of findings, 13 trigger types and more; see [What the tool identifies in pipelines and releases](#what-the-tool-identifies-in-pipelines-and-releases).

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
| Repo stack | stacks of the repo the pipeline builds; `unknown` if that repo's stack wasn't recognised; blank if the repo isn't in this project | the repo's Stack on the [Repos sheet](repos.md) |
| Build tools | build tools this pipeline uses, for example `maven, docker`; `none` if none were found **(deep only)** | its own tasks, task inputs, inline scripts and the repo scripts it calls by name, matched with `rules/archetypes.yaml` ([values](../archetype-values.md#build-tools)). This uses the pipeline's own definition only (no repo files, no assumed tools), so its repo can show more values |
| Test & scan tools | test runners and scanners it runs, for example `sonarqube` **(deep only)** | the same signals ([values](../archetype-values.md#test--scan-tools)) |
| Deploy targets | where it deploys (YAML deployment stages), for example `kubernetes` **(deep only)** | the same signals, plus service connection types and deployment-group jobs ([values](../archetype-values.md#deploy-targets)) |
| Artifacts produced | what it publishes, for example `image, files` **(deep only)** | the same signals ([values](../archetype-values.md#artifacts)) |
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

## What the tool identifies in pipelines and releases

The tool recognises 158 technology patterns and 32 kinds of findings in build/YAML pipelines and classic releases, and reads every trigger, stage, approval and gate. The counts come from the rule files in `rules/`, so they grow as you add rules.

| What it identifies | Count | Examples | Full list |
|---|---|---|---|
| Build tools | 50 | Maven, Gradle, MSBuild, dotnet, npm, Docker, Kaniko, Jib, OpenShift S2I | [Archetype values](../archetype-values.md#build-tools) |
| Test & scan tools | 37 | SonarQube, Checkmarx, Fortify, Snyk, Trivy, VSTest, Karma, Cypress | [Archetype values](../archetype-values.md#test--scan-tools) |
| Deploy targets | 56 | Kubernetes, OpenShift, IIS, Windows services, deployment groups, file shares, Tomcat/JBoss/WebLogic, Azure, AWS, Octopus, databases | [Archetype values](../archetype-values.md#deploy-targets) |
| Artifacts | 15 | container image, Helm chart, Maven/NuGet/npm/Python packages, installers, DACPAC | [Archetype values](../archetype-values.md#artifacts) |
| Findings | 32 | Key Vault groups, approvals, gates, `##vso` commands, `System.AccessToken`, TRX results needing JUnit conversion, config transforms, unmapped tasks | [Findings](findings.md) |
| Tasks mapped to a GitLab approach | 115 | each with an image hint and effort level; other tasks are listed by usage | [Tasks](tasks.md), `rules/task_mapping.yaml` |
| Complexity factors | 21 | plus a starting score per pipeline type | [Complexity score](../concepts.md#complexity-score) |
| Trigger types | 13 | 7 for build pipelines ([trigger format](#trigger-format)), 6 for classic releases ([Releases](releases.md#what-the-tool-identifies-in-classic-releases)) | |
| Azure DevOps variables mapped to GitLab `CI_*` variables | 74 | 71 variables plus 3 prefix families such as `Release.Artifacts.*`; e.g. `$(Build.SourcesDirectory)` → `CI_PROJECT_DIR` | `rules/predefined_vars.yaml` |

The build tools, test & scan tools, deploy targets and artifacts are matched through 209 task names, 379 script commands (such as `kubectl apply` or `./mvnw deploy`), 31 script regexes and 9 service-connection types. They describe the repos that the pipelines build, on the [Repos](repos.md) and [Archetypes](archetypes.md) sheets.

**What it reads from each definition (deep `analyze`):**
- **YAML pipelines:**
  - templates, including ones in other repos at the pinned version, and `extends`
  - parameters, `${{ if }}` and `${{ each }}`, and resources (repositories, pipelines, containers, webhooks)
  - deployment strategies (runOnce, rolling, canary, with their lifecycle hooks) and matrix or parallel jobs
  - container and service jobs, checkout options, conditions, `dependsOn`, timeouts and retries
  - variables and trigger overrides set in the UI, plus a check against the tasks of the last successful run
  - checks on the environments that deployment jobs use: approvals, exclusive lock and required template; any other check (business hours, branch control, …) is recorded by name
- **Classic builds:** task groups (expanded recursively, at the version used), secret and queue-time variables, demands, repository options (submodules, LFS, clean, fetch depth), multi-configuration and multi-agent jobs, build number format, job authorization scope and timeout, OAuth token access, retention.
- **Run history:** success rate, typical (p50) and slowest (p95) run time, queue time, trigger reasons, branches built, and peak concurrency per agent pool ([Agents & Pools](agents-and-pools.md)). Pipelines that are identical or at least 80% similar are grouped on the [Archetypes sheet](archetypes.md).

**Limits:**
- **Full detail needs `analyze`.** An `inventory` run reads the definition list and run history only, not the steps.
- **Runtime values aren't evaluated.** The tool can't evaluate `$[ ]` runtime expressions or variables that scripts set while running. Every `${{ if }}` branch is kept and flagged, because it can't tell which one runs.
- **Scripts are matched by command and regex, not understood.** A repo script is searched only when a pipeline calls it by name.
- **Unknown tasks aren't lost.** They are listed on the [Tasks sheet](tasks.md) with their usage, but don't count towards archetypes until you add them to `rules/archetypes.yaml`.
