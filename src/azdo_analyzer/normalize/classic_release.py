"""Classic release definitions -> normalized Pipeline (one Stage per environment)."""

from __future__ import annotations

import json
from typing import Any

from azdo_analyzer.model import Approval, Artifact, Gate, Job, Pipeline, ResourceRef, Stage, Trigger
from azdo_analyzer.normalize.common import (
    NormContext,
    describe_days,
    expand_classic_steps,
    step_resource_refs,
    variable_group_refs,
    variables_from_dict,
    web_url,
)

_PHASE = {1: "agentBasedDeployment", 2: "runOnServer", 4: "machineGroupBasedDeployment", 8: "deploymentGates"}
_PHASE_KIND = {"agentBasedDeployment": "agent", "runOnServer": "server", "machineGroupBasedDeployment": "deployment_group"}
_COND = {1: "event", 2: "environmentState", 4: "artifact"}
_TRIGGER = {1: "artifactSource", 2: "schedule", 3: "sourceRepo", 4: "containerImage", 5: "package", 6: "pullRequest"}
_ENV_STATUS = [(4, "succeeded"), (128, "partially succeeded"), (16, "rejected"), (8, "canceled")]


def _enum(value: Any, table: dict[int, str]) -> Any:
    return table.get(value, value) if isinstance(value, int) else value


def _approvals(block: dict | None, when: str) -> list[Approval]:
    block = block or {}
    manual = [a for a in block.get("approvals") or [] if not a.get("isAutomated")]
    if not manual:
        return []
    options = block.get("approvalOptions") or {}
    names = []
    for item in manual:
        approver = item.get("approver") or {}
        label = approver.get("displayName") or approver.get("uniqueName") or "?"
        if approver.get("isContainer"):
            label += " [group]"
        names.append(label)
    required = options.get("requiredApproverCount")
    return [
        Approval(
            when=when,
            approvers=names,
            required_count=required if required else len(names),
            creator_can_approve=options.get("releaseCreatorCanBeApprover"),
            timeout_minutes=options.get("timeoutInMinutes"),
        )
    ]


def _gates(block: dict | None, when: str, ctx: NormContext) -> list[Gate]:
    block = block or {}
    options = block.get("gatesOptions") or {}
    if not options.get("isEnabled"):
        return []
    out = []
    for gate in block.get("gates") or []:
        for task in gate.get("tasks") or []:
            info = ctx.catalog.resolve_id(task.get("taskId"), task.get("version"))
            out.append(
                Gate(
                    when=when,
                    name=task.get("name") or info.friendly or info.name,
                    task=info.ref,
                    settings={
                        "timeout": options.get("timeout"),
                        "samplingInterval": options.get("samplingInterval"),
                        "stabilizationTime": options.get("stabilizationTime"),
                    },
                )
            )
    return out


def _stage_trigger(conditions: list[dict]) -> tuple[str, list[str]]:
    parts, depends = [], []
    for cond in conditions or []:
        ctype = _enum(cond.get("conditionType"), _COND)
        if ctype == "event" and cond.get("name") == "ReleaseStarted":
            parts.append("after release")
        elif ctype == "environmentState":
            depends.append(cond.get("name"))
            try:
                value = int(cond.get("value") or 4)
            except ValueError:
                value = 4
            states = [label for bit, label in _ENV_STATUS if value & bit] or ["succeeded"]
            parts.append(f"after {cond.get('name')} ({'/'.join(states)})")
        elif ctype == "artifact":
            try:
                filt = json.loads(cond.get("value") or "{}")
            except ValueError:
                filt = {}
            branch = filt.get("sourceBranch")
            parts.append(f"artifact filter {cond.get('name')}" + (f" branch {branch}" if branch else ""))
    return ("; ".join(parts) if parts else "manual"), depends


def _queue_policy(policy: dict | None) -> str | None:
    if not policy:
        return None
    concurrency = policy.get("concurrencyCount")
    depth = policy.get("queueDepthCount")
    if concurrency in (0, None):
        return "unlimited parallel"
    mode = "latest only" if depth == 1 else "all in sequence"
    return f"{concurrency} at a time, {mode}"


