# Archetypes sheet

[Report guide](../README.md) › [Workbook](README.md) › Archetypes

**What it is:** three tables.
1. Every archetype combination found, with its repos.
2. Every value of every dimension, with its repos, build pipelines and releases: each stack, build tool, test or scan tool, deploy target, artifact and marker.
3. Pipelines that are clones of each other.

**Use it to:** decide which shared GitLab CI templates and CI/CD components to build, and which repos each one serves.
**Data:** repo files (deep runs) and the tasks, scripts and service connections of the pipelines and releases that use each repo. The rules are in `rules/archetypes.yaml`, and every value is listed in [Archetype values](../archetype-values.md).

A dimension can hold several values, joined with ", ". For example, an ASP.NET Core app with an Angular client has the stack `dotnet, angular`. Disabled repos are left out of the first two tables.

## Archetype combinations table (one row per archetype key)

| Column | What it shows | Derived from |
|---|---|---|
| Archetype key (stack \| build \| deploy \| artifact) | the full combination, for example `dotnet, angular \| dotnet, npm \| iis \| files` | [archetype key](../concepts.md#archetype-key) |
| Stack | the stacks of the combination | first part of the key |
| Build tools | the build tools | second part of the key |
| Deploy targets | the deploy targets; `none` = no deployment found | third part of the key |
| Artifacts | what is produced; `none` = nothing published found | fourth part of the key |
| Named archetype | friendly names, comma-separated: one per stack, or one for an entry that names several stacks; `custom` when nothing matches | [named archetypes](../concepts.md#named-archetypes) (computed; overrides are not applied here) |
| Proposed template | the templates of those names | each matching entry's `template` |
| Repos | number of repos with this key | repo profiles |
| Pipelines | build pipelines plus releases linked to those repos | Tracker links |
| Avg score | average repo complexity score | repo Score values |
| Complexity mix | how many repos per level, for example `High 1, Low 2` | computed levels (overrides not applied) |
| Test & scan tools (repos) | the test and scan tools of these repos, with the number of repos using each, for example `sonarqube (5), karma (3)` | each repo's Test & scan tools (not part of the key) |
| Markers (repos) | the markers of these repos, with counts, for example `docker (4), spring-boot (2)` | each repo's Markers (not part of the key) |
| Repos list | the repos (up to 15) | repo keys `project/repo` |

## Archetype components table (one row per value of each dimension)

| Column | What it shows | Derived from |
|---|---|---|
| Dimension | Stack, Build tools, Test & scan tools, Deploy targets, Artifacts or Markers | |
| Value | the value, for example `angular` or `kubernetes`. `unknown` (Stack) = repos where no stack was recognised | repo profiles |
| What it is | the value's description | `label` in `rules/archetypes.yaml` ([Archetype values](../archetype-values.md)) |
| Repos | number of repos with this value | repo profiles |
| Build pipelines | enabled build/YAML pipelines with this value. Build tools, test & scan tools, deploy targets and artifacts come from each pipeline's own definition; stacks and markers from the repo it builds | the [Pipelines sheet](pipelines.md) columns Repo stack, Build tools, Test & scan tools, Deploy targets, Artifacts produced |
| Releases | enabled classic releases with this value, counted the same way: their own values, and the stacks and markers of the repos they deploy | the [Releases sheet](releases.md) columns of the same names |
| Found together with (repos) | the other values most often found in the same repos (top 10), with repo counts, for example `stack:dotnet (5), deploy:iis (4), test/scan:karma (3)` | the same repos' other values, prefixed by dimension |
| Repos list | the repos (up to 15) | repo keys `project/repo` |
| Releases list | the releases (up to 15) | `project/release` |

## Pipeline clones table (one row per group)

| Column | What it shows | Derived from |
|---|---|---|
| Clone type | `identical` (same task sequence) or `similar (>= 80%)` | [fingerprint](../concepts.md#pipeline-fingerprint-and-clones) for identical; at least 80% task overlap within the same pipeline kind for similar |
| Fingerprint | the shared fingerprint (for similar groups, the first pipeline's) | ordered task list hash |
| Pipelines | the pipelines in the group (up to 10) | `project/pipeline` |
| Count | number of pipelines in the group | |
| Task sequence | the tasks in order, for example `NuGetCommand@2 > VSBuild@1 > VSTest@2` | first pipeline's enabled tasks |

## How to use it

1. Sort the components table by **Repos** within each dimension. Each frequent value is a building block: a CI/CD component or a template job, such as an Angular build, a container image build, a Helm deploy or a SonarQube scan. **Found together with** shows which blocks go together.
2. Sort the combinations table by **Repos**. The top combinations are the pipeline templates to build; each one includes the components it needs. **Named archetype** and **Proposed template** show what the rules suggest.
3. Name your combinations under `named:` in `rules/archetypes.yaml`, then rerun with `--offline`. An entry can name several stacks, for example `stack: [java-maven, angular]`. The Tracker and dossiers show the names.
4. For a release view, read the **Releases** column and list: for example every release that deploys to IIS, or that uses Octopus. Releases that aren't linked to any repo are counted too.
5. If a value looks wrong, open the repo's [dossier](../repo-dossier.md). Its archetype table shows the file, task or script line behind every value. Adjust the rule in `rules/archetypes.yaml` and rerun.
6. Clone groups confirm which pipelines can share one template unchanged.
