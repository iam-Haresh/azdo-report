"""Classic (designer) build definitions -> normalized Pipeline."""

from __future__ import annotations

from typing import Any

from azdo_analyzer.model import Job, Pipeline, ResourceRef, Stage
from azdo_analyzer.normalize.common import (
    NormContext,
    expand_classic_steps,
    parse_build_triggers,
    step_resource_refs,
    variable_group_refs,
    variables_from_dict,
    web_url,
)

_PHASE_KIND = {1: "agent", 2: "server", 4: "agent"}
_EXEC = {0: None, 1: "multi_config", 2: "multi_agent"}
_AUTH_SCOPE = {1: "projectCollection", 2: "project", "projectCollection": "projectCollection", "project": "project"}


def base_pipeline(d: dict, ctx: NormContext, kind: str) -> Pipeline:
    repo = d.get("repository") or {}
    links = (d.get("_links") or {}).get("web") or {}
    return Pipeline(
        key=f"build:{ctx.project}:{d['id']}",
        kind=kind,
        id=int(d["id"]),
        name=d.get("name") or str(d["id"]),
        project=ctx.project,
        folder=d.get("path") or "\\",
        url=links.get("href") or web_url(ctx, "build", d["id"]),
        repo_id=repo.get("id"),
        repo_name=repo.get("name"),
        repo_project=(ctx.repos_by_id.get(repo.get("id") or "", {}).get("project") or {}).get("name") or ctx.project,
        repo_type=repo.get("type"),
        default_branch=repo.get("defaultBranch"),
        enabled=(d.get("queueStatus") or "enabled") == "enabled",
        draft=(d.get("quality") == "draft"),
        created=d.get("createdDate"),
        author=(d.get("authoredBy") or {}).get("displayName"),
        build_number_format=d.get("buildNumberFormat"),
        timeout_minutes=d.get("jobTimeoutInMinutes"),
        job_auth_scope=_AUTH_SCOPE.get(d.get("jobAuthorizationScope")),
        retention={"rules": len(d.get("retentionRules") or [])} if d.get("retentionRules") else None,
    )


def checkout_options(repo: dict) -> dict[str, Any]:
    props = repo.get("properties") or {}
    fetch_depth = props.get("fetchDepth")
    return {
        "submodules": bool(repo.get("checkoutSubmodules")) or str(props.get("checkoutNestedSubmodules")).lower() == "true",
        "lfs": str(props.get("gitLfsSupport")).lower() == "true",
        "fetch_depth": int(fetch_depth) if str(fetch_depth or "").isdigit() else None,
        "clean": str(repo.get("clean")).lower() == "true" if repo.get("clean") is not None else None,
        "clean_options": props.get("cleanOptions"),
        "skip_sync": str(props.get("skipSyncSource")).lower() == "true",
    }


def process_parameters(d: dict) -> tuple[list[dict], dict[str, Any]]:
    inputs = ((d.get("processParameters") or {}).get("inputs")) or []
    params = [{"name": i.get("name"), "label": i.get("label"), "default": i.get("defaultValue"), "type": i.get("type")} for i in inputs]
    mapping = {f"Parameters.{i.get('name')}": i.get("defaultValue") for i in inputs if i.get("name")}
    return params, mapping


def normalize_classic_build(d: dict, ctx: NormContext) -> Pipeline:
    pipeline = base_pipeline(d, ctx, "classic_build")
    pipeline.triggers = parse_build_triggers(d.get("triggers"))
    pipeline.variables = variables_from_dict(d.get("variables"), "pipeline", "definition")
    pipeline.variable_groups = variable_group_refs(d.get("variableGroups") or [], ctx, detail="pipeline")
    pipeline.checkout = checkout_options(d.get("repository") or {})
    pipeline.parameters, param_map = process_parameters(d)
    process = d.get("process") or {}
    default_queue = d.get("queue") or {}
    stage = Stage(name="Build")
    if process.get("type") not in (None, 1):
        pipeline.warnings.append(f"unexpected process type {process.get('type')}")
    if not process.get("phases") and d.get("type") == "xaml":
        pipeline.warnings.append("XAML build definition (not supported by modern agents)")
    for index, phase in enumerate(process.get("phases") or []):
        target = phase.get("target") or {}
        options = target.get("executionOptions") or {}
        strategy_type = _EXEC.get(options.get("type"))
        queue_id = (target.get("queue") or {}).get("id") or default_queue.get("id")
        steps = expand_classic_steps(phase.get("steps") or [], ctx, params=param_map, warnings=pipeline.warnings)
        job = Job(
            name=phase.get("name") or f"Phase {index + 1}",
            kind=_PHASE_KIND.get(target.get("type"), "agent"),
            pool=ctx.queue_name(queue_id) or default_queue.get("name"),
            vm_image=(target.get("agentSpecification") or {}).get("identifier"),
            demands=list(target.get("demands") or d.get("demands") or []),
            strategy={"type": strategy_type, "multipliers": options.get("multipliers"), "max_concurrency": options.get("maxConcurrency")}
            if strategy_type
            else None,
            condition=phase.get("condition") or None,
            depends_on=[dep.get("scope") for dep in phase.get("dependencies") or [] if dep.get("scope")],
            timeout=phase.get("jobTimeoutInMinutes") or None,
            steps=steps,
        )
        stage.jobs.append(job)
        if target.get("allowScriptsAuthAccessOption"):
            pipeline.flags["oauth_token_access"] = True
    pipeline.stages = [stage]
    pipeline.resources = step_resource_refs(pipeline.all_steps(enabled_only=False), ctx)
    for job in stage.jobs:
        if job.pool:
            pipeline.resources.append(ResourceRef("queue", job.pool, None, ctx.project, detail=job.name))
    return pipeline
