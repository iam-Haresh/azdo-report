"""Typed views over the raw JSON cache (everything analysis needs, read offline)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from azdo_analyzer.cache import RawStore

ORG = "_org"


@dataclass
class OrgRaw:
    projects: list[dict] = field(default_factory=list)
    project_details: dict[str, dict] = field(default_factory=dict)
    tasks: list[dict] = field(default_factory=list)
    extensions: list[dict] = field(default_factory=list)
    pools: list[dict] = field(default_factory=list)
    agents: dict[int, list[dict]] = field(default_factory=dict)
    feeds: list[dict] = field(default_factory=list)
    hooks: list[dict] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    coverage: list[dict] = field(default_factory=list)

    def project(self, name: str) -> dict | None:
        return next((p for p in self.projects if p.get("name", "").lower() == name.lower()), None)


@dataclass
class ProjectRaw:
    name: str
    id: str
    meta: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    repos: list[dict] = field(default_factory=list)
    branch_stats: dict[str, list[dict]] = field(default_factory=dict)
    tags: dict[str, list[dict]] = field(default_factory=dict)
    open_prs: dict[str, list[dict]] = field(default_factory=dict)
    clone_status: dict[str, str] = field(default_factory=dict)
    policies: list[dict] = field(default_factory=list)
    tfvc_changesets: list[dict] | None = None
    build_definitions: list[dict] = field(default_factory=list)
    build_definitions_full: dict[int, dict] = field(default_factory=dict)
    builds: list[dict] = field(default_factory=list)
    timelines: dict[int, list[dict]] = field(default_factory=dict)
    release_definitions: list[dict] = field(default_factory=list)
    release_definitions_full: dict[int, dict] = field(default_factory=dict)
    deployments: list[dict] = field(default_factory=list)
    variable_groups: list[dict] = field(default_factory=list)
    secure_files: list[dict] = field(default_factory=list)
    task_groups: list[dict] = field(default_factory=list)
    feeds: list[dict] = field(default_factory=list)
    wikis: list[dict] = field(default_factory=list)
    endpoints: list[dict] = field(default_factory=list)
    endpoint_history: dict[str, list[dict]] = field(default_factory=dict)
    queues: list[dict] = field(default_factory=list)
    environments: list[dict] = field(default_factory=list)
    environment_details: dict[int, dict] = field(default_factory=dict)
    environment_deployments: dict[int, list[dict]] = field(default_factory=dict)
    deployment_groups: list[dict] = field(default_factory=list)
    checks: dict[str, list[dict]] = field(default_factory=dict)
    permissions: dict[str, dict] = field(default_factory=dict)
    identities: dict[str, dict] = field(default_factory=dict)
    coverage: list[dict] = field(default_factory=list)

    @property
    def deep(self) -> bool:
        return self.meta.get("depth") == "deep"


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _json_files(store: RawStore, *parts: Any) -> dict[str, Any]:
    folder = store.path(*parts)
    if not folder.is_dir():
        return {}
    out = {}
    for path in sorted(folder.glob("*.json")):
        data = store.read(*parts, path.name)
        if data is not None:
            out[path.stem] = data
    return out


def load_org(store: RawStore) -> OrgRaw:
    org = OrgRaw()
    org.projects = _list(store.read(ORG, "projects.json"))
    org.project_details = _json_files(store, ORG, "project_details")
    org.tasks = _list(store.read(ORG, "tasks.json"))
    org.extensions = _list(store.read(ORG, "extensions.json"))
    org.pools = _list(store.read(ORG, "pools.json"))
    org.agents = {int(k): _list(v) for k, v in _json_files(store, ORG, "agents").items() if k.isdigit()}
    org.feeds = _list(store.read(ORG, "feeds.json"))
    org.hooks = _list(store.read(ORG, "hooks.json"))
    org.meta = store.read(ORG, "_meta.json", default={}) or {}
    org.coverage = _list(store.read(ORG, "coverage.json"))
    return org


def load_project(store: RawStore, name: str, project_id: str | None = None) -> ProjectRaw:
    meta = store.read(name, "_meta.json", default={}) or {}
    raw = ProjectRaw(name=name, id=project_id or meta.get("project_id") or "", meta=meta)
    raw.details = store.read(ORG, "project_details", f"{raw.id}.json", default={}) if raw.id else {}
    raw.repos = _list(store.read(name, "repos.json"))
    for repo in raw.repos:
        rid = repo["id"]
        raw.branch_stats[rid] = _list(store.read(name, "repo", rid, "branch_stats.json"))
        raw.tags[rid] = _list(store.read(name, "repo", rid, "tags.json"))
        raw.open_prs[rid] = _list(store.read(name, "repo", rid, "open_prs.json"))
    raw.clone_status = store.read(name, "clone_status.json", default={}) or {}
    raw.policies = _list(store.read(name, "policy_configurations.json"))
    tfvc = store.read(name, "tfvc_changesets.json")
    raw.tfvc_changesets = tfvc if isinstance(tfvc, list) else None
    raw.build_definitions = _list(store.read(name, "build_definitions.json"))
    raw.build_definitions_full = {int(k): v for k, v in _json_files(store, name, "build_definition").items() if k.isdigit()}
    raw.builds = _list(store.read(name, "builds.json"))
    raw.timelines = {int(k): _list(v) for k, v in _json_files(store, name, "timeline").items() if k.isdigit()}
    raw.release_definitions = _list(store.read(name, "release_definitions.json"))
    raw.release_definitions_full = {int(k): v for k, v in _json_files(store, name, "release_definition").items() if k.isdigit()}
    raw.deployments = _list(store.read(name, "deployments.json"))
    raw.variable_groups = _list(store.read(name, "variable_groups.json"))
    raw.secure_files = _list(store.read(name, "secure_files.json"))
    raw.task_groups = _list(store.read(name, "task_groups.json"))
    raw.feeds = _list(store.read(name, "feeds.json"))
    raw.wikis = _list(store.read(name, "wikis.json"))
    raw.endpoints = _list(store.read(name, "service_endpoints.json"))
    raw.endpoint_history = {k: _list(v) for k, v in _json_files(store, name, "endpoint_history").items()}
    raw.queues = _list(store.read(name, "queues.json"))
    raw.environments = _list(store.read(name, "environments.json"))
    raw.environment_details = {int(k): v for k, v in _json_files(store, name, "environment").items() if k.isdigit()}
    raw.environment_deployments = {int(k): _list(v) for k, v in _json_files(store, name, "environment_deployments").items() if k.isdigit()}
    raw.deployment_groups = _list(store.read(name, "deployment_groups.json"))
    raw.checks = {k: _list(v) for k, v in _json_files(store, name, "checks").items()}
    raw.permissions = {k: v for k, v in _json_files(store, name, "pipeline_permissions").items() if isinstance(v, dict)}
    raw.identities = store.read(name, "identities.json", default={}) or {}
    raw.coverage = _list(store.read(name, "coverage.json"))
    return raw
