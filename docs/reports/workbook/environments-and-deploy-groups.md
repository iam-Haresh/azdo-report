# Environments & Deploy Groups sheet

[Report guide](../README.md) › [Workbook](README.md) › Environments & Deploy Groups

**One row per:** YAML environment (first), then deployment group.
**Use it to:** plan GitLab environments, protected-environment approvals, and where runners must be installed.
**Modes:** **deep only.** These Azure DevOps APIs need the PAT scopes "Environment (Read & manage)" and "Deployment Groups (Read & manage)". Without them the sheet is empty and the [Coverage sheet](coverage.md) shows FORBIDDEN.
**Data:** `distributedtask/environments` (with resources and deployment records), `pipelines/checks/configurations`, and `distributedtask/deploymentgroups` (with machines).

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Kind | `environment` or `deployment group` | which API the row came from |
| Name | environment or deployment-group name | `name` |
| Targets / resources | what it deploys to | environment resources as `type:name` (for example `kubernetes:payments`), or the deployment group's machine names |
| Tags | tags on the resources or machines | resource or machine `tags` |
| Checks | checks that must pass before deploying (environments only) | `pipelines/checks/configurations` for the environment: approvals (with approvers and minimum count), branch control, business hours, exclusive lock, required template, other checks |
| Deployments | deployments to the environment (blank for deployment groups) | environment deployment records, the latest 50 |
| Last deployment | most recent of those deployments | same records |
| Used by | pipelines and releases that deploy here | YAML deployment jobs naming the environment (`env` or `env.resource`), or release stages with deployment-group jobs |
| GitLab mapping | suggested GitLab setup | environment: "GitLab environment", plus "protected environment approvals (Premium)" when it has approval checks · deployment group: self-managed runners on its N targets, tagged per environment, or SSH/WinRM from a runner inside the network |

## Notes

- Deployment-group deployments are on the [Release Stages](release-stages.md) sheet, since they belong to classic release stages.
- Using a deployment group raises `DEPLOYMENT_GROUP` and `INTERNAL_TARGET`. Environment checks raise `APPROVALS` and `GATE`. See [Findings](findings.md).
