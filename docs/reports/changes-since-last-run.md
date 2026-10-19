# Changes since last run

[Report guide](README.md) › Changes since last run

**File:** `out/reports/<date>/diff-<label>.md`, written by every run.
**What it is:** a list per project of pipelines and repos added, removed or changed since the previous run. It catches drift during the migration, such as a new pipeline created in Azure DevOps after you analysed the project.

## Contents

| Line | Meaning |
|---|---|
| `_First run for this project - nothing to compare._` | no earlier run is stored for the project |
| **added** pipeline / repo | exists now but not in the previous run |
| **removed** pipeline / repo | was in the previous run but not now |
| **changed** pipeline | the pipeline's normalized definition differs, for example steps, triggers, variables, approvals or stages |
| `_No changes._` | nothing was added, removed or changed |

## How it works

- Each run saves an index per project in `out/model/<project>/index.json`: every pipeline's name, kind and a fingerprint of its normalized definition, plus the repo list. The next run compares against it, then replaces it.
- Run results aren't part of the fingerprint: run statistics, the last good run's agents and timeline comparison. So "changed" means the definition itself changed.
- An `--offline` rerun uses the same cached data, so it shows no changes. To see real drift, rerun with `--refresh`.
- Comparing an inventory run with a deep run of the same project marks pipelines as changed, because the deep run knows more about each pipeline. Compare like with like.
