# Secure Files sheet

[Report guide](../README.md) › [Workbook](README.md) › Secure Files

**One row per:** secure file (Pipelines → Library → Secure files): certificates, keystores, provisioning profiles and the like.
**Use it to:** list the files you must obtain from their owners and re-create in GitLab.
**Data:** `distributedtask/securefiles`. Only names and metadata are read; the file content is never downloaded.

| Column | What it shows | Derived from |
|---|---|---|
| Project | Azure DevOps project | Projects API |
| Name | file name | secure file `name` |
| Modified | when the file was last changed (UTC timestamp) | secure file `modifiedOn` |
| Modified by | who changed it last | secure file `modifiedBy` |
| Used by | pipelines and releases that use the file | task inputs holding the file's ID or name, for example `DownloadSecureFile`, `InstallAppleCertificate`, `InstallSSHKey` |
| Authorized | YAML pipelines allowed to use the file **(deep only)** | `pipelines/pipelinepermissions/securefile/{id}`: `all pipelines` or pipeline IDs |
| GitLab replacement | where it goes in GitLab | always "Project-level Secure Files (download-secure-files) or File-type variable" |

## Notes

- Every pipeline using a secure file raises a `SECURE_FILE` finding and +1 complexity per file (max +3).
