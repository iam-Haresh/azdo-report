"""Service connections (endpoints) and their execution history."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def collect_connections(ctx: CollectContext, project: dict) -> list[dict]:
    c, p = ctx.client, project["name"]
    endpoints = ctx.fetch(
        (p, "service_endpoints.json"),
        lambda: c.get_list("serviceendpoint/endpoints", {"includeFailed": "true"}, project=p),
        scope=p,
        collector="connections",
        endpoint="serviceendpoint/endpoints",
    ) or []
    if ctx.deep:
        ctx.pmap(
            lambda ep: ctx.fetch(
                (p, "endpoint_history", f"{ep['id']}.json"),
                lambda: c.get_list(f"serviceendpoint/{ep['id']}/executionhistory", {"top": 50}, project=p),
                scope=p,
                collector="connections",
                endpoint="serviceendpoint/{id}/executionhistory",
            ),
            endpoints,
        )
    return endpoints


def endpoint_summary(ep: dict[str, Any]) -> dict[str, Any]:
    """Non-sensitive view of an endpoint (never includes authorization parameters)."""
    auth = ep.get("authorization") or {}
    return {
        "id": ep.get("id"),
        "name": ep.get("name"),
        "type": ep.get("type"),
        "url": ep.get("url"),
        "scheme": auth.get("scheme"),
        "isShared": ep.get("isShared"),
        "isReady": ep.get("isReady"),
        "owner": ep.get("owner"),
        "description": ep.get("description"),
        "projects": [
            (ref.get("projectReference") or {}).get("name")
            for ref in ep.get("serviceEndpointProjectReferences") or []
            if (ref.get("projectReference") or {}).get("name")
        ],
    }
