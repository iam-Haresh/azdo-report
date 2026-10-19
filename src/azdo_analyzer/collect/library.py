"""Library items: variable groups, secure files, task groups, project feeds, wikis."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def collect_library(ctx: CollectContext, project: dict) -> dict[str, Any]:
    c, p = ctx.client, project["name"]
    out: dict[str, Any] = {}
    # Secret values are never returned by the API (they come back as null).
    out["variable_groups"] = ctx.fetch(
        (p, "variable_groups.json"),
        lambda: list(c.paged("distributedtask/variablegroups", {"$top": 500}, project=p)),
        scope=p,
        collector="library",
        endpoint="distributedtask/variablegroups",
    )
    out["secure_files"] = ctx.fetch(
        (p, "secure_files.json"),
        lambda: c.get_list("distributedtask/securefiles", project=p),
        scope=p,
        collector="library",
        endpoint="distributedtask/securefiles",
    )
    out["feeds"] = ctx.fetch(
        (p, "feeds.json"),
        lambda: c.get_list("packaging/feeds", project=p),
        scope=p,
        collector="library",
        endpoint="packaging/feeds (project)",
    )
    if ctx.deep:
        out["task_groups"] = ctx.fetch(
            (p, "task_groups.json"),
            lambda: c.get_list("distributedtask/taskgroups", project=p),
            scope=p,
            collector="library",
            endpoint="distributedtask/taskgroups",
        )
        out["wikis"] = ctx.fetch(
            (p, "wikis.json"),
            lambda: c.get_list("wiki/wikis", project=p),
            scope=p,
            collector="library",
            endpoint="wiki/wikis",
        )
    return out
