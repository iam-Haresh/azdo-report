# Repo dossier

[Report guide](README.md) › Repo dossier

**File:** `out/reports/<date>/dossiers/<project>/<repo>.md`. There is one per repo, written by a deep `analyze` only.
**What it is:** the migration checklist ([docs/migration-checklist.md](../migration-checklist.md)) for one repo, with everything Azure DevOps can tell filled in. Hand it to whoever builds that repo's GitLab pipeline.
**How to read it:**
- `[x]` = filled in automatically, with the value after the colon.
- `[ ]` = needs a person; the line says what to check.

## Header

| Item | Derived from |
|---|---|
| Project, GitLab path | Azure DevOps project; [GitLab path](concepts.md#gitlab-path) |
| Generated / Data as of | report time / when the data was fetched (deep or inventory) |
| Archetype, Complexity, Score, Activity, Recommendation, Template, Wave, Owner, Status | same values as the repo's row on the [Tracker sheet](workbook/tracker.md), with `overrides.yaml` applied |
| Archetype key, Score breakdown | the [archetype key](concepts.md#archetype-key), and every contribution to the [score](concepts.md#complexity-score) |
| Archetype table | one row per dimension (Stack, Build tools, Test & scan tools, Deploy targets, Artifacts, Markers): its values, and for each value the evidence that found it, such as `angular.json`, `task Maven@3 in pipeline shop-ci`, or a script line | [archetype key](concepts.md#archetype-key), [Archetype values](archetype-values.md) |
| Notes | `overrides.yaml` → `notes` |
| Blockers / high-severity findings box | the repo's blocker and high findings, including those of its pipelines, releases and variable groups ([Findings](workbook/findings.md)) |

## Sections

| Section | What is filled in | Derived from |
|---|---|---|
| 1. Project level | the project's repo and pipeline counts and TFVC flag; the pipelines and releases linked to this repo; template usage; last commit, last run, last deployment and the resulting activity status | [Summary](workbook/summary.md) / [Tracker](workbook/tracker.md) data; [activity rules](../../README.md#how-activity-is-calculated) |
| 2. Repository | size and LFS; default branch, branch count, stale branches, branching model; branch policies (table, with GitLab equivalents); proposed `CODEOWNERS` from required-reviewer policies; tags; submodules and cross-repo references; open PRs; counts of AZDO URLs, badges, `##vso` commands, `System.AccessToken`, predefined variables and feed configs found in files; PR templates | [Repos](workbook/repos.md) and [Branch Policies](workbook/branch-policies.md) data; file scan of the clone |
| 3. Build pipelines | one block per build/YAML pipeline: type and YAML path; triggers; pool, demands and Windows reasons; toolchain hints; detected build tools, test & scan tools, deploy targets and artifacts produced (as on the Pipelines sheet) (JDK, Maven, Node, .NET, VS versions from task inputs, container images); task counts, unmapped and marketplace tasks; templates (resolved, unresolved, dynamic); build number format; test result formats; quality-gate tasks; published artifacts; caching; matrix, parallel and container jobs; run statistics; variables, groups and parameters; checkout options; settings defined outside the YAML; last good run vs static analysis; normalization warnings; a task table (Task, Uses, Source, GitLab approach, Effort) | [Pipelines](workbook/pipelines.md) and [Tasks](workbook/tasks.md) data |
| 4. Release / deployment pipelines | per classic release: artifact sources, detected build tools, test & scan tools, deploy targets and artifacts produced (as on the Releases sheet), triggers, release name format, deployment groups, approvals and approvers, gates and manual interventions, stage variables and groups, config transforms, process parameters, retention, plus a stage table. For YAML pipelines with deployment stages: a stage table with environments, checks and deployments | [Releases](workbook/releases.md) and [Release Stages](workbook/release-stages.md) data |
| 5. Variables, secrets and connections | variable counts (secret, invalid names); variable groups with proposed level; Key Vault groups; secure files; a variable table (first 150 rows); a service-connection table (type, auth, URL, internal host, last used, GitLab replacement) | [Variables](workbook/variables.md), [Variable Groups](workbook/variable-groups.md), [Service Connections](workbook/service-connections.md), [Secure Files](workbook/secure-files.md) data |
| 6. Artifacts and feeds | Azure Artifacts feeds referenced in config files; other registries (Artifactory, Nexus, …); Dockerfile base images; universal packages and downloads of other pipelines' artifacts | file scan and task inputs |
| 7. Dependencies and integrations | pipelines that trigger this one, and pipelines it triggers; shared template repos; the project's service hooks; AZDO-specific script constructs with file:line | [Dependencies](workbook/dependencies.md) data and file scan |
| 8. Identity and access | approvers (users and groups) that must exist in GitLab | stage approvals and environment approval checks |
| 9. Network and runners | runner OS (Windows and/or macOS, with reasons, or "Linux containers should work"); tools the runner image needs; internal-only targets; AZDO pools used, with peak concurrency and build minutes per month | findings data; [Agents & Pools](workbook/agents-and-pools.md) data for this project |
| 10. Cutover and validation | manual checklist only | — |
| Findings | every finding for this repo: Severity, Finding, Pipeline, Detail, Remediation | [Findings](workbook/findings.md) |
| Dependency graph | Mermaid diagram of the repo, its pipelines and releases, and everything they use | [Dependencies](workbook/dependencies.md) rows for this repo. GitHub, GitLab and VS Code render it, or paste it into https://mermaid.live |

Items that always need a person are left `[ ]`. These include the owner team and criticality, repo permissions, rollback process, audit evidence, secret owners, token expiry dates, target registry, notifications, identity mapping, firewall and the cutover steps.
