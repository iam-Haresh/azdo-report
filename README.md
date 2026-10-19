# azdo-analyzer

Read-only analysis of **Azure DevOps Server 2022** projects, for planning and building their **GitLab.com** pipelines, one project at a time.

It pulls repos, YAML and classic build pipelines, classic releases, variables, connections, environments, agents and policies through the REST API with a **read-only PAT**. Its outputs:

- an Excel workbook
- one Markdown dossier per repo: the migration checklist ([docs/migration-checklist.md](docs/migration-checklist.md)), pre-filled
- a summary per project
- a drift report since the previous run

It **cannot** write to Azure DevOps (see [Read-only guarantees](#read-only-guarantees)), never touches GitLab, and does not generate `.gitlab-ci.yml` files.

## Setup

```bash
cd azdo-analysis                                    # the folder where you cloned this repository
python3.12 -m venv .venv                            # needs Python 3.11 or newer
.venv/bin/pip install -e '.[dev]'
cp config.example.yaml config.yaml                  # set azdo.collection_url (TLS verification is off by default)
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
| `azdo-analyzer inventory` | The same pass, for the projects listed under `scope.projects` in `config.yaml` |
| `azdo-analyzer analyze -p "Project"` | Deep pass before a wave: full definitions, timelines, checks, clones (depth 1), YAML template resolution, content scan, dossiers |
| `... --offline` | Re-run analysis and reports from the cache, with no API calls |
| `... --refresh` | Re-fetch everything (otherwise cached responses are reused) |
| `analyze ... --no-clone` | Skip clones; YAML files are read through the items API, and the repo content scan is skipped |
| `... --collection <url or name>` | Which collection to read (all commands). It takes a full URL, `https://azdo.mycompany.com/OtherCollection`, or just a name, `OtherCollection`, on the server from `config.yaml` |
| `... --output-dir <folder>` | Where to write the cache, clones and reports (all commands). Overrides `output.dir` |

**Which collection is used:** `--collection` if given, else the `AZDO_COLLECTION_URL` environment variable, else `azdo.collection_url` in `config.yaml`.

**One output folder holds one collection.** The cache remembers its collection. A run against a different collection stops with a message instead of mixing the two, so give each collection its own folder:
```bash
azdo-analyzer analyze --collection OtherCollection -p "Payments" --output-dir out-other
```

### Outputs (`out/reports/<date>/`)

For what every sheet, column and report section means and how it is derived, see the **[report guide](docs/reports/README.md)**.

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
- **Activity:** last commit, run and deployment give Active / Dormant / Dead (details below). Run statistics, peak concurrency and build minutes per pool are computed from the run history.
- **Usage graph:** links each repo to its pipelines, releases and the resources they use (variable groups, connections, secure files, pools, environments, deployment groups, template repos). It is confirmed with connection execution history and pipeline authorizations.
- **Archetype:** stack × build tool × deploy target × artifact. **Complexity:** the checklist baseline plus weighted points. **Findings:** severity, evidence and remediation.

### How activity is calculated

- **Last commit** is the newest commit across **all existing branches**, not just the default branch.
  - It comes from `git/repositories/{id}/stats/branches`, which returns each branch with its latest commit.
  - It uses the committer date (when the commit landed, e.g. when a PR was completed), falling back to the author date.
  - Deleted branches and tags don't count. The date comes from the commit, not the push, so pushing an old commit today keeps its old date.
- **Last pipeline run** is the newest run of the build/YAML pipelines that build the repo. It takes the definition's latest build (its finish time, or its queue time if still running), which isn't limited to the history window. YAML deployment stages run inside these runs, so they are covered too.
- **Last deployment** is the newest activity of the classic releases that deploy those builds: the latest deployment in the history window, or the creation date of the latest release, whichever is newer.
- **Template repos** take the activity of the pipelines that use their templates.
- **Repo status** is based on the newest of the dates above:

  | Status | Meaning |
  |---|---|
  | Active | within `analysis.active_days` (90 by default) |
  | Dormant | within `analysis.dormant_days` (365 by default) |
  | Dead | older than that |
  | Never | no activity found |
  | Disabled | the repo is disabled in AZDO |

  Pipelines get their own Active / Dormant / Dead status from their last run or deployment.
- **Stale branches** counts branches whose newest commit is older than `analysis.dormant_days`.
- **Run statistics** (runs, success %, durations, queue time, peak concurrency) cover the last `collection.history_days` days (180 by default).

All judgement lives in editable YAML under `rules/`:

| File | Contents |
|---|---|
| `task_mapping.yaml` | AZDO task → GitLab approach (unmapped tasks are listed by usage) |
| `archetypes.yaml` | detection rules and named archetypes |
| `scoring.yaml` | complexity weights and thresholds |
| `findings.yaml` | severity, title, remediation |
| `scan_patterns.yaml` | content-scan regexes |
| `predefined_vars.yaml` | AZDO → `CI_*` variable mapping |

## Run it in GitLab CI

`.gitlab-ci.yml` runs the tool in the official `python:3.12` image, which already includes git.

| Pipeline | Job | What it does |
|---|---|---|
| push / merge request | `test` | runs the tool's own offline test suite |
| Run pipeline (or a schedule / API), `AZDO_PROJECT` empty | `inventory` | `doctor`, then `inventory --all` |
| Run pipeline, `AZDO_PROJECT` set | `analyze` | `doctor`, then `analyze --project "$AZDO_PROJECT"` |

The workbook, dossiers, summaries and logs are kept as job artifacts (`out/reports/`, `out/logs/`) for 30 days.

**One-time setup**

1. Settings → CI/CD → Variables:

   | Variable | Value | Options |
   |---|---|---|
   | `AZDO_PAT` | the read-only PAT | **Masked** and **Protected** |
   | `AZDO_COLLECTION_URL` | your default collection URL | |
   | `AZDO_CONFIG_FILE` | *(optional)* a `config.yaml`, if you need non-default settings | type **File** |
2. **Runner:** your Azure DevOps Server is on-prem, and GitLab.com's hosted runners can't reach it.
   - Register a self-managed runner inside your network (Docker executor).
   - Put its tag in `.gitlab-ci.yml` under `.azdo-job` → `tags:` (the placeholder is `azdo-network`).
   - The `test` job needs no network and runs on any runner.

**Running it:** Build → Pipelines → **Run pipeline**. The form has three fields:
- `AZDO_PROJECT`: the project to analyse; leave it empty for the inventory.
- `AZDO_COLLECTION`: optional, another collection, as a URL or a name on the same server.
- `AZDO_EXTRA_ARGS`: optional, e.g. `--refresh` or `--no-clone`.

A pipeline schedule with the same variables keeps the inventory current.

Each CI job starts from an empty `out/` folder, so it always fetches fresh data. Only one analysis runs at a time (`resource_group`), to keep the load on the server low.

## Read-only guarantees

The tool cannot change anything in Azure DevOps. Each layer below is enforced in code and covered by `tests/test_read_only.py`.

1. **Your PAT is the outer boundary.** Give it Read scopes only, from an account in the Readers groups. Azure DevOps itself then refuses any write, whatever the tool does.
2. **REST calls** (`client.py`) are checked before anything is sent. The check runs twice: in the client and again in an httpx request hook, so even direct use of the underlying HTTP client can't get past it. A call is allowed only if it is:
   - a **GET** (POST, PUT, PATCH, DELETE and every other verb are refused),
   - to **your collection host only**,
   - to one of the **read endpoints listed in `READ_ENDPOINTS`** (about 25 routes, short enough to review). Any other route, even another GET, is refused.
   - Redirects are never followed.
3. **git** (`collect/content.py`):
   - Only `git clone` (depth 1) and `git ls-remote` can be run. Any other subcommand, including `push`, `fetch`, `commit` and `config`, is refused.
   - `--refresh` deletes the cached clone and clones again; it never fetches or resets.
   - Every clone gets an unreachable push URL (`read-only://...`), so even a manual `git push` from `out/repos/` fails.
   - Saved git credentials are switched off (`credential.helper` reset), so only the read-only PAT is ever used.
   - The server's clone URL is passed after `--`, so it can never be read as a git option.
4. **No other network or command-line access.** A test fails if any module other than `client.py` imports an HTTP library, or if any module other than the git wrapper and the macOS Keychain lookup runs a command.
5. **Local writes stay under `out/`**: cache, clones, model, reports, logs. `overrides.yaml` is only read.

`doctor` prints these safeguards at the end of its output.

Other notes:
- TLS certificate verification is **off by default** (`azdo.verify_tls: false`) for API calls and git. To verify against your corporate CA instead, set `verify_tls: true` and `ca_bundle: /path/to/ca.pem`.
- The PAT is redacted from logs and errors. git receives it through `GIT_CONFIG_*` environment variables, never in a URL, `.git/config` or the process list.
- `out/` is git-ignored. It holds API responses, which include **non-secret** variable values, and shallow clones. Set `analysis.redact_values: true` to keep plain values out of the reports.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Received an HTML page instead of JSON` / 401 | PAT invalid or expired, or the collection URL is wrong |
| TLS / certificate errors (only with `verify_tls: true`) | set `azdo.ca_bundle` to your corporate CA PEM |
| `out of range` API version | run `doctor` and set `azdo.api_version` to the version it prints |
| FORBIDDEN rows in Coverage | a scope or permission is missing; the rest of the analysis still runs |
| Server under load | lower `azdo.concurrency`; reruns use the cache unless `--refresh` |

## Tests

```bash
.venv/bin/python -m pytest -q
```

The tests run offline against sanitized sample data (`tests/fixtures/sample_data.py`). That includes a fake AZDO Server for the collectors and an end-to-end run that builds the workbook and dossiers.
