"""Collection-level data: projects, task catalog, extensions, agent pools, feeds, hooks."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext

ORG = "_org"


def collect_projects(ctx: CollectContext) -> list[dict]:
    c = ctx.client
    projects = ctx.fetch(
        (ORG, "projects.json"),
        lambda: list(c.paged("projects", {"$top": 1000, "stateFilter": "wellFormed"})),
        scope=ORG,
        collector="org",
        endpoint="projects",
    )
    return projects or []


def select_projects(ctx: CollectContext, projects: list[dict], requested: list[str] | None, all_projects: bool) -> list[dict]:
    names = {p["name"].lower(): p for p in projects}
    excluded = {n.lower() for n in ctx.cfg.scope.exclude_projects}
    if requested:
        missing = [n for n in requested if n.lower() not in names]
        if missing:
            raise ValueError(f"Project(s) not found in collection: {', '.join(missing)}")
        chosen = [names[n.lower()] for n in requested]
    elif all_projects or not ctx.cfg.scope.projects:
        chosen = list(projects)
    else:
        chosen = [names[n.lower()] for n in ctx.cfg.scope.projects if n.lower() in names]
    return sorted((p for p in chosen if p["name"].lower() not in excluded), key=lambda p: p["name"].lower())


def collect_org(ctx: CollectContext, projects: list[dict]) -> dict[str, Any]:
    c = ctx.client
    ctx.progress("collection-level data (task catalog, extensions, pools, feeds, hooks)")

    def project_details(project: dict) -> Any:
        pid = project["id"]
        return ctx.fetch(
            (ORG, "project_details", f"{pid}.json"),
            lambda: c.get_json(f"projects/{pid}", {"includeCapabilities": "true"}),
            scope=ORG,
            collector="org",
            endpoint="projects/{id}?includeCapabilities",
        )

    ctx.pmap(project_details, projects)

    out: dict[str, Any] = {}
    out["tasks"] = ctx.fetch(
        (ORG, "tasks.json"), lambda: c.get_list("distributedtask/tasks"), scope=ORG, collector="org", endpoint="distributedtask/tasks"
    )
    out["extensions"] = ctx.fetch(
        (ORG, "extensions.json"),
        lambda: c.get_list("extensionmanagement/installedextensions"),
        scope=ORG,
        collector="org",
        endpoint="extensionmanagement/installedextensions",
    )
    pools = ctx.fetch(
        (ORG, "pools.json"), lambda: c.get_list("distributedtask/pools"), scope=ORG, collector="org", endpoint="distributedtask/pools"
    ) or []

    def agents(pool: dict) -> Any:
        pid = pool["id"]
        return ctx.fetch(
            (ORG, "agents", f"{pid}.json"),
            lambda: c.get_list(
                f"distributedtask/pools/{pid}/agents",
                {"includeCapabilities": "true", "includeLastCompletedRequest": "true"},
            ),
            scope=ORG,
            collector="org",
            endpoint="distributedtask/pools/{id}/agents",
        )

    ctx.pmap(agents, [p for p in pools if not p.get("isHosted")])
    out["feeds"] = ctx.fetch(
        (ORG, "feeds.json"), lambda: c.get_list("packaging/feeds"), scope=ORG, collector="org", endpoint="packaging/feeds"
    )
    out["hooks"] = ctx.fetch(
        (ORG, "hooks.json"), lambda: c.get_list("hooks/subscriptions"), scope=ORG, collector="org", endpoint="hooks/subscriptions"
    )
    return out
