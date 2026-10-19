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

The key has four parts: `stack | build tool | deploy target(s) | artifact`. All rules are in `rules/archetypes.yaml`.

- **Stack:** the first entry under `stacks:` that matches the repo's file names.
  - For example `pom.xml` gives `java-maven`, and `*.csproj` targeting `net4x` gives `dotnet-framework`.
  - Without files (inventory runs, or a repo not cloned), it is inferred from the build tool. If neither works, it is `unknown`.
- **Build tool:** taken from the tasks (Maven → `maven`, VSBuild → `msbuild`, and so on).
  - The most specific wins, in this order: maven, gradle, ant, msbuild, dotnet, npm, python, go, terraform, nuget, docker.
  - Without a build task it falls back to the stack's default tool, otherwise `none`.
- **Deploy target(s):** every rule under `deploy_targets:` whose tasks, connection types, deployment-group use or script commands match.
  - For example HelmDeploy gives `kubernetes`, the IIS tasks give `iis`, and deployment-group jobs give `windows-vm`.
  - Several targets are joined with `+`. `none` means no deployment was found.
- **Artifact:** the first rule under `artifact_rules:` that matches:
  - `image`: Docker tasks, a Dockerfile, or `docker`/`podman`/`buildah` build/push in scripts
  - `package`: pack, push, publish or deploy with NuGet, dotnet, npm, Maven or Universal Packages
  - `chart`: a `Chart.yaml`
  - `files`: published or archived build artifacts
  - `none`: nothing matched
- **Named archetype:** the first entry under `named:` that matches the key, otherwise `custom`. Repos used only for YAML templates are named "AZDO YAML template repository".
  - **Proposed template:** the template name in that entry.
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
