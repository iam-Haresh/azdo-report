# Service Connections sheet

[Report guide](../README.md) › [Workbook](README.md) › Service Connections

**One row per:** service connection (Project settings → Service connections).
**Use it to:** decide what replaces each connection in GitLab, spot unused ones, and see which targets are only reachable inside your network.
**Data:** `serviceendpoint/endpoints`, plus execution history and pipeline authorizations (deep only). Credentials are never read; Azure DevOps doesn't return them.

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Name | connection name | endpoint `name` |
| Type | what it connects to, for example `kubernetes`, `dockerregistry`, `azurerm`, `sonarqube`, `ssh`, `generic` | endpoint `type` |
| Auth scheme | how it authenticates, for example `ServicePrincipal`, `WorkloadIdentityFederation`, `UsernamePassword`, `Token`, `Kubernetes` | endpoint `authorization.scheme` |
| URL | the target the connection points to | endpoint `url` |
| Internal host | `yes` if the target is only reachable inside your network | the URL's host matches `analysis.internal_host_patterns` ([internal host](../concepts.md#internal-host)) |
| Shared | `yes` if the connection is shared between projects | endpoint `isShared` |
| Other projects | projects it is shared with | endpoint `serviceEndpointProjectReferences` |
| Used by (definitions) | pipelines and releases that use it | any of: a task input holds the connection's ID or name; a YAML container or repository resource names it; a Key Vault variable group they use goes through it; a recent execution record names the definition |
| Executions (recent) | number of recent runs that used the connection **(deep only)** | `serviceendpoint/{id}/executionhistory` (latest 50 records) |
| Last used | most recent of those runs **(deep only)** | same records |
| Authorized pipelines | YAML pipelines allowed to use the connection **(deep only)** | `pipelines/pipelinepermissions/endpoint/{id}`: `all pipelines`, or the pipeline IDs authorized one by one |
| GitLab replacement | suggested GitLab equivalent for this type | built-in hints. Kubernetes / OpenShift → GitLab agent for Kubernetes (or a kubeconfig File variable) · Docker registry → masked registry credentials · Azure → OIDC `id_tokens` with workload identity federation · SonarQube → `SONAR_HOST_URL` + `SONAR_TOKEN` · SSH → private key as File variable · other types → masked variables |

## Notes

- Execution history may need the "Service Connections: **Read & query**" PAT scope. Without it, Executions stays 0 and the [Coverage sheet](coverage.md) shows FORBIDDEN.
- After a deep `analyze`, a connection with no users and no executions raises an `UNUSED_CONNECTION` finding: don't migrate it.
- A pipeline using an internal host raises `INTERNAL_TARGET`, because GitLab.com hosted runners can't reach it.
