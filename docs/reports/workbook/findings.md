# Findings sheet

[Report guide](../README.md) › [Workbook](README.md) › Findings

**One row per:** migration risk found on a project, repo, pipeline or release.
**Use it to:** see what blocks or complicates each migration, and what to do about it.
**Data:** derived by `azdo-analyzer` from all the collected data. Severity, title and remediation text come from `rules/findings.yaml` and can be edited there.

| Column | What it shows | Derived from |
|---|---|---|
| Severity | blocker, high, medium, low or info | `rules/findings.yaml` ([severity](../concepts.md#severity)) |
| ID | finding type, see the catalogue below | detection rules in the code |
| Title | short description | `rules/findings.yaml` |
| Project | Azure DevOps project | where it was found |
| Repo | repo it applies to; blank for project-level findings | where it was found |
| Pipeline | pipeline or release it applies to; blank when it comes from the repo's files or settings, or the project | where it was found |
| Detail | the evidence: names, files, counts | collected data |
| Remediation | what to do in GitLab | `rules/findings.yaml` |

Rows are sorted by severity, then project, repo and pipeline.

## Catalogue

"(deep)" means the finding needs data from a deep `analyze`.

### Repository

| ID | Severity | Raised when |
|---|---|---|
| `REPO_SIZE` | high (blocker when over the limit) | repo size is over half of `analysis.gitlab_repo_limit_gb`; blocker when over the full limit |
| `LFS` | low | `.gitattributes` uses `filter=lfs` (deep) |
| `SUBMODULES` | medium | `.gitmodules` lists submodules (deep) |
| `OPEN_PRS` | low | the repo has active pull requests |
| `NO_PIPELINE` | info | no pipeline, release or template use is linked to the repo (not raised for disabled repos) |
| `DORMANT` | info | repo status is Dormant, Dead or Never |
| `BRANCH_POLICIES` | low | branch policies apply to the repo |
| `ULTIMATE_ONLY` | medium | a "Status" branch policy applies and `analysis.gitlab_tier` isn't `ultimate` |
| `FEED_DEPENDENCY` | high | a feed config file points to an Azure Artifacts feed (deep) |
| `STATUS_BADGE` | low | files contain Azure DevOps status-badge URLs (deep) |

### Scripts and files

These are raised on the repo when found in its files (deep), and on a pipeline when found in its own inline scripts, task inputs or variables.

| ID | Severity | Raised when |
|---|---|---|
| `AZDO_URL` | medium | hard-coded Azure DevOps URLs (the scan patterns plus your server's host name) |
| `VSO_LOGGING_CMD` | medium | `##vso[...]` logging commands, such as `task.setvariable` or `build.updatebuildnumber` |
| `ACCESS_TOKEN` | high | `System.AccessToken` or `SYSTEM_ACCESSTOKEN` |
| `PREDEFINED_VARS` | low | Azure DevOps predefined variables such as `$(Build.SourcesDirectory)` or `BUILD_BUILDID` (environment forms only when they map to a known variable) |

### Pipelines and releases

| ID | Severity | Raised when |
|---|---|---|
| `WINDOWS_TOOLCHAIN` | high | Windows-only tasks, a Windows image or demand (msbuild, visualstudio, …), or a pool whose agents are all Windows. On a repo: stacks that need Windows (.NET Framework, WPF / WinForms, SSIS, ... : `windows: true` in `rules/archetypes.yaml`), if no pipeline already raised it |
| `UNKNOWN_TASK` | high | a task isn't in the server's task catalogue |
| `UNMAPPED_TASK` | medium | tasks with no entry in `rules/task_mapping.yaml` |
| `MARKETPLACE_TASK` | low | tasks that come from extensions |
| `TASK_GROUP` | low | classic task groups are used (deep) |
| `HIDDEN_UI_CONFIG` | high | a YAML pipeline has variables or trigger overrides set in its settings rather than in the file |
| `TEST_FORMAT` | medium | test results are published in a format other than JUnit (VSTest/TRX, NUnit, xUnit, CTest) |
| `CONFIG_TRANSFORM` | medium | File Transform or Replace Tokens tasks, or XML transformation / variable substitution / JSON file inputs |
| `CROSS_PIPELINE_TRIGGER` | medium | the pipeline starts when another pipeline finishes |
| `SCHEDULE` | low | scheduled triggers (pipeline or release stage) |
| `CROSS_REPO` | medium | templates or repositories from other repos, or extra checkouts |
| `UNRESOLVED_TEMPLATE` | medium | a YAML template, or the YAML file itself, couldn't be read |
| `DYNAMIC_TEMPLATES` | low | `${{ if }}` / `${{ each }}` logic is present (only shown when nothing is unresolved) |
| `PR_TRIGGER_IGNORED` | info | YAML `pr:` on an Azure Repos repo, where PR builds come from branch policies |
| `OAUTH_TOKEN_ACCESS` | low | "Allow scripts to access the OAuth token" is on, but no `System.AccessToken` use was found |
| `INTERNAL_TARGET` | high | the pipeline uses a connection to an [internal host](../concepts.md#internal-host), or a deployment group |
| `ORPHAN` | low | the pipeline's repo is missing or disabled |
| `EXTERNAL_REPO` | info | the pipeline builds a source outside Azure Repos (GitHub, other Git, TFVC) |

### Releases and deployments

| ID | Severity | Raised when |
|---|---|---|
| `DEPLOYMENT_GROUP` | high | deployment-group jobs |
| `APPROVALS` | medium | manual approvals (classic stages), or approval checks on environments, connections or variable groups |
| `GATE` | high | gates, or checks other than approvals (branch control, business hours, …) |
| `MANUAL_INTERVENTION` | low | Manual Intervention / Manual Validation steps |
| `AGENTLESS_JOB` | low | agentless (server) jobs |

### Variables and secrets

| ID | Severity | Raised when |
|---|---|---|
| `KEYVAULT` | high | the pipeline uses a Key Vault-linked variable group |
| `SECURE_FILE` | medium | the pipeline references secure files |
| `SECRETS_TO_REENTER` | medium | the pipeline has secret variables, which can't be exported (the detail gives the count) |
| `INVALID_VAR_NAME` | medium | variable names invalid as GitLab keys: in a pipeline, or in a variable group (shown on the project and on the repos using the group) |
| `PLAINTEXT_SECRET` | high | a plain variable whose name looks like a secret, in a pipeline or a variable group |

### Project

| ID | Severity | Raised when |
|---|---|---|
| `TFVC` | blocker | the project has TFVC changesets, or its settings say TFVC is enabled |
| `SERVICE_HOOKS` | low | the project has service hooks (Teams, Slack, web hooks, …) |
| `UNUSED_CONNECTION` | info | a service connection isn't referenced and has no recent executions (deep) |
| `INVENTORY_ONLY` | info | the project was analysed in inventory mode, so step-level findings are missing |