def _release_triggers(d: dict) -> list[Trigger]:
    out = []
    for t in d.get("triggers") or []:
        ttype = _enum(t.get("triggerType"), _TRIGGER)
        if ttype == "artifactSource":
            branches = [c.get("sourceBranch") for c in t.get("triggerConditions") or [] if c.get("sourceBranch")]
            tags = [tag for c in t.get("triggerConditions") or [] for tag in c.get("tags") or []]
            out.append(Trigger("artifact", "classic", branches_include=branches, source=t.get("artifactAlias"), detail={"tags": tags}))
        elif ttype == "schedule":
            s = t.get("schedule") or {}
            when = f"{describe_days(s.get('daysToRelease'))} {int(s.get('startHours') or 0):02d}:{int(s.get('startMinutes') or 0):02d} {s.get('timeZoneId') or ''}".strip()
            out.append(Trigger("release_schedule", "classic", schedule=when))
        elif ttype == "pullRequest":
            out.append(Trigger("pull_request", "classic", source=t.get("artifactAlias")))
        elif ttype in ("containerImage", "package", "sourceRepo"):
            out.append(Trigger({"containerImage": "container_image"}.get(ttype, ttype), "classic", source=t.get("artifactAlias")))
    return out


def normalize_classic_release(d: dict, ctx: NormContext) -> Pipeline:
    links = (d.get("_links") or {}).get("web") or {}
    pipeline = Pipeline(
        key=f"release:{ctx.project}:{d['id']}",
        kind="classic_release",
        id=int(d["id"]),
        name=d.get("name") or str(d["id"]),
        project=ctx.project,
        folder=d.get("path") or "\\",
        url=links.get("href") or web_url(ctx, "release", d["id"]),
        enabled=not d.get("isDisabled", False) and not d.get("isDeleted", False),
        created=d.get("createdOn"),
        modified=d.get("modifiedOn"),
        author=(d.get("createdBy") or {}).get("displayName"),
        release_name_format=d.get("releaseNameFormat"),
    )
    for a in d.get("artifacts") or []:
        ref = a.get("definitionReference") or {}
        definition = ref.get("definition") or {}
        artifact = Artifact(
            alias=a.get("alias") or "",
            type=a.get("type") or "",
            source_name=definition.get("name") or (ref.get("repository") or {}).get("name"),
            source_id=str(definition.get("id") or (ref.get("repository") or {}).get("id") or "") or None,
            project=(ref.get("project") or {}).get("name"),
            default_version=(ref.get("defaultVersionType") or {}).get("name") or (ref.get("defaultVersionType") or {}).get("id"),
            default_branch=(ref.get("defaultVersionBranch") or {}).get("id") or (ref.get("defaultVersionBranch") or {}).get("name"),
            is_primary=bool(a.get("isPrimary")),
        )
        pipeline.artifacts.append(artifact)
        if artifact.type == "Build":
            pipeline.resources.append(ResourceRef("pipeline", artifact.source_name or "?", artifact.source_id, artifact.project, detail=f"artifact {artifact.alias}"))
        elif artifact.type in ("Git", "TFVC", "GitHub"):
            pipeline.resources.append(ResourceRef("repository", artifact.source_name or "?", artifact.source_id, artifact.project, detail=f"artifact {artifact.alias}"))
    pipeline.triggers = _release_triggers(d)
    pipeline.variables = variables_from_dict(d.get("variables"), "pipeline", "release")
    pipeline.variable_groups = variable_group_refs(d.get("variableGroups") or [], ctx, detail="release")

    for env in sorted(d.get("environments") or [], key=lambda e: e.get("rank") or 0):
        name = env.get("name") or f"stage {env.get('id')}"
        trigger, depends = _stage_trigger(env.get("conditions") or [])
        params_list = ((env.get("processParameters") or {}).get("inputs")) or []
        param_map = {f"Parameters.{i.get('name')}": i.get("defaultValue") for i in params_list if i.get("name")}
        pipeline.parameters.extend(
            {"stage": name, "name": i.get("name"), "default": i.get("defaultValue"), "type": i.get("type")} for i in params_list
        )
        stage = Stage(
            name=name,
            rank=env.get("rank") or 0,
            depends_on=depends,
            trigger=trigger,
            approvals=_approvals(env.get("preDeployApprovals"), "pre") + _approvals(env.get("postDeployApprovals"), "post"),
            gates=_gates(env.get("preDeploymentGates"), "pre", ctx) + _gates(env.get("postDeploymentGates"), "post", ctx),
            variables=variables_from_dict(env.get("variables"), f"stage:{name}", "release stage"),
            variable_groups=[r.name for r in variable_group_refs(env.get("variableGroups") or [], ctx)],
            queue_policy=_queue_policy(env.get("executionPolicy")),
            schedules=[
                f"{describe_days(s.get('daysToRelease'))} {int(s.get('startHours') or 0):02d}:{int(s.get('startMinutes') or 0):02d}"
                for s in env.get("schedules") or []
            ],
            is_deploy=True,
            definition_environment_id=env.get("id"),
        )
        pipeline.variable_groups.extend(variable_group_refs(env.get("variableGroups") or [], ctx, detail=f"stage {name}"))
        for phase in sorted(env.get("deployPhases") or [], key=lambda ph: ph.get("rank") or 0):
            ptype = _enum(phase.get("phaseType"), _PHASE)
            if ptype == "deploymentGates":
                continue
            dinput = phase.get("deploymentInput") or {}
            kind = _PHASE_KIND.get(ptype, "agent")
            steps = expand_classic_steps(phase.get("workflowTasks") or [], ctx, params=param_map, warnings=pipeline.warnings)
            job = Job(name=phase.get("name") or ptype or "phase", kind=kind, steps=steps, condition=dinput.get("condition") or None,
                      timeout=dinput.get("timeoutInMinutes") or None, demands=list(dinput.get("demands") or []))
            if kind == "deployment_group":
                group = ctx.deployment_groups_by_id.get(int(dinput.get("queueId") or 0)) if str(dinput.get("queueId") or "").isdigit() else None
                job.deployment_group = group.get("name") if group else f"#{dinput.get('queueId')}"
                job.tags = list(dinput.get("tags") or [])
                pipeline.resources.append(ResourceRef("deployment_group", job.deployment_group, str(dinput.get("queueId")), ctx.project, detail=f"stage {name}", resolved=group is not None))
            elif kind == "agent":
                job.pool = ctx.queue_name(dinput.get("queueId"))
                job.vm_image = (dinput.get("agentSpecification") or {}).get("identifier")
                if job.pool:
                    pipeline.resources.append(ResourceRef("queue", job.pool, str(dinput.get("queueId")), ctx.project, detail=f"stage {name}"))
            parallel = (dinput.get("parallelExecution") or {}).get("parallelExecutionType")
            if parallel not in (None, 0, "none"):
                job.strategy = {"type": {1: "multiConfiguration", 2: "multiMachine"}.get(parallel, parallel)}
            if dinput.get("enableAccessToken"):
                pipeline.flags["oauth_token_access"] = True
            stage.jobs.append(job)
        pipeline.resources.extend(step_resource_refs([s for j in stage.jobs for s in j.steps], ctx, where=f"stage {name}"))
        gate_tasks = [t for block in (env.get("preDeploymentGates"), env.get("postDeploymentGates"))
                      for g in (block or {}).get("gates") or [] for t in g.get("tasks") or []]
        if gate_tasks:
            pipeline.resources.extend(step_resource_refs(expand_classic_steps(gate_tasks, ctx), ctx, where=f"gate {name}"))
        retention = env.get("retentionPolicy")
        if retention and pipeline.retention is None:
            pipeline.retention = {"days": retention.get("daysToKeep"), "releases": retention.get("releasesToKeep"), "retain_build": retention.get("retainBuild")}
        pipeline.stages.append(stage)
    return pipeline
