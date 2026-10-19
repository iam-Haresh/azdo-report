# Concepts

[Report guide](README.md) › Concepts

These terms appear in many columns. Settings in `code` live in `config.yaml`, and rule files are under `rules/`.

## Inventory vs deep mode

| | `inventory` | `analyze -p <project>` (deep) |
|---|---|---|
| Repos, branches, open PRs, branch policies | yes | yes |
| Pipeline and release definitions | list form | full form, one call each |
| Run and deployment history | yes | yes |
| Variable groups, secure files, service connections, agent pools | yes | yes |
| Tags, task groups, timeline of each pipeline's last good run | no | yes |
| Environments, checks, deployment groups, pipeline authorizations, connection execution history, required-reviewer names | no | yes |
| Repo clones (depth 1) and file scan, YAML template resolution | no | yes |

- Columns filled only in deep mode are marked **(deep only)** in these guides. In an inventory run they are blank or 0.
- The **Depth** column on the Pipelines and Releases sheets shows what a row is based on:
  - `deep`: the full definition was read.
  - `inventory`: list data only, so YAML templates are not resolved and classic task groups are not expanded.

## Time windows

| Setting | Default | Used for |
|---|---|---|
| `collection.history_days` | 180 | which runs and deployments are fetched; all run statistics |
| `analysis.active_days` | 90 | the Active status |
| `analysis.dormant_days` | 365 | Dormant vs Dead; stale branches |

- "Last run" and "last release" dates come from each definition, so `history_days` doesn't limit them.
- "Runs 90d" always means the last 90 days.

## Activity status

Each repo gets the most recent of these dates: its last commit on any branch, the last run of its pipelines, the last deployment of its releases, and (for template repos) the last run of the pipelines that use them.

| Status | Meaning |
|---|---|
| Active | most recent activity within `analysis.active_days` |
| Dormant | within `analysis.dormant_days` |
| Dead | older than that |
| Never | no activity found at all |
| Disabled | the repo is disabled in Azure DevOps |

