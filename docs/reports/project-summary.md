# Project summary

[Report guide](README.md) › Project summary

**Files:** `out/reports/<date>/<project>/summary.md` and `graph.mmd`. There is one pair per project, from every run.
**What it is:** a one-page view of a project for wave planning and status meetings.

## Header table

| Column | What it shows | Derived from |
|---|---|---|
| Repos | all repos in the project | `git/repositories` |
| Active / Dormant / Dead/never / Disabled | repos per [activity status](concepts.md#activity-status) | repo status |
| YAML pipelines / Classic builds / Classic releases | number of definitions of each kind | definitions |
| Low / Medium / High | repos per complexity level, excluding disabled repos (overrides applied) | [complexity](concepts.md#complexity-score) |
| Blockers | blocker-severity findings in the project | [Findings](workbook/findings.md) |

A warning line follows the table when the project uses TFVC.

## Wave readiness

One row per repo, disabled repos excluded. The order is the suggested migration order:
1. repos without blockers first;
2. Active repos before the others;
3. complexity Low → Medium → High;
4. then by score, then by name.

| Column | What it shows | Derived from |
|---|---|---|
| Repo | repo name | |
| Archetype | named archetype (override applied) | [Tracker → Archetype](workbook/tracker.md) |
| Pipelines | build pipelines plus releases linked to the repo | Tracker links |
| Complexity | Low, Medium or High; ⛔ marks a blocker | Tracker |
| Score | complexity points | Tracker |
| Activity | Active, Dormant, Dead or Never | Tracker |
| Recommendation | Migrate, Review with owner or Archive / retire | Tracker |
| Blocker/high findings | IDs of blocker and high findings (up to 6) | Findings |

## Other sections

| Section | What it shows | Derived from |
|---|---|---|
| Archetypes in this project | each archetype key with its named archetype and repo count | [Archetypes](workbook/archetypes.md) logic, per project |
| Shared resources | variable groups used by more than one repo or shared with other projects, and service connections used by more than one pipeline, with their proposed GitLab level or replacement. These are your group-level decisions | [Variable Groups](workbook/variable-groups.md), [Service Connections](workbook/service-connections.md) |
| Retire / archive candidates | repos whose status is Dead or Never, with their last commit date | activity status |
| Top findings | the 15 most important finding types (by severity, then count), each with one example | [Findings](workbook/findings.md) |
| Dependency graph | Mermaid diagram (also saved as `graph.mmd`) of the project's repos, pipelines and releases, their build/deploy/trigger links, and resources used by two or more pipelines | [Dependencies](workbook/dependencies.md). Agent queues are omitted; above 150 items the graph is cut short and says so |
