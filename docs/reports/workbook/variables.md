# Variables sheet

[Report guide](../README.md) › [Workbook](README.md) › Variables

**One row per:** variable. That covers the pipeline, stage and job variables of every pipeline and release, plus every variable of every variable group.
**Use it to:** plan GitLab CI/CD variables, which names need renaming, and which secrets must be re-entered.
**Data:** definition variables, YAML `variables:` blocks (deep), and `distributedtask/variablegroups`. Secret values are never returned by Azure DevOps.

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Scope | where the variable is defined | `pipeline` (YAML `variables:` or a classic definition) · `pipeline-ui` (set in a YAML pipeline's settings, not in the file) · `stage` (a classic release stage or YAML stage) · `job` (a YAML job) · `group` (a variable group) |
| Owner | pipeline or release name (stage variables add ` / <stage>`), or the variable group's name | the definition or group |
| Variable | variable name | as defined in Azure DevOps |
| Secret | `yes` if the variable is secret | the variable's `isSecret`; variables in Key Vault-linked groups are always secret |
| Settable at queue | `yes` if it can be changed when a run is queued | the variable's "settable at queue time" (`allowOverride`) |
| Value | the value | the plain value. `(secret)` for secrets, because Azure DevOps never returns them. `(redacted)` when the name looks like a secret (`analysis.secret_name_pattern`) or `analysis.redact_values` is on. `(Key Vault)` for Key Vault groups |
| Valid GitLab key | `yes` if the name can be used as-is in GitLab | GitLab keys may only contain `A-Z a-z 0-9 _` |
| Proposed key | name to use in GitLab | the name if valid; otherwise upper-cased, with every other character changed to `_`. This is the environment-variable name Azure DevOps already exposes, so scripts keep working: `build.platform` → `BUILD_PLATFORM` |
| Proposed GitLab level | where to create it in GitLab | see the rules below |
| Used by | pipeline(s) using it | the owning pipeline; for group variables, the pipelines that use the group (up to 5) |

## Proposed GitLab level rules

| Variable | Proposed level |
|---|---|
| pipeline or job variable, secret | project variable (masked) |
| pipeline or job variable, settable at queue | `spec:inputs` / prefilled pipeline variable |
| other pipeline or job variable | `.gitlab-ci.yml variables:` |
| stage variable | project variable with environment scope `<stage>` (masked if secret) |
| variable of a Key Vault-linked group | external secret (`secrets:azure_key_vault` / Vault) |
| group variable, where the group is shared with other Azure DevOps projects | parent GitLab group variable |
| group variable, where the group is used by more than one repo | GitLab group variable |
| group variable, where the group is used by one repo | project variable |
| group variable, where no pipeline uses the group | unused - skip |

## Notes

- Values shown here come from the raw cache under `out/raw`, which keeps them even when the report hides them. Keep `out/` private.
- Variable names that are invalid as GitLab keys raise an `INVALID_VAR_NAME` finding. Secret-looking plain values raise `PLAINTEXT_SECRET`. See [Findings](findings.md).
