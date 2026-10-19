# Repos sheet

[Report guide](../README.md) › [Workbook](README.md) › Repos

**One row per:** Git repository, including disabled and hidden ones.
**Use it to:** check repo health before moving it: size, branches, open PRs, files that reference Azure DevOps.
**Data:** `git/repositories`, `…/stats/branches`, `…/pullrequests`, `…/refs`, plus the clone (deep) for the file columns.

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Repo | repository name | `git/repositories` |
| Default branch | the repo's default branch | the repo's `defaultBranch`, without `refs/heads/` |
| Size MB | repo size as Azure DevOps reports it | the repo's `size` in bytes ÷ 1,048,576; compare with the GitLab.com 10 GB limit |
| Disabled | `yes` if the repo is disabled | the repo's `isDisabled` flag |
| Fork | `yes` if the repo is a fork | the repo's `isFork` flag |
| Branches | number of branches | `git/repositories/{id}/stats/branches` |
| Stale branches | branches with no commit for `analysis.dormant_days` | each branch's latest-commit date |
| Branching model | guessed from branch names | `develop` + `release/*` or `hotfix/*` → GitFlow · `develop` only → develop + main · `release/*` → trunk + release branches · one branch → single branch · otherwise trunk-based (+ feature branches) |
| Tags | number of tags **(deep only)** | `git/repositories/{id}/refs?filter=tags/` |
| Last commit | newest commit on **any** branch | latest committer date (author date as fallback) across all branches ([details](../../../README.md#how-activity-is-calculated)) |
| Open PRs | active pull requests | `git/repositories/{id}/pullrequests?searchCriteria.status=active` |
| Oldest PR days | age of the oldest open PR, in days | each open PR's creation date |
| Stack | language/platform | first part of the [archetype key](../concepts.md#archetype-key) |
| Build tool | main build tool | second part of the archetype key |
| Deploy targets | where it deploys | third part of the archetype key; `none` if no deployment was found |
| Artifact | what the build produces | fourth part of the archetype key: `image`, `package`, `chart`, `files` or `none` |
| LFS | `yes` if Git LFS is used **(deep only)** | `.gitattributes` lines containing `filter=lfs` |
| Submodules | `yes` if the repo has submodules **(deep only)** | `.gitmodules` |
| Azure Artifacts feeds | feeds the repo's config files point to **(deep only)** | URLs containing `/_packaging/<feed>` in `nuget.config`, `.npmrc`, `settings.xml`, `pom.xml`, `pip.conf`, `build.gradle` and the other files listed under `feed_files` in `rules/scan_patterns.yaml` |
| AZDO URL hits | hard-coded Azure DevOps URLs in the repo's files **(deep only)** | the `AZDO_URL` pattern in `rules/scan_patterns.yaml`, plus your server's host name; the same URL in the same file counts once |
| ##vso hits | `##vso[...]` logging commands in the repo's files **(deep only)** | the `VSO_LOGGING_CMD` pattern |
| Content | how the files were scanned | `clone`: full scan of the shallow clone · `tree`: repo bigger than `collection.clone.max_repo_mb`, so only key files (feed configs, Dockerfiles, `.gitmodules`, `.gitattributes`, project files) were read through the API · `not scanned`: inventory run, `--no-clone`, empty or disabled repo, or the clone failed |
| Web URL | link to the repo in Azure DevOps | the repo's `webUrl` |

## Notes

- The file scan skips binary files, files over 512 KB, lock files, and folders such as `node_modules`, `bin`, `obj` and `.git`. The size limit and the skipped file types are set in `rules/scan_patterns.yaml`; the skipped folders are fixed in the code.
- Every file scan hit becomes a finding on the [Findings sheet](findings.md) with the file names. The repo's [dossier](../repo-dossier.md) shows file and line.
