"""Archetype detection (stack x build tool x deploy target x artifact) and pipeline fingerprints."""

from __future__ import annotations

import fnmatch
import posixpath
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from azdo_analyzer.model import Pipeline
from azdo_analyzer.rules import Rules
from azdo_analyzer.util import short_hash

_TOOL_TO_STACK = {
    "maven": "java-maven",
    "gradle": "java-gradle",
    "ant": "java-ant",
    "msbuild": "dotnet-framework",
    "dotnet": "dotnet",
    "nuget": "dotnet",
    "npm": "node",
    "python": "python",
    "go": "go",
    "terraform": "terraform",
}
_BOILERPLATE = {"checkout", "download", "publish"}
_TOOL_PRIORITY = ["maven", "gradle", "ant", "msbuild", "dotnet", "npm", "python", "go", "terraform", "nuget", "docker"]


@dataclass
class RepoProfile:
    stack: str = "unknown"
    stacks: list[str] = field(default_factory=list)
    build_tool: str = "none"
    deploy_targets: list[str] = field(default_factory=list)
    artifact: str = "none"
    markers: list[str] = field(default_factory=list)
    windows: bool = False
    key: str = ""
    name: str = "custom"
    template: str | None = None
    source: str = "content"  # content | tasks


def _match(files: list[str], patterns: list[str]) -> list[str]:
    hits = []
    for rel in files:
        base = posixpath.basename(rel)
        for pattern in patterns:
            if ("/" in pattern and fnmatch.fnmatch(rel, pattern)) or fnmatch.fnmatch(base, pattern):
                hits.append(rel)
                break
    return hits


def detect_stack(files: list[str], read: Callable[[str], str | None], rules: Rules) -> tuple[str, list[str], bool]:
    stacks, primary, windows = [], "unknown", False
    for rule in rules.archetypes.get("stacks") or []:
        hits = _match(files, rule.get("files") or [])
        if not hits:
            continue
        regex = rule.get("content_regex")
        if regex:
            pattern = re.compile(regex, re.I)
            if not any(pattern.search(read(rel) or "") for rel in hits[:25]):
                continue
        if rule["id"] not in stacks:
            stacks.append(rule["id"])
        if primary == "unknown":
            primary = rule["id"]
            windows = bool(rule.get("windows"))
    if primary == "dotnet-framework" and "dotnet" in stacks:
        stacks.remove("dotnet")
    return primary, stacks, windows


def _task_name(ref: str | None) -> str:
    return (ref or "").split("@", 1)[0]


