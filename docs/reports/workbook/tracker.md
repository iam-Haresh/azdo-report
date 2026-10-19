# Tracker sheet

[Report guide](../README.md) › [Workbook](README.md) › Tracker

**One row per:** repo, including disabled ones.
**Use it to:** plan migration waves and track progress. This is the checklist's tracker table, filled in for you.
**Modes:** inventory and deep. The Dossier link exists only after a deep `analyze`.

## How repos and pipelines are linked

- A **build/YAML pipeline** belongs to the repo named in its definition (the repository it builds).
- A **classic release** has no repo of its own. It belongs to the repos of the build pipelines whose artifacts it deploys, or to a repo it uses directly as a Git artifact.
- A repo whose only use is providing **YAML templates** (or being checked out by another pipeline) is linked to the pipelines that use it.

## Columns

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Repo | repository name | `git/repositories` |
| GitLab path | proposed path inside your GitLab group; `(slug collision!)` if another repo gets the same path | [GitLab path](../concepts.md#gitlab-path) |
| Archetype | named archetype, for example ".NET Framework -> IIS (Windows)". A repo with several stacks can have several names, comma-separated | `overrides.yaml` → `archetype`, else the [named archetypes](../concepts.md#named-archetypes) of the repo (or `custom`) |
| Pipeline type | the kinds of linked pipelines: `YAML`, `Classic build`, `Classic release` | see "How repos and pipelines are linked"; `templates for <pipeline>` for template-only repos; `none` when nothing is linked |
| Build pipelines | number of build/YAML pipelines that build this repo | pipeline definition → repository |
| Releases | number of classic releases that deploy this repo | release artifacts → build pipeline → repository, or a Git artifact |
| Complexity | Low, Medium or High | `overrides.yaml` → `complexity`, else the level of Score |
| Score | complexity points | highest score among the repo's pipelines and releases, plus repo points (submodules +1, LFS +1, size over half the GitLab limit +2) ([details](../concepts.md#complexity-score)); not changed by an override |
| Blocker | `yes` if anything blocks the migration | at least one blocker-severity finding on the repo or its pipelines/releases |
| Blocker/high findings | IDs of the blocker and high findings | same findings as Blocker (first 6 IDs, then `… (+N)`); details on the [Findings sheet](findings.md) |
| Activity | Active, Dormant, Dead, Never or Disabled | [activity status](../concepts.md#activity-status) |
| Recommendation | what to do with the repo | `overrides.yaml` → `recommendation`, else Active → Migrate, Dormant → Review with owner, Dead/Never → Archive / retire, Disabled → Skip (disabled) |
| Template | proposed shared GitLab templates, comma-separated | `overrides.yaml` → `template`, else the named archetypes' `template` |
| Wave | migration wave | `overrides.yaml` → `wave` |
| Owner | owning team or person | `overrides.yaml` → `owner` |
| Status | progress | `overrides.yaml` → `status`; `Not started` if not set |
| Notes | free text | `overrides.yaml` → `notes` |
| Dossier | link to the repo's dossier file | `dossiers/<project>/<repo>.md` (deep `analyze` only) |

## Tips

- Filter **Activity = Active** and **Blocker = (blank)**, then sort by **Score** ascending, to find the easiest first wave.
- Wave, Owner, Status and Notes come only from `overrides.yaml`. Typing them into the workbook doesn't stick, because every run regenerates it.
