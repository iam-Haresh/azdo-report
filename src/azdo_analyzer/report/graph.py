"""Mermaid dependency graphs (per repo and per project)."""

from __future__ import annotations

from typing import Iterable

from azdo_analyzer.analyze import ProjectResult, RepoResult
from azdo_analyzer.analyze.usage import Edge

_SHAPES = {
    "repo": ('[("', '")]'),
    "external_repo": ('[("', '")]'),
    "yaml": ('(["', '"])'),
    "classic_build": ('(["', '"])'),
    "build_pipeline": ('(["', '"])'),
    "pipeline": ('(["', '"])'),
    "classic_release": ('[["', '"]]'),
}
_PREFIX = {
    "repo": "repo", "external_repo": "ext repo", "yaml": "YAML", "classic_build": "Classic build", "classic_release": "Release",
    "variable_group": "var group", "service_connection": "connection", "secure_file": "secure file", "environment": "env",
    "deployment_group": "deploy group", "template_repo": "templates", "repository": "repo", "queue": "pool", "pipeline": "pipeline",
    "container": "image", "build_pipeline": "build",
}
MAX_NODES = 150


def _label(kind: str, name: str) -> str:
    text = f"{_PREFIX.get(kind, kind)}: {name}".replace('"', "#quot;")
    return text[:80]


class _Graph:
    def __init__(self) -> None:
        self.ids: dict[tuple[str, str], str] = {}
        self.lines: list[str] = []
        self.links: set[tuple[str, str, str]] = set()

    def node(self, kind: str, name: str) -> str:
        key = (kind if kind not in ("yaml", "classic_build", "build_pipeline", "pipeline") else "pipeline-ish", name)
        if key not in self.ids:
            nid = f"n{len(self.ids)}"
            self.ids[key] = nid
            open_, close = _SHAPES.get(kind, ('{{"', '"}}'))
            self.lines.append(f"  {nid}{open_}{_label(kind, name)}{close}")
        return self.ids[key]

    def edge(self, a: str, b: str, label: str) -> None:
        if (a, b, label) not in self.links:
            self.links.add((a, b, label))

    def render(self) -> str:
        out = ["graph LR"] + self.lines + [f"  {a} -->|{label}| {b}" for a, b, label in sorted(self.links)]
        return "\n".join(out)


def _add_edges(graph: _Graph, edges: Iterable[Edge]) -> None:
    for e in edges:
        if len(graph.ids) >= MAX_NODES:
            break
        if e.dst_kind == "queue":
            continue
        a = graph.node(e.src_kind, e.src)
        b = graph.node(e.dst_kind, e.dst)
        graph.edge(a, b, e.relation)


def repo_graph(project: ProjectResult, repo: RepoResult) -> str:
    names = {project.pipelines[k].pipeline.name for k in repo.pipelines + repo.releases if k in project.pipelines}
    graph = _Graph()
    graph.node("repo", repo.name)
    relevant = [e for e in project.usage.edges if e.src in names or e.dst in names or (e.src_kind == "repo" and e.src == repo.name)]
    _add_edges(graph, relevant)
    return graph.render()


def project_graph(project: ProjectResult) -> str:
    users: dict[tuple[str, str], int] = {}
    for e in project.usage.edges:
        if e.relation == "uses":
            users[(e.dst_kind, e.dst)] = users.get((e.dst_kind, e.dst), 0) + 1
    graph = _Graph()
    structural = [e for e in project.usage.edges if e.relation in ("built by", "deployed by", "triggers")]
    shared = [e for e in project.usage.edges if e.relation == "uses" and users.get((e.dst_kind, e.dst), 0) > 1 and e.dst_kind != "queue"]
    _add_edges(graph, structural + shared)
    if len(graph.ids) >= MAX_NODES:
        graph.lines.append(f"  %% truncated at {MAX_NODES} nodes - see the Dependencies sheet")
    return graph.render()