def profile_repo(
    files: list[str],
    read: Callable[[str], str | None],
    pipelines: list[Pipeline],
    endpoint_types: dict[str, str],
    rules: Rules,
) -> RepoProfile:
    cfg = rules.archetypes
    profile = RepoProfile()
    if files:
        profile.stack, profile.stacks, profile.windows = detect_stack(files, read, rules)
        profile.markers = [m for m, pats in (cfg.get("markers") or {}).items() if _match(files, pats)]
    steps = [s for p in pipelines for s in p.all_steps()]
    task_names = [_task_name(s.task) for s in steps if s.task]
    tools = cfg.get("build_tools") or {}
    found_tools = [tools[t] for t in task_names if t in tools]
    ranked = sorted(set(found_tools), key=lambda t: _TOOL_PRIORITY.index(t) if t in _TOOL_PRIORITY else len(_TOOL_PRIORITY))
    profile.build_tool = (ranked[0] if ranked else None) or (cfg.get("stack_default_tool") or {}).get(profile.stack, "none")
    if profile.stack == "unknown" and profile.build_tool in _TOOL_TO_STACK:
        profile.stack = _TOOL_TO_STACK[profile.build_tool]
        profile.stacks = [profile.stack]
        profile.source = "tasks"
        profile.windows = profile.stack == "dotnet-framework"

    scripts = "\n".join(s.script or "" for s in steps) + "\n" + "\n".join(
        str(v) for s in steps for v in (s.inputs or {}).values() if isinstance(v, str)
    )
    used_endpoint_types = {endpoint_types.get(r.id or "", "") for p in pipelines for r in p.refs("service_connection")}
    has_deployment_group = any(j.kind == "deployment_group" for p in pipelines for j in p.all_jobs())
    targets = []
    for target, rule in (cfg.get("deploy_targets") or {}).items():
        hit = bool(set(rule.get("tasks") or []) & set(task_names))
        hit = hit or bool(set(rule.get("endpoint_types") or []) & used_endpoint_types)
        hit = hit or bool(rule.get("deployment_group") and has_deployment_group)
        if not hit and rule.get("script_regex"):
            hit = bool(re.search(rule["script_regex"], scripts))
        if hit:
            targets.append(target)
    profile.deploy_targets = targets

    profile.artifact = "none"
    for rule in cfg.get("artifact_rules") or []:
        hit = bool(set(rule.get("tasks") or []) & set(task_names))
        hit = hit or bool(set(rule.get("markers") or []) & set(profile.markers))
        if not hit and rule.get("script_regex"):
            hit = bool(re.search(rule["script_regex"], scripts))
        if not hit and rule.get("task_inputs"):
            for step in steps:
                spec = (rule["task_inputs"] or {}).get(_task_name(step.task))
                if not spec:
                    continue
                for key, values in spec.items():
                    actual = str((step.inputs or {}).get(key, "")).lower()
                    if any(str(v).lower() in actual.split() or str(v).lower() == actual for v in values):
                        hit = True
        if hit:
            profile.artifact = rule["id"]
            break

    deploy = "+".join(sorted(profile.deploy_targets)) or "none"
    profile.key = f"{profile.stack} | {profile.build_tool} | {deploy} | {profile.artifact}"
    for named in cfg.get("named") or []:
        if named.get("stack") and named["stack"] != profile.stack:
            continue
        if named.get("artifact") and named["artifact"] != profile.artifact:
            continue
        want = named.get("deploy")
        if want == "none" and profile.deploy_targets:
            continue
        if want and want != "none" and want not in profile.deploy_targets:
            continue
        profile.name, profile.template = named.get("name", "custom"), named.get("template")
        break
    return profile


def fingerprint(pipeline: Pipeline) -> str | None:
    refs = [s.task for s in pipeline.all_steps() if s.task and s.task not in _BOILERPLATE]
    if len(refs) < 2:
        return None
    return short_hash(pipeline.kind, *refs)


def clone_clusters(pipelines: list[Pipeline], threshold: float = 0.8) -> list[dict[str, Any]]:
    """Exact clones (same fingerprint) and near clones (Jaccard on task sets >= threshold)."""
    exact: dict[str, list[Pipeline]] = defaultdict(list)
    for p in pipelines:
        fp = fingerprint(p)
        if fp:
            exact[fp].append(p)
    clusters = [
        {"type": "identical", "fingerprint": fp, "pipelines": [f"{p.project}/{p.name}" for p in items], "tasks": " > ".join(items[0].task_refs())}
        for fp, items in exact.items()
        if len(items) > 1
    ]
    singles = [items[0] for items in exact.values() if len(items) == 1]
    sets = [(p, set(p.task_refs())) for p in singles]
    used: set[str] = set()
    for i, (p, s) in enumerate(sets):
        if p.key in used or not s:
            continue
        group = [p]
        for q, t in sets[i + 1:]:
            if q.key in used or not t or p.kind != q.kind:
                continue
            if len(s & t) / len(s | t) >= threshold:
                group.append(q)
                used.add(q.key)
        if len(group) > 1:
            used.add(p.key)
            clusters.append({"type": f"similar (>= {int(threshold * 100)}%)", "fingerprint": fingerprint(p),
                             "pipelines": [f"{x.project}/{x.name}" for x in group], "tasks": " > ".join(p.task_refs())})
    return clusters