Pipelines and releases get their own status from their last run or deployment. The full rules are in the main [README](../../README.md#how-activity-is-calculated).

## Complexity score

1. **Per pipeline:** a base value for its kind, plus points for each feature found. The values come from `rules/scoring.yaml`.
2. **Per repo:** the highest score among the repo's pipelines and releases, plus repo-level points.
3. **Level:** 0–3 is Low, 4–8 Medium, 9+ High (`thresholds` in `scoring.yaml`).
4. **Blocker:** the repo has at least one blocker-severity finding, such as TFVC. It doesn't add points.
5. **Overrides:** `overrides.yaml` can set `complexity` per repo. The Complexity column then shows your value, while Score still shows the computed points.

| Points | When |
|---|---|
| base 0 / 4 / 4 | YAML / classic build / classic release |
| +3 | 2 or more deployment stages |
| +1 each, max +3 | every deployment stage beyond the third |
| +2 | manual approvals (classic) or approval checks (environments, connections, variable groups) |
| +3 | gates, or checks other than approvals |
| +1 | manual intervention / manual validation steps |
| +3 | deployment-group jobs |
| +2 each, max +8 | tasks with no entry in `rules/task_mapping.yaml` |
| +1 each, max +3 | mapped tasks that come from extensions |
| +1 each, max +3 | classic task groups |
| +2 | Windows-only toolchain |
| +2 | uses a Key Vault-linked variable group |
| +1 each, max +3 | secure files |
| +1 | templates or checkouts from other repos |
| +2 | triggered by another pipeline |
| +1 | `##vso[...]` commands in the pipeline's own scripts or task inputs |
| +2 | `System.AccessToken` in the pipeline's own scripts, inputs or variables |
| +1 | config transforms or token replacement |
| +1 | conditional / dynamic YAML template logic |
| +2 | templates that could not be resolved |
| +1 | settings defined outside the YAML file (UI variables, UI trigger overrides) |
| +1 | checks out more than one repo |
| repo +1 / +1 / +2 | submodules / LFS / repo bigger than half the GitLab size limit |

## Archetype key

A repo's archetype has six dimensions. Each one can hold several values, joined with ", " in the reports. [Archetype values](archetype-values.md) lists every value and how it is found.

| Dimension | Answers | Examples | In the key |
|---|---|---|---|
| Stack | what the code is | `java-maven`, `dotnet`, `angular`, `terraform` | 1st part |
| Build tools | how it is built | `maven`, `npm`, `docker`, `msbuild` | 2nd part |
| Test & scan tools | which tests and scanners run | `sonarqube`, `karma`, `vstest` | no |
| Deploy targets | where it is deployed | `kubernetes`, `iis`, `azure-app-service` | 3rd part |
| Artifacts | what it produces | `image`, `nuget-package`, `files` | 4th part |
| Markers | other notable files and frameworks | `docker`, `helm`, `spring-boot`, `jenkinsfile` | no |

The key is `stacks | build tools | deploy targets | artifacts`, for example `dotnet, angular | dotnet, npm | iis | files`. An empty part shows `unknown` for the stack and `none` for the others. Values always appear in the order of `rules/archetypes.yaml`, so the same combination always gives the same key.

How values are found (rules in `rules/archetypes.yaml`):
- **Repo files** (deep runs): file names anywhere in the repo, sometimes with a content check.
  - `angular.json` gives `angular`.
  - A `*.csproj` targeting `net48` gives `dotnet-framework`, one targeting `net8.0` gives `dotnet`, and a multi-targeted `net48;net8.0` gives both.
  - Folders such as `node_modules`, `bin`, `obj`, `packages` and `vendor` are ignored.
- **The build pipelines and classic releases that use the repo:**
  - task names and task inputs: HelmDeploy with `command: upgrade` gives deploy target `kubernetes`; with `command: package` it gives artifact `helm-chart`.
  - commands in inline scripts and task inputs, such as `kubectl apply` or `./mvnw deploy`. `echo` / `Write-Host` lines and comments are ignored.
  - repo script files that a pipeline calls by name, such as `ci/deploy.sh`.
  - service connection types and deployment-group jobs.
- **Replacements:** a specific value replaces a generic one. A front-end framework replaces `node`, `android` replaces `java-gradle`, and `azure-app-service` replaces `azure`.
- **Fallback stacks** (`container`, `helm-charts`, `kubernetes-manifests`, `scripts`, `sql-scripts`) appear only when no other stack is found.
- **Assumed build tool:** when no build step builds a stack, its usual tool is assumed, for example `npm` for Angular.
- **No repo files** (inventory runs, or a repo that was not cloned): the stack is inferred from the build tools, for example VSBuild gives `dotnet-framework` and Maven gives `java-maven`.
- Repos used only for YAML templates by other pipelines get the stack `azdo-yaml-templates`.
- The repo's [dossier](repo-dossier.md) shows the evidence for every value: the file, task or script line that matched.

### Named archetypes

The `named:` entries in `rules/archetypes.yaml` give combinations a friendly name and a proposed shared GitLab template. Each entry has conditions (stack, and optionally build tools, test & scan tools, deploy targets, artifacts or markers). All the listed values must be present; `none` means that dimension is empty.

A repo's names are chosen like this:
1. Keep the entries whose conditions all match.
2. Rank them: entries naming more stacks first, then entries with more conditions, then the order in the file.
3. Take entries in that order, skipping an entry if one of its stacks already has a name.

So a repo gets one name per stack, unless one entry names several stacks together. Examples:
- `dotnet, angular` is named "ASP.NET Core + Angular", because that entry names both stacks.
- `java-maven` with an image deployed to Kubernetes is named "Java/Maven -> container -> Kubernetes", because that entry beats the plain "Java/Maven" one.
- `terraform, ansible` is named "Terraform / IaC, Ansible".

`also_covers` lets an entry stand for the platform stacks it brings along. "React Native app", for example, also covers `android` and `ios`, so those don't get names of their own. Every stack has an entry with only `stack:`, so every combination gets a name. Nothing matches only when no stack is recognised, and then the name is `custom`.

- **Proposed template:** the templates of the chosen entries.
- `overrides.yaml` (`archetype`, `template`) replaces the computed values in the Tracker and the dossiers.

## Pipeline fingerprint and clones

- **Fingerprint:** a 10-character code computed from the pipeline kind and its ordered list of tasks (`Name@major`).
  - YAML `checkout`, `download` and `publish` shortcuts are ignored.
  - It is blank when the pipeline has fewer than two tasks.
- **Identical clones:** pipelines with the same fingerprint.
- **Similar clones:** pipelines of the same kind sharing at least 80% of their tasks (by set overlap). Only pipelines that aren't already identical clones are checked.
- Clones are good candidates for one shared GitLab template.

## Severity

`blocker` > `high` > `medium` > `low` > `info`.

- A **blocker** must be solved before the repo can move; TFVC and a repo over the GitLab size limit are examples.
- Each finding's severity is set in `rules/findings.yaml` and can be changed there.

## GitLab path

`<project slug>/<repo slug>`, relative to the GitLab group you migrate into. Each slug is built like this:

1. Lower-case the name.
2. Change every run of characters other than letters, digits, `_`, `-` and `.` to a single `-`.
3. Collapse repeated `-`, then trim `-`, `_` and `.` from both ends.
4. If the result ends in `.git` or `.atom`, that ending is replaced by `-repo`.

`(slug collision!)` means another repo in the same project produces the same path.

## Internal host

A host name that matches one of the `analysis.internal_host_patterns`, such as `*.local`, `10.x.x.x` or a single-word name like `buildserver`. GitLab.com's hosted runners cannot reach such hosts. Deployment groups always count as internal.

## How values are shown

- `yes` / `no` mean true / false. Blank means not available, for example deep-only data in an inventory run.
- Lists are comma-separated, without duplicates. Long lists end with `… (+N)`, where N is the number of further items.
- Dates are UTC; the workbook shows them as `yyyy-mm-dd`.
- Values come from the raw cache in `out/raw/`. A rerun without `--refresh` reuses that data; "Data as of" on the Summary sheet tells you when it was fetched.
