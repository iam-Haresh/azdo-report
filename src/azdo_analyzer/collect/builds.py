"""Build/YAML pipeline definitions, run history and timelines."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def slim_build(b: dict) -> dict:
    queue = b.get("queue") or {}
    return {
        "id": b.get("id"),
        "buildNumber": b.get("buildNumber"),
        "status": b.get("status"),
        "result": b.get("result"),
        "queueTime": b.get("queueTime"),
        "startTime": b.get("startTime"),
        "finishTime": b.get("finishTime"),
        "reason": b.get("reason"),
        "sourceBranch": b.get("sourceBranch"),
        "sourceVersion": b.get("sourceVersion"),
        "definition": {"id": (b.get("definition") or {}).get("id"), "name": (b.get("definition") or {}).get("name")},
        "queue": {"id": queue.get("id"), "name": queue.get("name"), "pool": (queue.get("pool") or {}).get("name")},
        "requestedFor": (b.get("requestedFor") or {}).get("displayName"),
        "repository": {"id": (b.get("repository") or {}).get("id"), "type": (b.get("repository") or {}).get("type")},
    }


def slim_timeline(t: dict | None) -> list[dict]:
    out = []
    for r in (t or {}).get("records") or []:
        task = r.get("task") or None
        out.append(
            {
                "id": r.get("id"),
                "parentId": r.get("parentId"),
                "type": r.get("type"),
                "name": r.get("name"),
                "order": r.get("order"),
                "result": r.get("result"),
                "startTime": r.get("startTime"),
                "finishTime": r.get("finishTime"),
                "workerName": r.get("workerName"),
                "task": {"id": task.get("id"), "name": task.get("name"), "version": task.get("version")} if task else None,
            }
        )
    return out


def collect_builds(ctx: CollectContext, project: dict) -> dict[str, Any]:
    c, p = ctx.client, project["name"]
    defs = ctx.fetch(
        (p, "build_definitions.json"),
        lambda: list(
            c.paged(
                "build/definitions",
                {"includeAllProperties": "true", "includeLatestBuilds": "true", "$top": 500},
                project=p,
            )
        ),
        scope=p,
        collector="builds",
        endpoint="build/definitions",
    ) or []
    ctx.progress(f"{p}: {len(defs)} build/YAML pipeline definitions")

    if ctx.deep:
        ctx.pmap(
            lambda d: ctx.fetch(
                (p, "build_definition", f"{d['id']}.json"),
                lambda: c.get_json(f"build/definitions/{d['id']}", project=p),
                scope=p,
                collector="builds",
                endpoint="build/definitions/{id}",
            ),
            defs,
        )

    since = ctx.history_start()
    builds = ctx.fetch(
        (p, "builds.json"),
        lambda: [
            slim_build(b)
            for b in c.paged(
                "build/builds",
                {"minTime": since, "queryOrder": "finishTimeDescending", "statusFilter": "completed", "$top": 1000},
                project=p,
            )
        ],
        scope=p,
        collector="builds",
        endpoint="build/builds",
    ) or []

    if ctx.deep:
        latest = latest_good_build_per_definition(builds, defs)
        ctx.pmap(
            lambda bid: ctx.fetch(
                (p, "timeline", f"{bid}.json"),
                lambda: slim_timeline(c.get_json(f"build/builds/{bid}/timeline", project=p)),
                scope=p,
                collector="builds",
                endpoint="build/builds/{id}/timeline",
            ),
            sorted(set(latest.values())),
        )
    return {"definitions": defs, "builds": builds}


def latest_good_build_per_definition(builds: list[dict], defs: list[dict]) -> dict[int, int]:
    """Definition id -> id of the latest succeeded/partially succeeded run (default branch preferred)."""
    default_branch = {d["id"]: (d.get("repository") or {}).get("defaultBranch") for d in defs}
    best: dict[int, tuple[int, str, int]] = {}
    for b in builds:
        did = (b.get("definition") or {}).get("id")
        if did is None or b.get("result") not in ("succeeded", "partiallySucceeded"):
            continue
        on_default = 1 if b.get("sourceBranch") == default_branch.get(did) else 0
        key = (on_default, b.get("finishTime") or "", b["id"])
        if did not in best or key > best[did]:
            best[did] = key
    return {did: key[2] for did, key in best.items()}
