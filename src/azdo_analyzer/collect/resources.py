"""Agent queues, YAML environments, deployment groups, checks and pipeline authorizations."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.collect.base import CollectContext


def collect_resources(
    ctx: CollectContext,
    project: dict,
    *,
    repos: list[dict],
    variable_groups: list[dict],
    secure_files: list[dict],
    endpoints: list[dict],
) -> dict[str, Any]:
    c, p = ctx.client, project["name"]
    out: dict[str, Any] = {}
    out["queues"] = ctx.fetch(
        (p, "queues.json"),
        lambda: c.get_list("distributedtask/queues", project=p),
        scope=p,
        collector="resources",
        endpoint="distributedtask/queues",
    ) or []
    if not ctx.deep:
        return out

    # Environments and deployment groups need the "Read & manage" PAT scopes;
    # without them these calls are recorded as FORBIDDEN in Coverage.
    envs = ctx.fetch(
        (p, "environments.json"),
        lambda: list(c.paged("distributedtask/environments", {"$top": 500}, project=p)),
        scope=p,
        collector="resources",
        endpoint="distributedtask/environments",
    ) or []
    out["environments"] = envs

    def env_detail(env: dict) -> None:
        eid = env["id"]
        ctx.fetch(
            (p, "environment", f"{eid}.json"),
            lambda: c.get_json(f"distributedtask/environments/{eid}", {"expands": "resourceReferences"}, project=p),
            scope=p,
            collector="resources",
            endpoint="distributedtask/environments/{id}",
        )
        ctx.fetch(
            (p, "environment_deployments", f"{eid}.json"),
            lambda: c.get_list(f"distributedtask/environments/{eid}/environmentdeploymentrecords", {"top": 50}, project=p),
            scope=p,
            collector="resources",
            endpoint="distributedtask/environments/{id}/environmentdeploymentrecords",
        )

    ctx.pmap(env_detail, envs)
    out["deployment_groups"] = ctx.fetch(
        (p, "deployment_groups.json"),
        lambda: list(c.paged("distributedtask/deploymentgroups", {"$expand": "machines", "$top": 500}, project=p)),
        scope=p,
        collector="resources",
        endpoint="distributedtask/deploymentgroups",
    ) or []

    project_id = project["id"]
    targets: list[tuple[str, str]] = []
    targets += [("environment", str(e["id"])) for e in envs]
    targets += [("queue", str(q["id"])) for q in out["queues"]]
    targets += [("endpoint", str(e["id"])) for e in endpoints]
    targets += [("variablegroup", str(v["id"])) for v in variable_groups]
    targets += [("securefile", str(s["id"])) for s in secure_files]
    targets += [("repository", f"{project_id}.{r['id']}") for r in repos if not r.get("isDisabled")]

    def checks_and_permissions(target: tuple[str, str]) -> None:
        rtype, rid = target
        ctx.fetch(
            (p, "checks", f"{rtype}_{rid}.json"),
            lambda: c.get_list(
                "pipelines/checks/configurations",
                {"resourceType": rtype, "resourceId": rid, "$expand": "settings"},
                project=p,
            ),
            scope=p,
            collector="resources",
            endpoint="pipelines/checks/configurations",
        )
        ctx.fetch(
            (p, "pipeline_permissions", f"{rtype}_{rid}.json"),
            lambda: c.get_json(f"pipelines/pipelinepermissions/{rtype}/{rid}", project=p),
            scope=p,
            collector="resources",
            endpoint="pipelines/pipelinepermissions",
        )

    ctx.progress(f"{p}: checks and pipeline authorizations for {len(targets)} resources")
    ctx.pmap(checks_and_permissions, targets)
    return out
