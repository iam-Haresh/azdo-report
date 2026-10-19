"""Shared normalization helpers: context, classic step expansion, resource matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from azdo_analyzer.model import ResourceRef, Step, Trigger, Variable
from azdo_analyzer.normalize.catalog import TaskCatalog, TaskGroupIndex
from azdo_analyzer.util import as_list

_MACRO = re.compile(r"\$\(([A-Za-z0-9_.\-]+)\)")
_DAYS = [(1, "Mon"), (2, "Tue"), (4, "Wed"), (8, "Thu"), (16, "Fri"), (32, "Sat"), (64, "Sun")]
_TRIGGER_TYPES = {
    1: "none",
    2: "continuousIntegration",
    4: "batchedContinuousIntegration",
    8: "schedule",
    16: "gatedCheckIn",
    32: "batchedGatedCheckIn",
    64: "pullRequest",
    128: "buildCompletion",
}


@dataclass
class NormContext:
    project: str
    project_id: str
    catalog: TaskCatalog
    task_groups: TaskGroupIndex
    web_base: str = ""
    repos_by_id: dict[str, dict] = field(default_factory=dict)
    queues_by_id: dict[int, dict] = field(default_factory=dict)
    deployment_groups_by_id: dict[int, dict] = field(default_factory=dict)
    variable_groups_by_id: dict[int, dict] = field(default_factory=dict)
    endpoints: list[dict] = field(default_factory=list)
    secure_files: list[dict] = field(default_factory=list)
    timelines: dict[int, list[dict]] = field(default_factory=dict)
    file_provider: Any = None
    deep: bool = True

    def __post_init__(self) -> None:
        self._endpoint_keys = {}
        for ep in self.endpoints:
            for key in (ep.get("id"), ep.get("name")):
                if key:
                    self._endpoint_keys[str(key).strip().lower()] = ep
        self._secure_keys = {}
        for sf in self.secure_files:
            for key in (sf.get("id"), sf.get("name")):
                if key:
                    self._secure_keys[str(key).strip().lower()] = sf

    def match_endpoint(self, value: str) -> dict | None:
        return self._endpoint_keys.get(value.strip().lower())

    def match_secure_file(self, value: str) -> dict | None:
        return self._secure_keys.get(value.strip().lower())

    def queue_name(self, queue_id: Any) -> str | None:
        try:
            q = self.queues_by_id.get(int(queue_id))
        except (TypeError, ValueError):
            return None
        return q.get("name") if q else None


def substitute(value: Any, mapping: dict[str, Any] | None) -> Any:
    """Replace $(name) macros using ``mapping`` (task-group inputs, process parameters)."""
    if not mapping or not isinstance(value, str) or "$(" not in value:
        return value

    def repl(match: re.Match) -> str:
        name = match.group(1)
        replacement = mapping.get(name)
        return match.group(0) if replacement is None else str(replacement)

    return _MACRO.sub(repl, value)


def expand_classic_steps(
    raw_steps: Iterable[dict],
    ctx: NormContext,
    *,
    params: dict[str, Any] | None = None,
    via: tuple[str, ...] = (),
    depth: int = 0,
    warnings: list[str] | None = None,
) -> list[Step]:
    """Classic build steps / release workflowTasks -> Steps, expanding task groups recursively."""
    out: list[Step] = []
    for raw in raw_steps or []:
        task = raw.get("task") or {}
        task_id = task.get("id") or raw.get("taskId")
        spec = task.get("versionSpec") or raw.get("version")
        dtype = (task.get("definitionType") or raw.get("definitionType") or "task").lower()
        inputs = {k: substitute(v, params) for k, v in (raw.get("inputs") or {}).items()}
        enabled = raw.get("enabled", True) is not False
        display = raw.get("displayName") or raw.get("name") or ""
        if dtype == "metatask":
            group = ctx.task_groups.get(task_id, spec)
            if group is None or depth >= 10:
                if warnings is not None:
                    warnings.append(f"task group {display or task_id} not resolved")
                out.append(
                    Step(name=display or f"task group {task_id}", kind="task", task=f"TaskGroup:{display or task_id}",
                         task_id=task_id, source="unknown", enabled=enabled, inputs=inputs, via_task_group=list(via))
                )
                continue
            nested = expand_classic_steps(
                group.get("tasks") or [], ctx, params={**(params or {}), **inputs},
                via=via + (group.get("name") or display,), depth=depth + 1, warnings=warnings,
            )
            for step in nested:
                step.enabled = step.enabled and enabled
            out.extend(nested)
            continue
        info = ctx.catalog.resolve_id(task_id, spec)
        out.append(
            Step(
                name=display or info.friendly or info.name,
                kind="task",
                task=info.ref,
                task_id=task_id,
                task_version=str(spec) if spec is not None else None,
                source=info.source,
                extension=info.extension,
                enabled=enabled,
                condition=raw.get("condition") or None,
                continue_on_error=bool(raw.get("continueOnError")),
                timeout=raw.get("timeoutInMinutes") or None,
                retries=raw.get("retryCountOnTaskFailure") or None,
                inputs=inputs,
                env=raw.get("environment") or {},
                via_task_group=list(via),
                windows_only=info.windows_only,
            )
        )
    return out


def step_resource_refs(steps: Iterable[Step], ctx: NormContext, where: str = "") -> list[ResourceRef]:
    """Service connections / secure files referenced by step inputs (by GUID or name)."""
    refs: list[ResourceRef] = []
    seen: set[tuple[str, str]] = set()
    for step in steps:
        for key, value in (step.inputs or {}).items():
            if not isinstance(value, str) or not value.strip() or len(value) > 400:
                continue
            for part in [v for v in re.split(r"[,;\n]", value) if v.strip()]:
                ep = ctx.match_endpoint(part)
                if ep:
                    ident = ("service_connection", ep["id"])
                    if ident not in seen:
                        seen.add(ident)
                        refs.append(ResourceRef("service_connection", ep.get("name"), ep.get("id"), ctx.project,
                                                detail=f"{step.task}:{key}{(' in ' + where) if where else ''}"))
                    continue
                sf = ctx.match_secure_file(part)
                if sf:
                    ident = ("secure_file", sf["id"])
                    if ident not in seen:
                        seen.add(ident)
                        refs.append(ResourceRef("secure_file", sf.get("name"), sf.get("id"), ctx.project, detail=f"{step.task}:{key}"))
    return refs


def variables_from_dict(raw: dict[str, Any] | None, scope: str, source: str) -> list[Variable]:
    out = []
    for name, spec in (raw or {}).items():
        spec = spec if isinstance(spec, dict) else {"value": spec}
        out.append(
            Variable(
                name=name,
                value=None if spec.get("isSecret") else (None if spec.get("value") is None else str(spec.get("value"))),
                is_secret=bool(spec.get("isSecret")),
                settable_at_queue=bool(spec.get("allowOverride")),
                scope=scope,
                source=source,
            )
        )
    return out


def variable_group_refs(ids: Iterable[Any], ctx: NormContext, detail: str = "") -> list[ResourceRef]:
    refs = []
    for vid in ids or []:
        if isinstance(vid, dict):
            vid = vid.get("id")
        try:
            group = ctx.variable_groups_by_id.get(int(vid))
        except (TypeError, ValueError):
            group = None
        refs.append(
            ResourceRef("variable_group", group.get("name") if group else f"#{vid}", str(vid), ctx.project, detail=detail, resolved=group is not None)
        )
    return refs


def _filters(values: Iterable[str]) -> tuple[list[str], list[str]]:
    inc, exc = [], []
    for raw in values or []:
        value = str(raw)
        target = exc if value.startswith("-") else inc
        value = value[1:] if value[:1] in "+-" else value
        target.append(value[len("refs/heads/"):] if value.startswith("refs/heads/") else value)
    return inc, exc


def describe_days(days: Any) -> str:
    if isinstance(days, int):
        if days == 127:
            return "daily"
        return ",".join(name for bit, name in _DAYS if days & bit) or "never"
    return str(days or "")


def parse_build_triggers(triggers: list[dict] | None, *, yaml_pipeline: bool = False) -> list[Trigger]:
    """Classic triggers, or UI overrides on YAML pipelines (settingsSourceType == 1)."""
    out: list[Trigger] = []
    for t in triggers or []:
        ttype = t.get("triggerType")
        ttype = _TRIGGER_TYPES.get(ttype, ttype) if isinstance(ttype, int) else ttype
        source_type = t.get("settingsSourceType")
        if yaml_pipeline and source_type != 1:
            continue  # comes from the YAML file, parsed separately
        defined_in = "ui" if yaml_pipeline else "classic"
        if ttype in ("continuousIntegration", "batchedContinuousIntegration"):
            bi, be = _filters(t.get("branchFilters") or [])
            pi, pe = _filters(t.get("pathFilters") or [])
            out.append(Trigger("ci", defined_in, bi, be, pi, pe, batch=bool(t.get("batchChanges")) or ttype.startswith("batched")))
        elif ttype == "schedule":
            for s in t.get("schedules") or []:
                bi, be = _filters(s.get("branchFilters") or [])
                when = f"{describe_days(s.get('daysToBuild'))} {int(s.get('startHours') or 0):02d}:{int(s.get('startMinutes') or 0):02d} {s.get('timeZoneId') or ''}".strip()
                if s.get("scheduleOnlyWithChanges"):
                    when += " (only if changed)"
                out.append(Trigger("schedule", defined_in, bi, be, schedule=when))
        elif ttype == "buildCompletion":
            definition = t.get("definition") or {}
            bi, be = _filters(t.get("branchFilters") or [])
            project = (definition.get("project") or {}).get("name")
            out.append(Trigger("build_completion", defined_in, bi, be, source=definition.get("name") or str(definition.get("id")),
                               detail={"definitionId": definition.get("id"), "project": project, "requiresSuccessfulBuild": t.get("requiresSuccessfulBuild")}))
        elif ttype == "pullRequest":
            bi, be = _filters(t.get("branchFilters") or [])
            pi, pe = _filters(t.get("pathFilters") or [])
            out.append(Trigger("pr", defined_in, bi, be, pi, pe))
        elif ttype in ("gatedCheckIn", "batchedGatedCheckIn"):
            pi, pe = _filters(t.get("pathFilters") or [])
            out.append(Trigger("gated", defined_in, paths_include=pi, paths_exclude=pe))
    return out


def web_url(ctx: NormContext, kind: str, ident: Any) -> str | None:
    if not ctx.web_base:
        return None
    from urllib.parse import quote

    base = f"{ctx.web_base}/{quote(ctx.project)}"
    if kind == "build":
        return f"{base}/_build?definitionId={ident}"
    if kind == "release":
        return f"{base}/_release?definitionId={ident}&view=mine&_a=releases"
    return None


def ids_of(values: Iterable[Any]) -> list[str]:
    return [str(v) for v in as_list(values) if v is not None]
