# Report guide

What `azdo-analyzer` produces, where to find it, and what every column means.

## Where the reports are

Each run writes to `out/reports/<run date>/`:

| File | What it is | Guide |
|---|---|---|
| `azdo-analysis-<label>.xlsx` | The workbook: 18 sheets, one filterable table each | [Workbook guide](workbook/README.md) |
| `dossiers/<project>/<repo>.md` | One migration checklist per repo, pre-filled (deep `analyze` only) | [Repo dossier](repo-dossier.md) |
| `<project>/summary.md` and `<project>/graph.mmd` | One summary page and dependency graph per project | [Project summary](project-summary.md) |
| `diff-<label>.md` | What changed since the previous run | [Changes since last run](changes-since-last-run.md) |

`<label>` depends on the command:
- the project name for `analyze -p <project>`
- `projects` when several projects are analysed together
- `inventory` for `inventory`

## Where to start

| I want to... | Open |
|---|---|
| see every repo with its status, and plan migration waves | [Tracker sheet](workbook/tracker.md) |
| get the headline numbers | [Summary sheet](workbook/summary.md), or the [project summary](project-summary.md) |
| prepare one repo's migration | its [dossier](repo-dossier.md) |
| know what blocks or complicates a migration | [Findings sheet](workbook/findings.md) |
| decide which shared GitLab CI templates to build | [Archetypes](workbook/archetypes.md) and [Tasks](workbook/tasks.md) sheets |
| see which repo uses which pipeline, connection or variable group | [Dependencies sheet](workbook/dependencies.md) |
| plan CI/CD variables and secrets | [Variables](workbook/variables.md), [Variable Groups](workbook/variable-groups.md), [Secure Files](workbook/secure-files.md) |
| plan runners and network access | [Agents & Pools](workbook/agents-and-pools.md), [Environments & Deploy Groups](workbook/environments-and-deploy-groups.md), [Service Connections](workbook/service-connections.md) |
| recreate branch protection in GitLab | [Branch Policies sheet](workbook/branch-policies.md) |
| check whether data is missing because of permissions | [Coverage sheet](workbook/coverage.md) |

## Terms used in many columns

[Concepts](concepts.md) explains:
- inventory vs deep mode, and the time windows
- activity status, complexity score and severity
- archetype key and pipeline fingerprint
- GitLab path and "internal host"
- how lists and empty values are shown
