"""Normalized pipeline model shared by YAML, classic build and classic release.

Pipeline -> Stage -> Job -> Step, plus Trigger, Variable, ResourceRef, Artifact.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from azdo_analyzer.util import gitlab_key, is_valid_gitlab_key


@dataclass
class Step:
    name: str
    kind: str  # task | script | checkout | download | publish | template | other
    task: str | None = None  # normalized "Name@major" (scripts use script/bash/pwsh/powershell)
    task_id: str | None = None
    task_version: str | None = None
    source: str = "builtin"  # builtin | extension | unknown | yaml
    extension: str | None = None
    enabled: bool = True
    condition: str | None = None
    continue_on_error: bool = False
    timeout: int | None = None
    retries: int | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    script: str | None = None
    env: dict[str, Any] = field(default_factory=dict)
    via_task_group: list[str] = field(default_factory=list)
    origin: str | None = None  # template file the step came from
    windows_only: bool = False


@dataclass
class Job:
    name: str
    kind: str = "agent"  # agent | server | deployment | deployment_group
    pool: str | None = None
    vm_image: str | None = None
    demands: list[str] = field(default_factory=list)
    container: str | None = None
    services: list[str] = field(default_factory=list)
    strategy: dict[str, Any] | None = None
    environment: str | None = None
    deployment_group: str | None = None
    tags: list[str] = field(default_factory=list)
    condition: str | None = None
    depends_on: list[str] = field(default_factory=list)
    timeout: int | None = None
    continue_on_error: bool = False
    steps: list[Step] = field(default_factory=list)


@dataclass
class Approval:
    when: str  # pre | post | check
    approvers: list[str] = field(default_factory=list)
    required_count: int | None = None
    creator_can_approve: bool | None = None
    timeout_minutes: int | None = None


@dataclass
class Gate:
    when: str  # pre | post | check
    name: str
    task: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class Variable:
    name: str
    value: str | None
    is_secret: bool = False
    settable_at_queue: bool = False
    scope: str = "pipeline"  # pipeline | pipeline-ui | stage:<name> | group:<name>
    source: str = ""  # where it was defined

    @property
    def valid_gitlab_key(self) -> bool:
        return is_valid_gitlab_key(self.name)

    @property
    def proposed_key(self) -> str:
        return self.name if self.valid_gitlab_key else gitlab_key(self.name)


@dataclass
class ResourceRef:
    kind: str  # variable_group | service_connection | secure_file | queue | environment | deployment_group | repository | template_repo | pipeline | task_group | container
    name: str
    id: str | None = None
    project: str | None = None
    detail: str | None = None
    resolved: bool = True


@dataclass
class Trigger:
    kind: str  # ci | pr | schedule | pipeline | build_completion | artifact | release_schedule | pull_request | container_image | package | gated | none
    defined_in: str = "yaml"  # yaml | classic | ui (UI override on a YAML pipeline)
    branches_include: list[str] = field(default_factory=list)
    branches_exclude: list[str] = field(default_factory=list)
    paths_include: list[str] = field(default_factory=list)
    paths_exclude: list[str] = field(default_factory=list)
    batch: bool = False
    schedule: str | None = None
    source: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        parts = [self.kind + (" (UI override)" if self.defined_in == "ui" else "")]
        if self.source:
            parts.append(f"from {self.source}")
        if self.branches_include:
            parts.append("branches " + ",".join(self.branches_include))
        if self.branches_exclude:
            parts.append("excl " + ",".join(self.branches_exclude))
        if self.paths_include:
            parts.append("paths " + ",".join(self.paths_include))
        if self.schedule:
            parts.append(self.schedule)
        if self.batch:
            parts.append("batched")
        return " ".join(parts)


@dataclass
class Artifact:
    alias: str
    type: str
    source_name: str | None = None
    source_id: str | None = None
    project: str | None = None
    default_version: str | None = None
    default_branch: str | None = None
    is_primary: bool = False


@dataclass
class Stage:
    name: str
    rank: int = 0
    depends_on: list[str] = field(default_factory=list)
    condition: str | None = None
    trigger: str | None = None
    environment: str | None = None
    environment_id: str | None = None
    jobs: list[Job] = field(default_factory=list)
    approvals: list[Approval] = field(default_factory=list)
    gates: list[Gate] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    variable_groups: list[str] = field(default_factory=list)
    queue_policy: str | None = None
    schedules: list[str] = field(default_factory=list)
    is_deploy: bool = False
    definition_environment_id: int | None = None


@dataclass
class Pipeline:
    key: str
    kind: str  # yaml | classic_build | classic_release
    id: int
    name: str
    project: str
    folder: str = "\\"
    url: str | None = None
    repo_id: str | None = None
    repo_name: str | None = None
    repo_project: str | None = None
    repo_type: str | None = None
    yaml_path: str | None = None
    default_branch: str | None = None
    enabled: bool = True
    draft: bool = False
    created: str | None = None
    modified: str | None = None
    author: str | None = None
    triggers: list[Trigger] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    variable_groups: list[ResourceRef] = field(default_factory=list)
    resources: list[ResourceRef] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    parameters: list[dict[str, Any]] = field(default_factory=list)
    build_number_format: str | None = None
    release_name_format: str | None = None
    timeout_minutes: int | None = None
    job_auth_scope: str | None = None
    checkout: dict[str, Any] = field(default_factory=dict)
    retention: dict[str, Any] | None = None
    templates: list[str] = field(default_factory=list)
    flags: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    depth: str = "deep"  # deep | inventory

    # ------------------------------------------------------------ helpers
    def all_jobs(self) -> list[Job]:
        return [job for stage in self.stages for job in stage.jobs]

    def all_steps(self, enabled_only: bool = True) -> list[Step]:
        return [s for j in self.all_jobs() for s in j.steps if s.enabled or not enabled_only]

    def task_refs(self, enabled_only: bool = True) -> list[str]:
        return [s.task for s in self.all_steps(enabled_only) if s.kind == "task" and s.task]

    def all_variables(self) -> list[Variable]:
        out = list(self.variables)
        for stage in self.stages:
            out.extend(stage.variables)
        return out

    def refs(self, kind: str) -> list[ResourceRef]:
        found = [r for r in self.resources if r.kind == kind]
        if kind == "variable_group":
            found = list(self.variable_groups) + found
        return found

    def deploy_stages(self) -> list[Stage]:
        return [s for s in self.stages if s.is_deploy]

    @property
    def kind_label(self) -> str:
        return {"yaml": "YAML", "classic_build": "Classic build", "classic_release": "Classic release"}.get(self.kind, self.kind)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
