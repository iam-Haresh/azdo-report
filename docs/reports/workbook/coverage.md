# Coverage sheet

[Report guide](../README.md) › [Workbook](README.md) › Coverage

**One row per:** API endpoint the tool called, per scope. Per-item endpoints, such as one call per repo, are grouped into one row.
**Use it to:** check that nothing is missing. A FORBIDDEN row means the PAT or your account lacks a permission, so the related columns are empty.
**Data:** recorded by the collector during the last online run (saved in `out/raw/<scope>/coverage.json`). An `--offline` run shows the coverage of the last online run.

| Column | What it shows | Derived from |
|---|---|---|
| Scope | `_org` for collection-wide data (task catalogue, pools, extensions, feeds, service hooks), otherwise the project | the collector |
| Collector | the part of the tool that called it: `org`, `repos`, `builds`, `releases`, `library`, `connections`, `resources`, `content` | the collector |
| Endpoint | REST route (`{id}` stands for one call per item), or `git clone` | the collector |
| Status | the worst result across the calls | `OK` fetched · `CACHED` reused from `out/raw` without an API call · `NOT_FOUND` 404, the thing doesn't exist (for example an empty repo's branches) · `FORBIDDEN` 401/403, missing PAT scope or permission · `ERROR` another failure · `MISSING_OFFLINE` `--offline` and not in the cache |
| Calls | number of calls made (or served from cache) | the collector |
| Failed | calls that ended FORBIDDEN, ERROR or MISSING_OFFLINE | the collector |
| Items | total records returned | the collector |
| Message | the first error message, if any | the API response |

## Common FORBIDDEN rows

| Endpoint | Why | Effect |
|---|---|---|
| `distributedtask/environments`, `distributedtask/deploymentgroups` | these need the PAT scopes "Environment (Read & manage)" and "Deployment Groups (Read & manage)"; there is no read-only option | Environments & Deploy Groups sheet is empty; deployment groups show as `#<id>` |
| `serviceendpoint/{id}/executionhistory` | may need "Service Connections (Read & query)" | Executions / Last used stay empty |
| `identities` | optional "Identity (Read)" scope | required reviewers show IDs instead of names |

`tfvc/changesets` reports OK with 0 items for a Git-only project: the server's 404 there just means "no TFVC".
