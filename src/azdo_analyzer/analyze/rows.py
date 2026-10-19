"""Tabular views (one row per variable, connection, policy, stage, ...) used by the reports."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlsplit

from azdo_analyzer.analyze.activity import StageStats
from azdo_analyzer.analyze.facts import agent_summary, describe_check, is_internal
from azdo_analyzer.analyze.usage import Usage
from azdo_analyzer.collect.connections import endpoint_summary
from azdo_analyzer.model import Pipeline, Variable
from azdo_analyzer.normalize.catalog import TaskCatalog
from azdo_analyzer.rawdata import OrgRaw, ProjectRaw
from azdo_analyzer.rules import Rules
from azdo_analyzer.util import branch_name, compact, gitlab_key, is_valid_gitlab_key, parse_dt

_CONNECTION_HINTS = {
    "kubernetes": "GitLab agent for Kubernetes (ci_access) or kubeconfig File variable",
    "openshift": "GitLab agent for Kubernetes or oc token as masked variable",
    "dockerregistry": "Registry credentials as masked variables (or GitLab container registry + CI_JOB_TOKEN)",
    "azurerm": "OIDC id_tokens + Entra workload identity federation",
    "sonarqube": "SONAR_HOST_URL + SONAR_TOKEN variables",
    "ssh": "SSH private key as File variable",
    "github": "GitHub token variable (or mirror the repo)",
    "githubenterprise": "GitHub token variable (or mirror the repo)",
    "git": "Deploy token / access token variable",
    "externaltfs": "Access token variable",
    "generic": "Credentials as masked variables",
    "artifactoryservice": "JFrog access token variable",
    "jfrogartifactoryservice": "JFrog access token variable",
    "externalnugetfeed": "NuGet feed credentials as variables",
    "externalnpmregistry": ".npmrc token variable",
    "externalmavenrepository": "settings.xml (File variable) credentials",
    "externalpythonuploadfeed": "TWINE_* variables",
    "servicenow": "ServiceNow integration / webhook",
    "jenkins": "Jenkins API token variable",
}


@dataclass
class PolicyRow:
    project: str
    repo: str
    branch: str
    policy: str
    enabled: bool
    blocking: bool
    settings: str
    gitlab: str


def _policy_text(policy: str, s: dict, pipeline_names: dict[int, str], identities: dict[str, Any], tier: str) -> tuple[str, str]:
    p = policy.lower()
    if "minimum number of reviewers" in p:
        n = s.get("minimumApproverCount")
        summary = f"min {n}; creator vote counts={s.get('creatorVoteCounts')}; reset on push={s.get('resetOnSourcePush')}"
        gitlab = f"Approval rule: {n} approval(s) (Premium)"
        if not s.get("creatorVoteCounts"):
            gitlab += "; prevent approval by author"
        if s.get("resetOnSourcePush") or s.get("resetRejectionsOnSourcePush"):
            gitlab += "; remove approvals when commits are added"
        return summary, gitlab
    if "required reviewers" in p:
        names = [(identities.get(i) or {}).get("displayName", i) for i in s.get("requiredReviewerIds") or []]
        paths = s.get("filenamePatterns") or ["/*"]
        return (f"reviewers: {compact(names)}; paths: {compact(paths)}; min {s.get('minimumApproverCount') or 1}",
                "CODEOWNERS entry for the paths + Code Owner approval on the protected branch (Premium)")
    if p == "build" or p.startswith("build"):
        name = pipeline_names.get(int(s.get("buildDefinitionId") or 0), f"#{s.get('buildDefinitionId')}")
        paths = s.get("filenamePatterns") or []
        summary = f"pipeline {name}; {'manual' if s.get('manualQueueOnly') else 'automatic'}; valid {s.get('validDuration') or 0} min"
        if paths:
            summary += f"; paths {compact(paths)}"
        return summary, "MR pipeline + 'Pipelines must succeed'" + (f" (rules:changes {compact(paths)})" if paths else "")
    if "comment" in p:
        return "all comments must be resolved", "All threads must be resolved"
    if "work item" in p:
        return "linked work item required", "Issue reference via MR template / push rule (Jira integration)"
    if "merge strategy" in p:
        allowed = [k.replace("allow", "") for k in ("allowNoFastForward", "allowSquash", "allowRebase", "allowRebaseMerge") if s.get(k)]
        return f"allowed: {compact(allowed)}", "Project merge method + squash setting"
    if p == "status" or p.startswith("status"):
        return (f"status {s.get('statusGenre') or ''}/{s.get('statusName') or ''}".strip("/"),
                "External status check (Ultimate)" if tier == "ultimate" else "External status check needs Ultimate - use a pipeline job on Premium")
    if "file size" in p:
        size = s.get("maximumGitBlobSizeInBytes") or 0
        return f"max {size / 1024 / 1024:.0f} MB per file", "Push rule: maximum file size (Premium)"
    if "path length" in p:
        return f"max path {s.get('maxPathLength')}", "No direct equivalent (CI check)"
    if "reserved names" in p or "file name" in p:
        return compact(s.get("filenamePatterns") or []) or "restricted names", "Push rule: prohibited file names (Premium)"
    if "author email" in p or "email" in p:
        return compact(s.get("authorEmailPatterns") or []), "Push rule: commit author email regex (Premium)"
    rest = {k: v for k, v in s.items() if k != "scope"}
    return json.dumps(rest, default=str)[:200], "Review manually"


def policy_rows(raw: ProjectRaw, pipelines: list[Pipeline], tier: str) -> list[PolicyRow]:
    repos = {r["id"]: r["name"] for r in raw.repos}
    names = {p.id: p.name for p in pipelines if p.kind != "classic_release"}
    out = []
    for cfg in raw.policies:
        if cfg.get("isDeleted"):
            continue
        policy = (cfg.get("type") or {}).get("displayName") or "?"
        settings = cfg.get("settings") or {}
        summary, gitlab = _policy_text(policy, settings, names, raw.identities, tier)
        for scope in settings.get("scope") or [{}]:
            rid = scope.get("repositoryId")
            repo = repos.get(rid, f"#{rid}") if rid else "(all repositories)"
            ref = scope.get("refName")
            branch = (branch_name(ref) or ref) if ref else "(all branches)"
            if scope.get("matchKind", "").lower() == "prefix" and ref:
                branch += "*"
            out.append(PolicyRow(raw.name, repo, branch, policy, bool(cfg.get("isEnabled", True)), bool(cfg.get("isBlocking", True)), summary, gitlab))
    return out


def _value(v: Variable, redact: bool, secret_re: re.Pattern) -> str:
    if v.is_secret:
        return "(secret)"
    if v.value is None:
        return ""
    if redact or secret_re.search(v.name):
        return "(redacted)"
    return v.value


def variable_rows(raw: ProjectRaw, pipelines: list[Pipeline], usage: Usage, repo_names: Callable[[set[str]], list[str]],
                  redact: bool, secret_pattern: str) -> list[dict[str, Any]]:
    secret_re = re.compile(secret_pattern)
    names = {p.key: p.name for p in pipelines}
    rows = []
    for p in pipelines:
        for v in p.all_variables():
            if v.scope.startswith("stage:"):
                level = f"project variable, environment scope '{v.scope[6:]}'" + (" (masked)" if v.is_secret else "")
            elif v.is_secret:
                level = "project variable (masked)"
            elif v.settable_at_queue:
                level = "spec:inputs / prefilled pipeline variable"
            else:
                level = ".gitlab-ci.yml variables:"
            rows.append({
                "project": raw.name, "scope_type": v.scope.split(":")[0], "owner": p.name + (f" / {v.scope[6:]}" if v.scope.startswith("stage:") else ""),
                "name": v.name, "secret": v.is_secret, "settable": v.settable_at_queue, "value": _value(v, redact, secret_re),
                "valid_key": is_valid_gitlab_key(v.name), "proposed_key": v.proposed_key, "proposed_level": level,
                "used_by": p.name, "pipeline_key": p.key,
            })
    for g in raw.variable_groups:
        users = usage.users("variable_group", str(g.get("id")))
        repos = repo_names(users)
        kv = str(g.get("type", "")).lower() == "azurekeyvault"
        shared = [(ref.get("projectReference") or {}).get("name") for ref in g.get("variableGroupProjectReferences") or []]
        shared = [s for s in shared if s and s != raw.name]
        if kv:
            level = "external secret (secrets:azure_key_vault / vault)"
        elif shared:
            level = f"parent GitLab group variable (also used by {compact(shared)})"
        elif len(repos) > 1:
            level = f"GitLab group variable (shared by {len(repos)} repos)"
        elif repos:
            level = "project variable"
        else:
            level = "unused - skip"
        for name, spec in (g.get("variables") or {}).items():
            spec = spec or {}
            raw_value = spec.get("value")
            v = Variable(name, None if spec.get("isSecret") or raw_value is None else str(raw_value), bool(spec.get("isSecret")),
                         scope=f"group:{g.get('name')}")
            rows.append({
                "project": raw.name, "scope_type": "group", "owner": g.get("name"), "name": name, "secret": v.is_secret or kv,
                "settable": False, "value": "(Key Vault)" if kv else _value(v, redact, secret_re), "valid_key": is_valid_gitlab_key(name),
                "proposed_key": name if is_valid_gitlab_key(name) else gitlab_key(name), "proposed_level": level,
                "used_by": compact(sorted(names.get(k, k) for k in users), limit=5),
                "group_id": g.get("id"),
            })
    return rows


def group_rows(raw: ProjectRaw, usage: Usage, pipeline_names: dict[str, str], repo_names: Callable[[set[str]], list[str]]) -> list[dict[str, Any]]:
    rows = []
    for g in raw.variable_groups:
        users = usage.users("variable_group", str(g.get("id")))
        variables = g.get("variables") or {}
        kv = str(g.get("type", "")).lower() == "azurekeyvault"
        repos = repo_names(users)
        shared = [(ref.get("projectReference") or {}).get("name") for ref in g.get("variableGroupProjectReferences") or []]
        rows.append({
            "project": raw.name, "name": g.get("name"), "id": g.get("id"), "type": g.get("type"),
            "variables": len(variables), "secrets": sum(1 for v in variables.values() if (v or {}).get("isSecret")),
            "key_vault": ((g.get("providerData") or {}).get("vault")) if kv else "",
            "shared_projects": compact([s for s in shared if s and s != raw.name]),
            "used_by": compact(sorted(pipeline_names.get(k, k) for k in users), limit=6),
            "repos": compact(repos, limit=6), "repo_count": len(repos),
            "proposed_level": "external secret store" if kv else (
                "parent GitLab group" if [s for s in shared if s and s != raw.name] else (
                    "GitLab group" if len(repos) > 1 else ("project" if repos else "unused"))),
        })
    return rows


def connection_rows(raw: ProjectRaw, usage: Usage, pipeline_names: dict[str, str], internal_patterns: list[str]) -> list[dict[str, Any]]:
    rows = []
    for ep in raw.endpoints:
        s = endpoint_summary(ep)
        eid = str(ep.get("id")).lower()
        users = usage.users("service_connection", eid)
        history = usage.endpoint_history.get(eid) or {}
        perm = usage.authorizations.get(f"endpoint_{ep.get('id')}") or {}
        host = urlsplit(s["url"]).hostname if s.get("url") else None
        rows.append({
            "project": raw.name, "name": s["name"], "id": s["id"], "type": s["type"], "scheme": s["scheme"], "url": s["url"],
            "internal": is_internal(host, internal_patterns), "shared": bool(s["isShared"]),
            "projects": compact([x for x in s["projects"] if x != raw.name]),
            "used_by": compact(sorted(pipeline_names.get(k, k) for k in users), limit=6), "used_count": len(users),
            "executions": history.get("runs", 0), "last_used": history.get("last"),
            "history_definitions": compact(sorted(history.get("definitions") or [])),
            "authorized": "all pipelines" if perm.get("all") else compact(perm.get("pipelines") or []),
            "gitlab": _CONNECTION_HINTS.get(str(s["type"] or "").lower(), "Masked CI/CD variable(s)"),
        })
    return rows


def secure_file_rows(raw: ProjectRaw, usage: Usage, pipeline_names: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for sf in raw.secure_files:
        users = usage.users("secure_file", str(sf.get("id")))
        perm = usage.authorizations.get(f"securefile_{sf.get('id')}") or {}
        rows.append({
            "project": raw.name, "name": sf.get("name"), "id": sf.get("id"),
            "modified": sf.get("modifiedOn"), "modified_by": (sf.get("modifiedBy") or {}).get("displayName"),
            "used_by": compact(sorted(pipeline_names.get(k, k) for k in users), limit=6),
            "authorized": "all pipelines" if perm.get("all") else compact(perm.get("pipelines") or []),
            "gitlab": "Project-level Secure Files (download-secure-files) or File-type variable",
        })
    return rows


def environment_rows(raw: ProjectRaw, usage: Usage, pipeline_names: dict[str, str]) -> list[dict[str, Any]]:
    rows = []
    for env in raw.environments:
        detail = raw.environment_details.get(int(env["id"])) or env
        resources = [f"{r.get('type')}:{r.get('name')}" for r in detail.get("resources") or []]
        checks = [describe_check(c)[1] for c in raw.checks.get(f"environment_{env['id']}", [])]
        records = raw.environment_deployments.get(int(env["id"])) or []
        last = max((parse_dt(r.get("finishTime") or r.get("startTime")) for r in records if r.get("finishTime") or r.get("startTime")), default=None)
        users = usage.users("environment", str(env.get("name")))
        rows.append({
            "project": raw.name, "kind": "environment", "name": env.get("name"), "targets": compact(resources),
            "tags": compact({t for r in detail.get("resources") or [] for t in r.get("tags") or []}),
            "checks": "; ".join(checks), "deployments": len(records), "last_deployment": last,
            "used_by": compact(sorted(pipeline_names.get(k, k) for k in users), limit=6),
            "gitlab": "GitLab environment" + (" + protected environment approvals (Premium)" if any(c.startswith("Approval") for c in checks) else ""),
        })
    for dg in raw.deployment_groups:
        machines = dg.get("machines") or []
        names = [(m.get("agent") or {}).get("name") for m in machines]
        oses = {str((m.get("agent") or {}).get("osDescription") or "").split(" ")[0] for m in machines} - {""}
        users = usage.users("deployment_group", str(dg.get("id")))
        rows.append({
            "project": raw.name, "kind": "deployment group", "name": dg.get("name"), "targets": compact(names),
            "tags": compact({t for m in machines for t in m.get("tags") or []}), "checks": "",
            "deployments": None, "last_deployment": None,
            "used_by": compact(sorted(pipeline_names.get(k, k) for k in users), limit=6),
            "gitlab": f"Self-managed runners on {len(machines)} target(s) ({compact(oses) or 'OS ?'}) tagged per environment, or SSH/WinRM from a runner in the network",
        })
    return rows


def stage_rows(raw: ProjectRaw, pipelines: list[Pipeline], dep_stats: dict[tuple[int, int], StageStats]) -> list[dict[str, Any]]:
    env_records: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for records in raw.environment_deployments.values():
        for r in records:
            env_records[((r.get("definition") or {}).get("id") or 0, str(r.get("stageName") or ""))].append(r)
    rows = []
    for p in pipelines:
        for stage in p.deploy_stages():
            pre = [a for a in stage.approvals if a.when == "pre"]
            post = [a for a in stage.approvals if a.when == "post"]
            if p.kind == "classic_release":
                stats = dep_stats.get((p.id, int(stage.definition_environment_id or 0))) or StageStats()
                deployments, last, rate = stats.deployments, stats.last_deployed, stats.success_rate
            else:
                records = env_records.get((p.id, stage.name), [])
                deployments = len(records)
                last = max((parse_dt(r.get("finishTime")) for r in records if r.get("finishTime")), default=None)
                ok = sum(1 for r in records if str(r.get("result")).lower() == "succeeded")
                rate = round(100.0 * ok / deployments, 1) if deployments else None
            deploy_tasks = [s.task for j in stage.jobs for s in j.steps if s.kind == "task" and s.enabled and s.task]
            rows.append({
                "project": raw.name, "pipeline": p.name, "pipeline_key": p.key, "kind": p.kind_label, "stage": stage.name, "rank": stage.rank,
                "trigger": stage.trigger or (compact(stage.depends_on) and f"after {compact(stage.depends_on)}") or "",
                "pre_approvers": compact(n for a in pre for n in a.approvers),
                "post_approvers": compact(n for a in post for n in a.approvers),
                "required": compact(a.required_count for a in stage.approvals if a.required_count),
                "creator_can_approve": compact(a.creator_can_approve for a in stage.approvals if a.creator_can_approve is not None),
                "gates": compact(g.name for g in stage.gates),
                "jobs": compact(f"{j.kind}" + (f":{j.deployment_group}" if j.deployment_group else "") + (f" [{','.join(j.tags)}]" if j.tags else "") for j in stage.jobs),
                "environment": stage.environment or "",
                "queue_policy": stage.queue_policy or "",
                "variables": len(stage.variables),
                "tasks": compact(deploy_tasks, limit=8),
                "deployments": deployments, "last_deployed": last, "success_rate": rate,
            })
    return rows


def task_rows(pipelines: list[Pipeline], pipeline_repo: Callable[[Pipeline], list[str]], catalog: TaskCatalog, rules: Rules) -> list[dict[str, Any]]:
    uses: Counter[str] = Counter()
    where: dict[str, set[str]] = defaultdict(set)
    repos: dict[str, set[str]] = defaultdict(set)
    meta: dict[str, Any] = {}
    for p in pipelines:
        for s in p.all_steps():
            if not s.task or s.kind not in ("task", "script", "checkout", "download", "publish"):
                continue
            uses[s.task] += 1
            where[s.task].add(f"{p.project}/{p.name}")
            repos[s.task].update(pipeline_repo(p))
            meta.setdefault(s.task, s)
    rows = []
    for task, count in uses.most_common():
        hint = rules.task_hint(task) or {}
        step = meta[task]
        info = catalog.resolve_ref(task) if step.kind == "task" and not task.startswith("TaskGroup:") else None
        rows.append({
            "task": task, "friendly": info.friendly if info else step.kind, "source": step.source, "extension": step.extension or "",
            "uses": count, "pipelines": len(where[task]), "repos": len(repos[task]),
            "mapped": bool(hint), "gitlab": hint.get("gitlab", ""), "image": hint.get("image", ""), "effort": hint.get("effort", ""),
            "windows": bool(hint.get("windows") or step.windows_only), "category": hint.get("category", ""),
            "notes": hint.get("notes", ""), "examples": compact(sorted(where[task]), limit=4),
        })
    return rows


def agent_rows(org: OrgRaw, usage_by_pool: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    rows = []
    for pool in org.pools:
        if pool.get("isHosted"):
            continue
        stats = usage_by_pool.get(pool.get("name"), {})
        agents = org.agents.get(int(pool.get("id") or 0)) or []
        if not agents:
            rows.append({"pool": pool.get("name"), "agent": "(no agents collected)", "os": "", "version": "", "status": "", "enabled": None,
                         "tools": "", "last_job": None, "peak": stats.get("peak_concurrency"), "minutes": stats.get("minutes_per_month"), "runs": stats.get("runs")})
        for agent in agents:
            a = agent_summary(agent)
            rows.append({"pool": pool.get("name"), "agent": a["name"], "os": a["os_description"] or a["os"], "version": a["version"],
                         "status": a["status"], "enabled": a["enabled"], "tools": ", ".join(a["tools"]), "last_job": parse_dt(a["last_job"]),
                         "peak": stats.get("peak_concurrency"), "minutes": stats.get("minutes_per_month"), "runs": stats.get("runs")})
    return rows
