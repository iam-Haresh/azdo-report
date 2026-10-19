# Agents & Pools sheet

[Report guide](../README.md) › [Workbook](README.md) › Agents & Pools

**One row per:** agent in each self-hosted agent pool. Microsoft-hosted pools are skipped. A pool whose agents couldn't be read shows one row: `(no agents collected)`.
**Use it to:** design GitLab runners: which operating systems, which tools in the runner image, and how many runners.
**Data:** `distributedtask/pools` and `distributedtask/pools/{id}/agents` (with capabilities), plus the run history of the analysed projects.

| Column | What it shows | Derived from |
|---|---|---|
| Pool | agent pool name | pool `name` |
| Agent | agent name | agent `name` |
| OS | operating system | agent `osDescription`, or else the `Agent.OSVersion` / `Agent.OS` capability |
| Agent version | Azure Pipelines agent version | agent `version` |
| Status | `online` or `offline` | agent `status` |
| Enabled | `no` if the agent is disabled in the pool | agent `enabled` |
| Tools found in capabilities | tools installed on the agent, i.e. what a GitLab runner image needs | the agent's system and user capabilities. Detected names: java, maven, gradle, ant, node, dotnet, .NET Framework, msbuild, visualstudio, vstest, docker, kubectl, helm, oc, python, pwsh, powershell, terraform, az, ansible, sqlpackage, git |
| Last job | when the agent last finished a job | agent `lastCompletedRequest` |
| Pool peak concurrency | most runs that were in progress at the same moment in this pool | build/YAML runs in the history window, across all analysed projects, overlapped by start and finish time |
| Pool build min/month | build minutes per month in this pool | total run minutes in the window ÷ (`history_days` ÷ 30) |
| Pool runs (window) | number of runs in this pool in the history window | the same runs |

## Notes

- The three Pool columns repeat on every agent row of the same pool.
- Pools are shared by the whole collection, but the pool numbers only count runs of the projects in this report. Release deployments aren't included.
- A pool whose agents are all Windows makes the pipelines using it raise `WINDOWS_TOOLCHAIN`.
