# Archetypes sheet

[Report guide](../README.md) › [Workbook](README.md) › Archetypes

**What it is:** two tables. First, repos grouped by archetype key. Then, pipelines that are clones of each other.
**Use it to:** choose the 5–8 shared GitLab CI templates worth building, and see which repos each template would serve.
**Data:** derived from repo files (deep) and pipeline tasks. Rules are in `rules/archetypes.yaml`.

## Archetypes table (one row per archetype key)

Disabled repos are left out.

| Column | What it shows | Derived from |
|---|---|---|
| Archetype key (stack \| build \| deploy \| artifact) | the four-part key, for example `java-maven \| maven \| kubernetes \| image` | [archetype key](../concepts.md#archetype-key) |
| Named archetype | friendly name, or `custom` when no named rule matches | first matching entry under `named:` in `rules/archetypes.yaml` (computed; overrides are not applied here) |
| Proposed template | name of the shared GitLab template to build for this archetype | the matching entry's `template` |
| Repos | number of repos with this key | repo profiles |
| Pipelines | build pipelines plus releases linked to those repos | Tracker links |
| Avg score | average repo complexity score | repo Score values |
| Complexity mix | how many repos per level, for example `High 1, Low 2` | computed levels (overrides not applied) |
| Repos list | the repos (up to 15) | repo keys `project/repo` |

## Pipeline clones table (one row per group)

| Column | What it shows | Derived from |
|---|---|---|
| Clone type | `identical` (same task sequence) or `similar (>= 80%)` | [fingerprint](../concepts.md#pipeline-fingerprint-and-clones) for identical; at least 80% task overlap within the same pipeline kind for similar |
| Fingerprint | the shared fingerprint (for similar groups, the first pipeline's) | ordered task list hash |
| Pipelines | the pipelines in the group (up to 10) | `project/pipeline` |
| Count | number of pipelines in the group | |
| Task sequence | the tasks in order, for example `NuGetCommand@2 > VSBuild@1 > VSTest@2` | first pipeline's enabled tasks |

## How to use it

1. Sort the first table by **Repos**. The top rows are your template candidates.
2. Give the useful keys a name and template under `named:` in `rules/archetypes.yaml`, then rerun. The Tracker and dossiers show the names.
3. Clone groups confirm which pipelines can share one template unchanged.
