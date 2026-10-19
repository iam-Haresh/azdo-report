"""Classic release definitions and deployment history."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def slim_deployment(d: dict) -> dict:
    return {
        "id": d.get("id"),
        "releaseDefinition": {"id": (d.get("releaseDefinition") or {}).get("id"), "name": (d.get("releaseDefinition") or {}).get("name")},
        "release": {"id": (d.get("release") or {}).get("id"), "name": (d.get("release") or {}).get("name")},
        "releaseEnvironment": {"id": (d.get("releaseEnvironment") or {}).get("id"), "name": (d.get("releaseEnvironment") or {}).get("name")},
        "definitionEnvironmentId": d.get("definitionEnvironmentId"),
        "deploymentStatus": d.get("deploymentStatus"),
        "operationStatus": d.get("operationStatus"),
        "reason": d.get("reason"),
        "attempt": d.get("attempt"),
        "queuedOn": d.get("queuedOn"),
        "startedOn": d.get("startedOn"),
        "completedOn": d.get("completedOn"),
        "requestedFor": (d.get("requestedFor") or {}).get("displayName"),
    }


def collect_releases(ctx: CollectContext, project: dict) -> dict[str, Any]:
    c, p = ctx.client, project["name"]
    defs = ctx.fetch(
        (p, "release_definitions.json"),
        lambda: list(
            c.paged(
                "release/definitions",
                {"$expand": "environments,artifacts,triggers,lastRelease", "$top": 500},
                project=p,
            )
        ),
        scope=p,
        collector="releases",
        endpoint="release/definitions",
    ) or []
    ctx.progress(f"{p}: {len(defs)} classic release definitions")

    if ctx.deep:
        ctx.pmap(
            lambda d: ctx.fetch(
                (p, "release_definition", f"{d['id']}.json"),
                lambda: c.get_json(f"release/definitions/{d['id']}", project=p),
                scope=p,
                collector="releases",
                endpoint="release/definitions/{id}",
            ),
            defs,
        )

    since = ctx.history_start()
    deployments = ctx.fetch(
        (p, "deployments.json"),
        lambda: [
            slim_deployment(d)
            for d in c.paged(
                "release/deployments",
                {"minStartedTime": since, "queryOrder": "descending", "$top": 1000},
                project=p,
            )
        ],
        scope=p,
        collector="releases",
        endpoint="release/deployments",
    ) or []
    return {"definitions": defs, "deployments": deployments}
