# azdo-analyzer

Read-only analysis of **Azure DevOps Server 2022** projects, for planning and building their **GitLab.com** pipelines, one project at a time.

It pulls repos, YAML and classic build pipelines, classic releases, variables, connections, environments, agents and policies through the REST API with a **read-only PAT**. Its outputs:

- an Excel workbook
- one Markdown dossier per repo: the migration checklist ([docs/migration-checklist.md](docs/migration-checklist.md)), pre-filled
- a summary per project
- a drift report since the previous run

It never writes to Azure DevOps or GitLab, and it does not generate `.gitlab-ci.yml` files.

## Setup

```bash
cd ~/claude_workspace/azdo-analysis
/opt/homebrew/bin/python3.12 -m venv .venv          # system python3 is 3.9 - use 3.12
.venv/bin/pip install -e '.[dev]'
cp config.example.yaml config.yaml                  # set azdo.collection_url (+ ca_bundle if your server uses an internal CA)
export AZDO_PAT='<read-only PAT>'                   # never put the PAT in config.yaml
.venv/bin/azdo-analyzer doctor                      # connectivity, API version, PAT coverage, git access
```

### The PAT

Create it from an account that is only in the **Readers** groups. The effective permission is the PAT scope intersected with the account's permissions, and the tool only sends GET requests anyway.

| Scope (Read) | Used for |
|---|---|
| Code | repos, branches, tags, PRs, branch policies, TFVC detection, `git clone` |
| Build | definitions, runs, timelines, checks/approvals, pipeline authorizations, service hooks |
| Release | release definitions, deployments |
| Agent Pools | pools, agents + capabilities, queues, task catalog |
| Task Groups, Variable Groups, Secure Files | library (secret values are never returned) |
| Service Connections | endpoints (execution history may need *Read & query*) |
| Project and Team, Extensions, Packaging | projects, installed extensions, feeds |
| Wiki, Identity *(optional)* | wiki list; names of required reviewers (for CODEOWNERS) |
| ⚠ Environment, Deployment Groups | only "Read & manage" exists. If you leave them out, those collectors show as FORBIDDEN in the Coverage sheet |

On macOS you can keep the PAT in the Keychain instead: `security add-generic-password -s azdo-analyzer -a $USER -w`, then set `azdo.keychain_service: azdo-analyzer`.

## Usage

| Command | What it does |
|---|---|
| `azdo-analyzer doctor` | Shows who the PAT authenticates as, the newest API version, which endpoints are allowed, and whether `git ls-remote` works |
| `azdo-analyzer inventory --all` | Metadata-only pass over every project, no clones. Use it for wave planning and the retire list |
| `azdo-analyzer analyze -p "Project"` | Deep pass before a wave: full definitions, timelines, checks, clones (depth 1), YAML template resolution, content scan, dossiers |
| `... --offline` | Re-run analysis and reports from the cache, with no API calls |
| `... --refresh` | Re-fetch everything (otherwise cached responses are reused) |
| `analyze ... --no-clone` | Skip clones; YAML files are read through the items API, and the repo content scan is skipped |

### Outputs (`out/reports/<date>/`)

- `azdo-analysis-<label>.xlsx` has these sheets:
  - Summary
  - **Tracker** (one row per repo, with your Wave/Owner/Status)
  - Repos, Pipelines, Releases, Release Stages
  - Tasks (with their GitLab mapping)
  - Variables, Variable Groups, Service Connections, Secure Files
  - Agents & Pools, Environments & Deploy Groups, Branch Policies
  - Dependencies, Findings, Archetypes (+ pipeline clones)
  - Coverage
- `dossiers/<project>/<repo>.md` is the checklist for that repo:
  - `[x]` marks items filled from AZDO; `[ ]` marks manual items
  - it lists findings with remediation and ends with a Mermaid dependency graph
- `<project>/summary.md` + `graph.mmd`: wave readiness, archetypes, shared resources, retire candidates.
- `diff-<label>.md`: pipelines and repos added, removed or changed since the last run.

Manual decisions go in `overrides.yaml` (see `overrides.example.yaml`; keep it in git). They are merged into every run, so regenerating the reports never loses them.

## How it works

`collect` (GET-only, cached in `out/raw/`) → `normalize` (YAML, classic build and classic release become one Pipeline → Stage → Job → Step model) → `analyze` (rules) → `report`.

- **Classic:** task GUIDs are resolved through the server's task catalog, and task groups are expanded recursively.
- **YAML:**
  - `template:` references are inlined, including `path@alias` from other repos at the pinned `ref`, and `${{ parameters.x }}` values are substituted.
  - `${{ if }}` branches are **all** kept and flagged, and `${{ each }}` over literal lists is unrolled.
  - Variables and trigger overrides defined in the UI are merged in.
  - The result is cross-checked against the tasks that actually ran in the last good run.
- **Activity:** last commit, run and deployment give Active / Dormant / Dead. Run statistics, peak concurrency and build minutes per pool are computed from the run history.
- **Usage graph:** links each repo to its pipelines, releases and the resources they use (variable groups, connections, secure files, pools, environments, deployment groups, template repos). It is confirmed with connection execution history and pipeline authorizations.
- **Archetype:** stack × build tool × deploy target × artifact. **Complexity:** the checklist baseline plus weighted points. **Findings:** severity, evidence and remediation.

All judgement lives in editable YAML under `rules/`:

| File | Contents |
|---|---|
| `task_mapping.yaml` | AZDO task → GitLab approach (unmapped tasks are listed by usage) |
| `archetypes.yaml` | detection rules and named archetypes |
| `scoring.yaml` | complexity weights and thresholds |
| `findings.yaml` | severity, title, remediation |
| `scan_patterns.yaml` | content-scan regexes |
| `predefined_vars.yaml` | AZDO → `CI_*` variable mapping |

## Security notes

- The client refuses anything but GET, both in code and in an httpx request hook.
- The PAT is redacted from logs and errors. Git receives it through `GIT_CONFIG_*` environment variables, never in a URL, `.git/config` or the process list.
- `out/` is git-ignored. It holds API responses, which include **non-secret** variable values, and shallow clones. Set `analysis.redact_values: true` to keep plain values out of the reports.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Received an HTML page instead of JSON` / 401 | PAT invalid or expired, or the collection URL is wrong |
| TLS / certificate errors | set `azdo.ca_bundle` to your corporate CA PEM |
| `out of range` API version | run `doctor` and set `azdo.api_version` to the version it prints |
| FORBIDDEN rows in Coverage | a scope or permission is missing; the rest of the analysis still runs |
| Server under load | lower `azdo.concurrency`; reruns use the cache unless `--refresh` |

## Tests

```bash
.venv/bin/python -m pytest -q
```

The tests run offline against sanitized sample data (`tests/fixtures/sample_data.py`). That includes a fake AZDO Server for the collectors and an end-to-end run that builds the workbook and dossiers.
