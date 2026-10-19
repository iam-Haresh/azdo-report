"""Collection orchestration: org-level data, then each selected project."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext, Coverage, write_meta
from azdo_analyzer.collect.builds import collect_builds
from azdo_analyzer.collect.connections import collect_connections
from azdo_analyzer.collect.content import clone_repos
from azdo_analyzer.collect.library import collect_library
from azdo_analyzer.collect.org import ORG, collect_org, collect_projects, select_projects
from azdo_analyzer.collect.releases import collect_releases
from azdo_analyzer.collect.repos import collect_repos, resolve_identities
from azdo_analyzer.collect.resources import collect_resources
from azdo_analyzer.util import iso

__all__ = ["CollectContext", "Coverage", "collect_all", "ORG"]


def collect_project(ctx: CollectContext, project: dict, pat: str | None) -> None:
    p = project["name"]
    repos = collect_repos(ctx, project)
    collect_builds(ctx, project)
    collect_releases(ctx, project)
    library = collect_library(ctx, project)
    endpoints = collect_connections(ctx, project)
    collect_resources(
        ctx,
        project,
        repos=repos,
        variable_groups=library.get("variable_groups") or [],
        secure_files=library.get("secure_files") or [],
        endpoints=endpoints,
    )
    if ctx.deep:
        reviewer_ids: set[str] = set()
        for cfg in ctx.store.read(p, "policy_configurations.json", default=[]) or []:
            reviewer_ids.update((cfg.get("settings") or {}).get("requiredReviewerIds") or [])
        if reviewer_ids:
            resolve_identities(ctx, p, reviewer_ids)
        if ctx.cfg.collection.clone.enabled and pat:
            clone_repos(ctx, project, repos, pat)
    previous = ctx.store.read(p, "_meta.json", default={}) or {}
    depth = "deep" if ctx.deep or previous.get("depth") == "deep" else "inventory"
    extra = {"deep_fetched_at": iso(ctx.now)} if ctx.deep else {}
    write_meta(ctx.store, p, fetched_at=iso(ctx.now), depth=depth, project_id=project["id"], **extra)
    ctx.store.write(ctx.coverage.to_list(p), p, "coverage.json")


def collect_all(
    ctx: CollectContext,
    *,
    requested: list[str] | None,
    all_projects: bool,
    pat: str | None,
) -> list[dict[str, Any]]:
    projects = collect_projects(ctx)
    if not projects:
        raise RuntimeError("No projects returned - check collection_url and that the PAT has 'Project and Team (Read)'.")
    selected = select_projects(ctx, projects, requested, all_projects)
    collect_org(ctx, selected)
    write_meta(ctx.store, ORG, fetched_at=iso(ctx.now), collection_url=ctx.cfg.azdo.collection_url)
    ctx.store.write(ctx.coverage.to_list(ORG), ORG, "coverage.json")
    for project in selected:
        collect_project(ctx, project, pat)
    return selected
