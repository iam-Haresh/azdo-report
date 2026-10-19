# Release Stages sheet

[Report guide](../README.md) › [Workbook](README.md) › Release Stages

**One row per:** deployment stage. That means every stage of a classic release, and every YAML stage that contains a deployment job.
**Use it to:** design GitLab environments, protected-environment approvals, `when: manual` jobs and `resource_group` locks.
**Data:** the stages in each definition, `release/deployments` (classic), and environment deployment records (YAML, deep only).

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Pipeline | release or YAML pipeline the stage belongs to | definition name |
| Kind | `Classic release` or `YAML` | definition kind |
| Stage | stage name | classic environment name, or YAML `stage:` |
| Rank | order of the stage | classic stage rank (from 1); YAML position (from 0) |
| Trigger | when the stage starts | **classic:** `after release` (when a release is created), `after <stage> (succeeded)` (or another state), `artifact filter …`, or `manual` (no automatic start) · **YAML:** `after <stages in dependsOn>` |
| Pre-deploy approvers | who approves before deployment (classic); groups end in `[group]` | stage pre-deployment approvals, ignoring automatic ones. YAML approvals are environment checks: see [Environments & Deploy Groups](environments-and-deploy-groups.md) |
| Post-deploy approvers | who approves after deployment (classic) | stage post-deployment approvals |
| Required approvals | how many approvals are needed | the stage's "minimum number of approvers"; when that is 0 (all must approve), the number of approvers listed |
| Creator can approve | whether the person who created the release may approve it | stage approval option "release creator can be approver" |
| Gates | enabled gates (classic) | stage pre/post-deployment gates |
| Jobs | the stage's job types | `agent`, `server` (agentless), `deployment_group:<name> [tags]`, or `deployment` (YAML deployment job) |
| Environment | YAML environment the deployment job targets (blank for classic) | YAML `environment:` |
| Queue policy | how parallel deployments are handled (classic) | stage deployment queue settings: `N at a time, all in sequence`, `N at a time, latest only`, or `unlimited parallel` |
| Stage variables | number of variables scoped to this stage | classic stage variables; YAML stage and job variables |
| Tasks | enabled tasks the stage runs, in order (up to 8) | the stage's job steps, with task groups expanded |
| Deployments | deployments of this stage | **classic:** deployments in the history window · **YAML:** environment deployment records for this pipeline and stage, the latest 50 per environment **(deep only)** |
| Last deployed | most recent deployment | same records |
| Success % | share of deployments that succeeded | **classic:** succeeded ÷ (succeeded + failed) · **YAML:** succeeded ÷ all records |

## Where to find the GitLab equivalents

| Azure DevOps | GitLab |
|---|---|
| approvers | protected environment + deployment approval rules (Premium) |
| `manual` trigger | `when: manual` job |
| queue policy `1 at a time` | `resource_group` |
| deployment-group jobs | self-managed runners on the target machines (see [Environments & Deploy Groups](environments-and-deploy-groups.md)) |
