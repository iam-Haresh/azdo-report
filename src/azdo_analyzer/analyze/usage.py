"""Usage graph: which repos/pipelines/releases use which shared resources."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from azdo_analyzer.model import Pipeline
from azdo_analyzer.rawdata import ProjectRaw
from azdo_analyzer.util import parse_dt


@dataclass(frozen=True)
class Edge:
    project: str
    src_kind: str
    src: str
    relation: str
    dst_kind: str
    dst: str
    dst_project: str | None = None
    evidence: str = ""


@dataclass
class Usage:
    edges: list[Edge] = field(default_factory=list)
    repo_pipelines: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    repo_releases: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    pipeline_repos: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    resource_users: dict[tuple[str, str], set[str]] = field(default_factory=lambda: defaultdict(set))
    template_users: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    endpoint_history: dict[str, dict[str, Any]] = field(default_factory=dict)
    authorizations: dict[str, dict[str, Any]] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)
    external: list[str] = field(default_factory=list)

    def users(self, kind: str, ident: str | None) -> set[str]:
        return self.resource_users.get((kind, (ident or "").lower()), set())


def resource_key(kind: str, ident: str | None, name: str | None) -> tuple[str, str]:
    by_name = kind in ("queue", "environment", "repository", "template_repo", "container")
    return kind, ((name if by_name else ident) or name or ident or "").lower()


def build_usage(raw: ProjectRaw, pipelines: list[Pipeline]) -> Usage:
    usage = Usage()
    edges: set[Edge] = set()
    p_name = raw.name
    repos_by_id = {r["id"]: r for r in raw.repos}
    repos_by_name = {r["name"].lower(): r for r in raw.repos}
    builds_by_id = {p.id: p for p in pipelines if p.kind != "classic_release"}
    keys = {p.key for p in pipelines}

    for p in pipelines:
        if p.kind != "classic_release":
            repo = repos_by_id.get(p.repo_id or "")
            if repo:
                usage.repo_pipelines[repo["id"]].append(p.key)
                usage.pipeline_repos[p.key].append(repo["id"])
                if repo.get("isDisabled"):
                    usage.orphans.append(p.key)
                edges.add(Edge(p_name, "repo", repo["name"], "built by", p.kind, p.name, evidence="definition repository"))
            elif p.repo_type in (None, "TfsGit"):
                if p.repo_id or p.repo_name:
                    usage.orphans.append(p.key)
            else:
                usage.external.append(p.key)
                edges.add(Edge(p_name, "external_repo", f"{p.repo_type}:{p.repo_name}", "built by", p.kind, p.name, evidence="definition repository"))
        else:
            for a in p.artifacts:
                if a.type == "Build":
                    same = a.project in (None, p_name)
                    build = builds_by_id.get(int(a.source_id)) if same and (a.source_id or "").isdigit() else None
                    if build:
                        edges.add(Edge(p_name, build.kind, build.name, "deployed by", "classic_release", p.name, evidence=f"artifact {a.alias}"))
                        for rid in usage.pipeline_repos.get(build.key, []) or ([build.repo_id] if build.repo_id in repos_by_id else []):
                            if p.key not in usage.repo_releases[rid]:
                                usage.repo_releases[rid].append(p.key)
                                usage.pipeline_repos[p.key].append(rid)
                    else:
                        edges.add(Edge(p_name, "build_pipeline", a.source_name or str(a.source_id), "deployed by", "classic_release", p.name,
                                       dst_project=a.project, evidence=f"artifact {a.alias}" + ("" if same else " (other project)")))
                elif a.type in ("Git", "TFVC"):
                    repo = repos_by_id.get(a.source_id or "") or repos_by_name.get((a.source_name or "").lower())
                    if repo:
                        if p.key not in usage.repo_releases[repo["id"]]:
                            usage.repo_releases[repo["id"]].append(p.key)
                            usage.pipeline_repos[p.key].append(repo["id"])
                        edges.add(Edge(p_name, "repo", repo["name"], "deployed by", "classic_release", p.name, evidence=f"git artifact {a.alias}"))
                else:
                    edges.add(Edge(p_name, "artifact", f"{a.type}:{a.source_name or a.alias}", "consumed by", "classic_release", p.name, evidence=f"artifact {a.alias}"))
        for ref in p.resources:
            if ref.kind in ("template_repo", "repository") and "/" in (ref.name or ""):
                ref_project, _, ref_repo = ref.name.rpartition("/")
                repo = repos_by_name.get(ref_repo.lower()) if ref_project in ("", p_name) else None
                if repo:
                    usage.template_users[repo["id"]].add(p.key)
        for ref in p.refs("variable_group") + [r for r in p.resources if r.kind != "variable_group"]:
            usage.resource_users[resource_key(ref.kind, ref.id, ref.name)].add(p.key)
            edges.add(Edge(p_name, p.kind, p.name, "uses", ref.kind, ref.name or str(ref.id), dst_project=ref.project if ref.project != p_name else None,
                           evidence=ref.detail or ""))
        for t in p.triggers:
            if t.kind in ("build_completion", "pipeline"):
                upstream_project = (t.detail or {}).get("project")
                edges.add(Edge(p_name, "pipeline", t.source or "?", "triggers", p.kind, p.name,
                               dst_project=upstream_project if upstream_project not in (None, p_name) else None, evidence=t.kind))

    for group in raw.variable_groups:
        ep_id = (group.get("providerData") or {}).get("serviceEndpointId")
        if ep_id:
            users = usage.resource_users.get(("variable_group", str(group.get("id")).lower()), set())
            usage.resource_users[("service_connection", str(ep_id).lower())].update(users)
            edges.add(Edge(p_name, "variable_group", group.get("name") or "?", "uses", "service_connection",
                           next((e.get("name") for e in raw.endpoints if str(e.get("id")).lower() == str(ep_id).lower()), str(ep_id)),
                           evidence="Key Vault link"))

    for ep_id, records in raw.endpoint_history.items():
        info: dict[str, Any] = {"runs": 0, "last": None, "definitions": set()}
        for rec in records:
            data = rec.get("data") or rec
            info["runs"] += 1
            when: datetime | None = parse_dt(data.get("finishTime") or data.get("startTime"))
            if when and (info["last"] is None or when > info["last"]):
                info["last"] = when
            definition = data.get("definition") or {}
            if definition.get("name"):
                info["definitions"].add(definition["name"])
            plan = str(data.get("planType") or "").lower()
            key = f"{'release' if plan == 'release' else 'build'}:{p_name}:{definition.get('id')}"
            if key in keys:
                usage.resource_users[("service_connection", ep_id.lower())].add(key)
        usage.endpoint_history[ep_id.lower()] = info

    for key, perm in raw.permissions.items():
        usage.authorizations[key] = {
            "all": bool((perm.get("allPipelines") or {}).get("authorized")),
            "pipelines": [x.get("id") for x in perm.get("pipelines") or [] if x.get("authorized")],
        }
    usage.edges = sorted(edges, key=lambda e: (e.src_kind, e.src, e.relation, e.dst_kind, e.dst))
    return usage
