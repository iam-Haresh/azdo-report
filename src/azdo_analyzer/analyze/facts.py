"""Per-pipeline facts derived once and reused by scoring, findings and reports."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from azdo_analyzer.analyze.scan import ScanHit
from azdo_analyzer.model import Pipeline
from azdo_analyzer.rawdata import OrgRaw, ProjectRaw
from azdo_analyzer.rules import Rules

_CONFIG_TRANSFORM_TASKS = re.compile(r"(?i)^(filetransform|replacetokens|tokenizer|magicchunks|xdttransform|variabletransform)")
_CONFIG_TRANSFORM_INPUTS = {"xmltransformation", "xmlvariablesubstitution", "jsonfiles", "enablexmltransform", "xmltransformationrules", "jsonvariablesubstitution"}
_WINDOWS_DEMAND = re.compile(r"(?i)(msbuild|visualstudio|vstest|windows_nt|dotnetframework|azurepowershell|sqlpackage)")
_WINDOWS_IMAGE = re.compile(r"(?i)(windows|vs20\d\d|win\d)")
_TEST_FORMAT_INPUTS = ("testResultsFormat", "testRunner")


@dataclass
class PipelineFacts:
    key: str
    tasks: list[str] = field(default_factory=list)
    unmapped_tasks: list[str] = field(default_factory=list)
    marketplace_tasks: list[str] = field(default_factory=list)
    unknown_tasks: list[str] = field(default_factory=list)
    task_groups: list[str] = field(default_factory=list)
    windows_reasons: list[str] = field(default_factory=list)
    keyvault_groups: list[str] = field(default_factory=list)
    secure_files: list[str] = field(default_factory=list)
    service_connections: list[str] = field(default_factory=list)
    variable_groups: list[str] = field(default_factory=list)
    cross_repo: list[str] = field(default_factory=list)
    cross_pipeline_triggers: list[str] = field(default_factory=list)
    schedules: list[str] = field(default_factory=list)
    vso_commands: list[str] = field(default_factory=list)
    access_token: bool = False
    predefined_vars: list[str] = field(default_factory=list)
    azdo_urls: list[str] = field(default_factory=list)
    config_transforms: list[str] = field(default_factory=list)
    dynamic_templates: bool = False
    unresolved_templates: list[str] = field(default_factory=list)
    hidden_ui: list[str] = field(default_factory=list)
    multi_repo: list[str] = field(default_factory=list)
    approvals: list[str] = field(default_factory=list)
    approvers: list[str] = field(default_factory=list)
    gates: list[str] = field(default_factory=list)
    manual_interventions: int = 0
    deployment_groups: list[str] = field(default_factory=list)
    deploy_stages: int = 0
    environments: list[str] = field(default_factory=list)
    test_formats: list[str] = field(default_factory=list)
    agentless_jobs: int = 0
    internal_targets: list[str] = field(default_factory=list)
    oauth_token_access: bool = False
    pr_trigger_ignored: bool = False
    inline_hits: list[ScanHit] = field(default_factory=list)


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def is_internal(host: str | None, patterns: list[str]) -> bool:
    return bool(host) and any(re.search(p, host, re.I) for p in patterns)


def environment_checks(raw: ProjectRaw, env_name: str | None) -> list[dict]:
    if not env_name:
        return []
    names = {str(e.get("name", "")).lower(): e for e in raw.environments}
    env = names.get(env_name.lower()) or names.get(env_name.split(".", 1)[0].lower())
    return raw.checks.get(f"environment_{env['id']}", []) if env else []


def describe_check(check: dict) -> tuple[str, str]:
    """(kind, label) where kind is approval | gate | lock."""
    ctype = ((check.get("type") or {}).get("name") or "").lower()
    settings = check.get("settings") or {}
    if ctype == "approval":
        approvers = [a.get("displayName") or a.get("id") for a in settings.get("approvers") or []]
        need = settings.get("minRequiredApprovers")
        return "approval", f"Approval by {', '.join(approvers) or '?'}" + (f" (min {need})" if need else "")
    if ctype in ("exclusivelock", "exclusive lock"):
        return "lock", "Exclusive lock"
    if ctype in ("extendscheck", "required template"):
        return "gate", "Required template"
    name = settings.get("displayName") or (settings.get("definitionRef") or {}).get("name") or ctype or "check"
    return "gate", str(name)


def compute_facts(pipeline: Pipeline, raw: ProjectRaw, org: OrgRaw, rules: Rules, *, inline_hits: list[ScanHit],
                  internal_patterns: list[str], windows_pools: set[str]) -> PipelineFacts:
    f = PipelineFacts(key=pipeline.key)
    steps = pipeline.all_steps()
    refs = []
    for step in steps:
        if step.kind != "task" or not step.task:
            continue
        if step.task.startswith("TaskGroup:"):
            continue
        refs.append(step.task)
        if step.source == "unknown":
            f.unknown_tasks.append(step.task)
        elif step.source == "extension":
            f.marketplace_tasks.append(step.task)
        hint = rules.task_hint(step.task)
        if hint is None and step.source != "unknown":
            f.unmapped_tasks.append(step.task)
        if step.windows_only or (hint or {}).get("windows"):
            f.windows_reasons.append(f"task {step.task}")
        if _CONFIG_TRANSFORM_TASKS.match(step.task):
            f.config_transforms.append(step.task)
        else:
            for key, value in (step.inputs or {}).items():
                if key.lower() in _CONFIG_TRANSFORM_INPUTS and str(value).strip().lower() not in ("", "false", "none"):
                    f.config_transforms.append(f"{step.task}:{key}")
        name = step.task.split("@")[0]
        if name == "PublishTestResults":
            fmt = next((str(step.inputs.get(k)) for k in _TEST_FORMAT_INPUTS if step.inputs.get(k)), "JUnit")
            f.test_formats.append(fmt)
        elif name == "VSTest":
            f.test_formats.append("VSTest (TRX)")
        elif name == "DotNetCoreCLI" and str(step.inputs.get("command", "")).lower() == "test" and str(step.inputs.get("publishTestResults", "true")).lower() != "false":
            f.test_formats.append("VSTest (TRX)")
        elif name in ("ManualIntervention", "ManualValidation"):
            f.manual_interventions += 1
    f.tasks = sorted(set(refs))
    f.unmapped_tasks = sorted(set(f.unmapped_tasks))
    f.marketplace_tasks = sorted(set(f.marketplace_tasks))
    f.unknown_tasks = sorted(set(f.unknown_tasks))
    f.task_groups = sorted({g for s in pipeline.all_steps(enabled_only=False) for g in s.via_task_group})
    f.config_transforms = sorted(set(f.config_transforms))
    f.test_formats = sorted(set(f.test_formats))

    for job in pipeline.all_jobs():
        if job.kind == "server":
            f.agentless_jobs += 1
        if job.deployment_group:
            f.deployment_groups.append(job.deployment_group)
        if job.vm_image and _WINDOWS_IMAGE.search(job.vm_image):
            f.windows_reasons.append(f"image {job.vm_image}")
        for demand in job.demands:
            if _WINDOWS_DEMAND.search(demand):
                f.windows_reasons.append(f"demand {demand}")
        if job.pool and job.pool.lower() in windows_pools:
            f.windows_reasons.append(f"pool {job.pool} (Windows agents)")
    f.windows_reasons = sorted(set(f.windows_reasons))
    f.deployment_groups = sorted(set(f.deployment_groups))

    groups_by_id = {str(g.get("id")): g for g in raw.variable_groups}
    for ref in pipeline.refs("variable_group"):
        f.variable_groups.append(ref.name)
        group = groups_by_id.get(str(ref.id))
        if group and str(group.get("type", "")).lower() == "azurekeyvault":
            f.keyvault_groups.append(ref.name)
            kv_endpoint = next((e for e in raw.endpoints if str(e.get("id")).lower() == str((group.get("providerData") or {}).get("serviceEndpointId")).lower()), None)
            if kv_endpoint:
                f.service_connections.append(kv_endpoint.get("name"))
    f.variable_groups = sorted(set(f.variable_groups))
    f.keyvault_groups = sorted(set(f.keyvault_groups))
    endpoints = {str(e.get("id")).lower(): e for e in raw.endpoints}
    for ref in pipeline.refs("service_connection"):
        f.service_connections.append(ref.name)
        ep = endpoints.get(str(ref.id or "").lower())
        host = _host(ep.get("url")) if ep else None
        if host and is_internal(host, internal_patterns):
            f.internal_targets.append(f"{ref.name} ({host})")
    f.service_connections = sorted(set(f.service_connections))
    f.secure_files = sorted({r.name for r in pipeline.refs("secure_file")})
    if f.deployment_groups:
        f.internal_targets += [f"deployment group {g}" for g in f.deployment_groups]
    f.internal_targets = sorted(set(f.internal_targets))

    f.cross_repo = sorted({f"{r.name} ({r.detail})" for r in pipeline.resources if r.kind in ("template_repo", "repository")})
    f.multi_repo = list(pipeline.checkout.get("multi_repo") or [])
    for t in pipeline.triggers:
        if t.kind in ("build_completion", "pipeline"):
            f.cross_pipeline_triggers.append(t.source or "?")
        elif t.kind in ("schedule", "release_schedule"):
            f.schedules.append(t.schedule or "")
        elif t.kind == "pr" and (t.detail or {}).get("ignored"):
            f.pr_trigger_ignored = True
    for stage in pipeline.stages:
        f.schedules += [f"stage {stage.name}: {s}" for s in stage.schedules]

    flags = pipeline.flags
    f.dynamic_templates = bool(flags.get("dynamic_templates"))
    f.unresolved_templates = list(flags.get("unresolved_templates") or [])
    if flags.get("yaml_unresolved"):
        f.unresolved_templates.append(f"root YAML {pipeline.yaml_path}")
    if pipeline.kind == "yaml":
        if flags.get("ui_variables"):
            f.hidden_ui.append(f"{flags['ui_variables']} UI-defined variable(s)")
        if flags.get("ui_trigger_override"):
            f.hidden_ui.append("trigger override in UI: " + ", ".join(flags["ui_trigger_override"]))
    f.oauth_token_access = bool(flags.get("oauth_token_access"))

    # approvals / gates: classic stage approvals + checks on environments and other resources
    for stage in pipeline.stages:
        if stage.is_deploy:
            f.deploy_stages += 1
        for a in stage.approvals:
            f.approvals.append(f"{stage.name} ({a.when})")
            f.approvers += a.approvers
        for g in stage.gates:
            f.gates.append(f"{stage.name}: {g.name}")
        env_name = stage.environment
        if env_name:
            f.environments.append(env_name)
        for check in environment_checks(raw, env_name):
            kind, label = describe_check(check)
            if kind == "approval":
                f.approvals.append(f"{stage.name} (environment {env_name})")
                f.approvers += [a.get("displayName") or "?" for a in (check.get("settings") or {}).get("approvers") or []]
            else:
                f.gates.append(f"{stage.name}: {label} (environment {env_name})")
    resource_checks = []
    for ref in pipeline.refs("service_connection"):
        resource_checks.append(("endpoint", ref.id))
    for ref in pipeline.refs("variable_group"):
        resource_checks.append(("variablegroup", ref.id))
    for rtype, rid in resource_checks:
        for check in raw.checks.get(f"{rtype}_{rid}", []):
            kind, label = describe_check(check)
            if kind == "approval":
                f.approvals.append(f"{rtype} {rid}")
            else:
                f.gates.append(f"{label} ({rtype})")
    f.approvers = sorted(set(f.approvers))
    f.environments = sorted(set(f.environments))

    f.inline_hits = inline_hits
    for hit in inline_hits:
        if hit.pattern == "VSO_LOGGING_CMD":
            f.vso_commands.append(hit.match)
        elif hit.pattern == "ACCESS_TOKEN":
            f.access_token = True
        elif hit.pattern in ("PREDEFINED_VAR", "PREDEFINED_ENV"):
            f.predefined_vars.append(hit.match)
        elif hit.pattern == "AZDO_URL":
            f.azdo_urls.append(hit.match)
    for v in pipeline.all_variables():
        if v.value and "System.AccessToken" in v.value:
            f.access_token = True
    f.vso_commands = sorted(set(f.vso_commands))
    f.predefined_vars = sorted(set(f.predefined_vars))
    f.azdo_urls = sorted(set(f.azdo_urls))
    return f


def windows_pool_names(org: OrgRaw) -> set[str]:
    """Pools whose agents all report Agent.OS = Windows_NT."""
    names = set()
    for pool in org.pools:
        agents = org.agents.get(int(pool.get("id") or 0)) or []
        oses = {str((a.get("systemCapabilities") or {}).get("Agent.OS", "")).lower() for a in agents}
        oses.discard("")
        if oses and oses <= {"windows_nt"}:
            names.add(str(pool.get("name", "")).lower())
    return names


def agent_summary(agent: dict[str, Any]) -> dict[str, Any]:
    caps = {**(agent.get("systemCapabilities") or {}), **(agent.get("userCapabilities") or {})}
    keys = []
    lowered = {k.lower(): (k, v) for k, v in caps.items()}
    probes = [
        ("java", ("java", "jdk")), ("maven", ("maven",)), ("gradle", ("gradle",)), ("ant", ("ant",)),
        ("node", ("node.js", "npm")), ("dotnet", ("dotnet",)), (".NET Framework", ("dotnetframework",)),
        ("msbuild", ("msbuild",)), ("visualstudio", ("visualstudio",)), ("vstest", ("vstest",)),
        ("docker", ("docker",)), ("kubectl", ("kubectl",)), ("helm", ("helm",)), ("oc", ("oc",)),
        ("python", ("python", "python3")), ("pwsh", ("pwsh",)), ("powershell", ("powershell",)),
        ("terraform", ("terraform",)), ("az", ("azure cli", "azcli", "az")), ("ansible", ("ansible",)),
        ("sqlpackage", ("sqlpackage",)), ("git", ("git",)),
    ]
    for label, prefixes in probes:
        if any(any(k == p or k.startswith(p + "_") or k.startswith(p + ".") for p in prefixes) for k in lowered):
            keys.append(label)
    request = agent.get("lastCompletedRequest") or {}
    return {
        "name": agent.get("name"),
        "os": caps.get("Agent.OS") or agent.get("osDescription"),
        "os_description": agent.get("osDescription") or caps.get("Agent.OSVersion"),
        "version": agent.get("version"),
        "status": agent.get("status"),
        "enabled": agent.get("enabled"),
        "tools": keys,
        "last_job": request.get("finishTime") or request.get("receiveTime"),
    }
