# Variable Groups sheet

[Report guide](../README.md) › [Workbook](README.md) › Variable Groups

**One row per:** variable group (Pipelines → Library in Azure DevOps).
**Use it to:** decide which groups become GitLab group-level variables, which stay per project, and which move to a secret store.
**Data:** `distributedtask/variablegroups`, plus which pipelines reference each group.

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Group | group name | group `name` |
| ID | group ID | group `id` |
| Type | `Vsts` (a normal group) or `AzureKeyVault` (values come from an Azure Key Vault) | group `type` |
| Variables | number of variables in the group | group `variables` |
| Secrets | number of secret variables | variables marked `isSecret` |
| Key Vault | vault name (Key Vault groups only) | group `providerData.vault` |
| Shared with projects | other Azure DevOps projects the group is shared with | group `variableGroupProjectReferences` |
| Used by pipelines | pipelines and releases that reference the group | YAML `- group: <name>` (deep only for YAML); classic definitions and release stages that link the group by ID |
| Repos | repos those pipelines belong to | pipeline → repo links (see [Tracker](tracker.md)) |
| Proposed level | where the group's variables should live in GitLab | `external secret store` (Key Vault group) · `parent GitLab group` (shared with other projects) · `GitLab group` (used by more than one repo) · `project` (one repo) · `unused` (no pipeline uses it) |

## Notes

- One row per variable, with its own proposed GitLab key, is on the [Variables sheet](variables.md).
- A Key Vault group reads its secrets through a service connection. That connection counts as used by the pipelines using the group (see [Service Connections](service-connections.md)).
