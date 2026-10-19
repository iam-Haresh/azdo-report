# Dependencies sheet

[Report guide](../README.md) › [Workbook](README.md) › Dependencies

**One row per:** link between two items, such as a repo and the pipeline that builds it, or a pipeline and a variable group it uses.
**Use it to:** answer "what does this repo need?" and "who uses this resource?". The Mermaid graphs in the dossiers and project summaries are drawn from these rows.
**Data:** derived from the analysed definitions, plus connection execution history (deep only).

| Column | What it shows | Derived from |
|---|---|---|
| Project | project of the item the link starts from | the definition's project |
| From kind | type of the starting item | see the relations table |
| From | name of the starting item | |
| Relation | `built by`, `deployed by`, `consumed by`, `uses` or `triggers` | see the relations table |
| To kind | type of the target item | |
| To | name of the target item | |
| Other project | set when the target belongs to another Azure DevOps project | the reference's project |
| Evidence | where the link was found | for example `definition repository`, `artifact _legacy-web-CI`, `HelmDeploy@0:kubernetesServiceConnection`, `stage QA`, `templates @v2`, `Key Vault link` |

## Relations

| From kind → To kind | Relation | Meaning |
|---|---|---|
| repo → yaml / classic_build | built by | the pipeline builds this repo |
| external_repo → pipeline | built by | the pipeline builds a source outside Azure Repos (GitHub, other Git, TFVC) |
| yaml / classic_build → classic_release | deployed by | the release deploys this pipeline's artifacts |
| repo → classic_release | deployed by | the release uses the repo directly as a Git artifact |
| artifact → classic_release | consumed by | the release consumes another artifact type, such as a container image or package |
| build_pipeline → classic_release | deployed by | the release's build artifact comes from a pipeline that isn't in this report (another project, or deleted) |
| pipeline / release → resource | uses | the definition uses a variable group, service connection, secure file, agent queue, environment, deployment group, repository, template repo, container image or upstream pipeline |
| variable_group → service_connection | uses | a Key Vault group reads its secrets through this connection |
| pipeline → yaml / classic_build | triggers | when the upstream pipeline finishes, this one starts (YAML `resources.pipelines`, classic build completion) |

## Tips

- Filter **From = <pipeline>** to see everything one pipeline needs in GitLab.
- Filter **To kind = variable_group** (or service_connection) and **To = <name>** to see who would break if it moved.
