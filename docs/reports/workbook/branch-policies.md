# Branch Policies sheet

[Report guide](../README.md) › [Workbook](README.md) › Branch Policies

**One row per:** branch policy and the scope it applies to. A policy that covers several repos or branches appears once per scope.
**Use it to:** recreate branch protection, merge request approvals and push rules in GitLab.
**Data:** `policy/configurations`. Required-reviewer names come from `identities` (deep only; needs the optional Identity (Read) scope).

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Repo | the repo, or `(all repositories)` for project-wide policies | policy scope `repositoryId` |
| Branch | the branch; a trailing `*` means a prefix match (for example `release/*`); `(all branches)` when unscoped | policy scope `refName` and `matchKind` |
| Policy | policy type, as Azure DevOps names it | policy `type.displayName` |
| Enabled | `yes` if the policy is on | policy `isEnabled` |
| Blocking | `yes` = required, `no` = optional | policy `isBlocking` |
| Settings | the policy's settings in short form, for example `min 2; creator vote counts=False; reset on push=True` | policy `settings`, summarised per type. Required reviewers show names when the identity lookup worked, otherwise IDs |
| GitLab equivalent | what to configure in GitLab | the mapping below |

## Policy mapping

| Azure DevOps policy | GitLab equivalent |
|---|---|
| Minimum number of reviewers | approval rule with N approvals (Premium). Creator's vote doesn't count → "Prevent approval by author". Reset votes on push → "Remove all approvals when commits are added" |
| Required reviewers (with path filters) | `CODEOWNERS` entry for the paths + Code Owner approval on the protected branch (Premium) |
| Build (build validation) | merge request pipeline + "Pipelines must succeed"; path filters become `rules:changes` |
| Comment requirements | "All threads must be resolved" |
| Work item linking | issue reference via MR template or push rule (Jira integration) |
| Require a merge strategy | project merge method and squash setting |
| Status | external status check (Ultimate). On Premium the report says to use a pipeline job, and raises `ULTIMATE_ONLY` |
| File size restriction | push rule: maximum file size (Premium) |
| Path length restriction | no direct equivalent (use a CI check) |
| Reserved names restriction / File name restriction | push rule: prohibited file names (Premium) |
| Commit author email validation | push rule: commit author email regex (Premium) |
| any other type | "Review manually" |

## Notes

- Repos covered by any policy get a `BRANCH_POLICIES` finding.
- Required-reviewer policies also appear in the repo's dossier as the proposed `CODEOWNERS` entries.
