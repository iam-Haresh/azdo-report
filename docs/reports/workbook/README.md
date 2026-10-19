# Workbook guide

[Report guide](../README.md) › Workbook

`out/reports/<date>/azdo-analysis-<label>.xlsx` has one table per sheet. Every table can be filtered and sorted with the arrows in its header row, and the header stays visible while you scroll.

## Sheets

| Sheet | One row per | Guide |
|---|---|---|
| Summary | project, plus three short top-N lists | [summary.md](summary.md) |
| Tracker | repo: the migration plan | [tracker.md](tracker.md) |
| Repos | repo: repository details | [repos.md](repos.md) |
| Pipelines | build or YAML pipeline | [pipelines.md](pipelines.md) |
| Releases | classic release definition | [releases.md](releases.md) |
| Release Stages | deployment stage (classic or YAML) | [release-stages.md](release-stages.md) |
| Tasks | task used by any pipeline | [tasks.md](tasks.md) |
| Variables | variable (pipeline, stage, job or group) | [variables.md](variables.md) |
| Variable Groups | variable group | [variable-groups.md](variable-groups.md) |
| Service Connections | service connection | [service-connections.md](service-connections.md) |
| Secure Files | secure file | [secure-files.md](secure-files.md) |
| Agents & Pools | agent in a self-hosted pool | [agents-and-pools.md](agents-and-pools.md) |
| Environments & Deploy Groups | YAML environment or deployment group | [environments-and-deploy-groups.md](environments-and-deploy-groups.md) |
| Branch Policies | branch policy and the branch it applies to | [branch-policies.md](branch-policies.md) |
| Dependencies | link between two items (repo, pipeline, resource) | [dependencies.md](dependencies.md) |
| Findings | migration risk found | [findings.md](findings.md) |
| Archetypes | archetype key; second table: pipeline clones | [archetypes.md](archetypes.md) |
| Coverage | API endpoint the tool called | [coverage.md](coverage.md) |

## Colours

| Column | Colours |
|---|---|
| Complexity | Low green · Medium yellow · High red |
| Activity | Active green · Dormant yellow · Dead / Never red · Disabled grey |
| Severity | blocker dark red · high red · medium yellow · low blue · info grey |
| Coverage → Status | OK / CACHED green · NOT_FOUND / MISSING_OFFLINE yellow · FORBIDDEN red · ERROR dark red |
| Tasks → Mapped, Variables → Valid GitLab key | yellow when `no` |
| Service Connections → Internal host | yellow when `yes` |

## Links

- **Pipelines → URL** and **Releases → URL** open the definition in Azure DevOps. **Repos → Web URL** opens the repo.
- **Tracker → Dossier** opens the repo's dossier file. It is a relative link, so keep the workbook in its report folder.

## Your own notes

The workbook is regenerated on every run, so edits made in it are lost. Put Wave, Owner, Status, Notes and any archetype or complexity overrides in `overrides.yaml` instead.
