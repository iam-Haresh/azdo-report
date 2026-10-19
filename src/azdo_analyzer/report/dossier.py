"""Per-repo Markdown dossiers: the migration checklist, auto-filled."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from azdo_analyzer.analyze import AnalysisResult, PipelineResult, ProjectResult, RepoResult
from azdo_analyzer.analyze.archetype import DIMENSIONS
from azdo_analyzer.cache import safe_name
from azdo_analyzer.model import Pipeline
from azdo_analyzer.report.graph import repo_graph
from azdo_analyzer.util import compact

_TOOL_INPUTS = {
    "JavaToolInstaller": ("versionSpec", "jdkArchitectureOption"),
    "Maven": ("jdkVersionOption", "mavenVersionOption", "goals"),
    "Gradle": ("jdkVersionOption", "tasks"),
    "Ant": ("jdkVersionOption", "targets"),
    "NodeTool": ("versionSpec",),
    "UseNode": ("version",),
    "UsePythonVersion": ("versionSpec",),
    "UseDotNet": ("packageType", "version"),
    "VSBuild": ("vsVersion", "platform", "configuration"),
    "MSBuild": ("msbuildVersion", "msbuildArchitecture"),
    "VSTest": ("vsTestVersion",),
    "GoTool": ("version",),
    "HelmInstaller": ("helmVersionToInstall",),
    "KubectlInstaller": ("kubectlVersion",),
    "TerraformInstaller": ("terraformVersion",),
    "DotNetCoreCLI": ("command",),
    "Npm": ("command",),
}
MAX_VARIABLE_ROWS = 150


def _size(size: int) -> str:
    mb = size / 1024 / 1024
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb:.1f} MB"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _date(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value) if value else "—"


def environment(templates: Path) -> Environment:
    env = Environment(loader=FileSystemLoader(str(templates)), autoescape=False, trim_blocks=True, lstrip_blocks=True,
                      undefined=StrictUndefined, keep_trailing_newline=True)
    env.filters["cell"] = _cell
    env.filters["d"] = _date
    env.filters["yn"] = lambda v: "yes" if v else "no"
    return env


def toolchain(pipeline: Pipeline) -> str:
    hints = []
    for step in pipeline.all_steps():
        name = (step.task or "").split("@")[0]
        keys = _TOOL_INPUTS.get(name)
        if not keys:
            continue
        values = [f"{k}={step.inputs[k]}" for k in keys if step.inputs.get(k) not in (None, "")]
        hints.append(f"{step.task}({', '.join(values)})" if values else step.task)
    for job in pipeline.all_jobs():
        if job.container:
            hints.append(f"container {job.container}")
        if job.vm_image:
            hints.append(f"image {job.vm_image}")
    return compact(hints, limit=8)


def _task_table(pipeline: Pipeline, rules: Any) -> list[dict[str, Any]]:
    counts = Counter(s.task for s in pipeline.all_steps() if s.task)
    sources = {s.task: s.source for s in pipeline.all_steps() if s.task}
    rows = []
    for task, uses in counts.most_common():
        hint = rules.task_hint(task) or {}
        rows.append({"task": task, "uses": uses, "source": sources.get(task, ""), "gitlab": hint.get("gitlab", "**unmapped**"),
                     "effort": hint.get("effort", "?")})
    return rows


def build_view(r: PipelineResult, rules: Any) -> dict[str, Any]:
    pl, f, st = r.pipeline, r.facts, r.stats
    jobs = pl.all_jobs()
    secrets = sum(1 for v in pl.all_variables() if v.is_secret)
    timeline = ""
    if pl.flags.get("timeline_checked"):
        extra, missing = pl.flags.get("timeline_only_tasks") or [], pl.flags.get("static_only_tasks") or []
        timeline = "matches" if not extra and not missing else (
            (f"only at runtime: {compact(extra)}" if extra else "") + ("; " if extra and missing else "") +
            (f"not executed last run: {compact(missing)}" if missing else ""))
    strategies = [f"{j.name}: {j.strategy.get('type')}" for j in jobs if j.strategy]
    containers = [f"container {j.container}" for j in jobs if j.container] + [f"service {s}" for j in jobs for s in j.services]
    quality = [t for t in f.tasks if (rules.task_hint(t) or {}).get("category") in ("quality", "security")]
    publishes = []
    for s in pl.all_steps():
        name = (s.task or "").split("@")[0]
        if name in ("PublishBuildArtifacts", "PublishPipelineArtifact", "publish"):
            publishes.append(str(s.inputs.get("ArtifactName") or s.inputs.get("artifactName") or s.inputs.get("artifact") or s.inputs.get("publish") or s.name))
        elif name in ("Docker", "DockerCompose") and str(s.inputs.get("command", "")).lower() in ("push", "buildandpush", ""):
            publishes.append(f"image {s.inputs.get('repository') or s.inputs.get('imageName') or '?'}")
        elif name in ("NuGetCommand", "DotNetCoreCLI", "Npm", "UniversalPackages") and str(s.inputs.get("command", "")).lower() in ("push", "publish", "pack"):
            publishes.append(f"{name} {s.inputs.get('command')}")
    checkout = pl.checkout or {}
    checkout_bits = [k for k in ("submodules", "lfs") if checkout.get(k) not in (None, False, "false")]
    if checkout.get("fetch_depth"):
        checkout_bits.append(f"fetchDepth {checkout['fetch_depth']}")
    if checkout.get("multi_repo"):
        checkout_bits.append("also checks out " + compact(checkout["multi_repo"]))
    if checkout.get("none"):
        checkout_bits.append("checkout: none in some jobs")
    runs = "no runs in the history window"
    if st and st.runs:
        reasons = compact(f"{k} {v}" for k, v in st.reasons.items())
        branches = compact(f"{b} ({n})" for b, n in st.branches)
        runs = (f"{st.runs} runs ({st.runs_90d} in 90d), success {st.success_rate}%, duration p50 {st.p50_minutes} / p95 {st.p95_minutes} min, "
                f"queue p95 {st.queue_p95_minutes} min; reasons: {reasons}; branches: {branches}")
    return {
        "name": pl.name, "kind": pl.kind_label, "url": pl.url, "yaml_path": pl.yaml_path, "extends": pl.flags.get("extends"),
        "enabled": pl.enabled, "depth": pl.depth,
        "triggers": compact((t.describe() for t in pl.triggers), limit=6) or "none (manual only)",
        "pools": compact({j.pool or j.vm_image or "" for j in jobs}), "demands": compact({d for j in jobs for d in j.demands}),
        "windows": compact(f.windows_reasons), "toolchain": toolchain(pl), "task_count": len(f.tasks),
        "unmapped": compact(f.unmapped_tasks), "marketplace": compact(f.marketplace_tasks),
        "templates": compact(pl.templates, limit=6), "unresolved": compact(f.unresolved_templates, limit=3), "dynamic": f.dynamic_templates,
        "build_number": pl.build_number_format, "tests": compact(f.test_formats), "quality": compact(quality),
        "artifacts": compact(publishes), "cache": "Cache task" if any((s.task or "").startswith("Cache@") for s in pl.all_steps()) else "none",
        "matrix": compact(strategies + containers), "runs": runs,
        "variables": f"{len(pl.all_variables())} ({secrets} secret)", "groups": compact(f.variable_groups),
        "parameters": compact(p.get("name") for p in pl.parameters), "checkout": compact(checkout_bits) or "default",
        "hidden_ui": "; ".join(f.hidden_ui), "timeline": timeline, "warnings": compact(pl.warnings, limit=3),
        "tasks": _task_table(pl, rules),
    }


def release_view(r: PipelineResult, project: ProjectResult) -> dict[str, Any]:
    pl, f = r.pipeline, r.facts
    stage_vars = sum(len(s.variables) for s in pl.stages)
    secrets = sum(1 for s in pl.stages for v in s.variables if v.is_secret)
    retention = pl.retention or {}
    return {
        "name": pl.name, "url": pl.url,
        "artifacts": compact(
            f"{a.alias}: {a.type} {a.source_name or ''} (default {a.default_version or '?'}{', branch ' + str(a.default_branch) if a.default_branch else ''}{', primary' if a.is_primary else ''})"
            for a in pl.artifacts),
        "triggers": compact(t.describe() for t in pl.triggers), "release_name_format": pl.release_name_format,
        "stages": [s for s in project.stages if s["pipeline_key"] == pl.key],
        "deployment_groups": compact(f.deployment_groups), "approvals": compact(f.approvals), "approvers": compact(f.approvers),
        "gates": compact(f.gates), "manual": f.manual_interventions,
        "stage_variables": f"{stage_vars} stage-scoped ({secrets} secret)", "groups": compact(f.variable_groups),
        "config_transforms": compact(f.config_transforms), "parameters": compact(f"{p.get('stage')}: {p.get('name')}" for p in pl.parameters),
        "retention": compact(f"{k}={v}" for k, v in retention.items() if v is not None),
    }


def repo_context(result: AnalysisResult, project: ProjectResult, repo: RepoResult) -> dict[str, Any]:
    rules, cfg = result.rules, result.cfg
    builds = [project.pipelines[k] for k in repo.pipelines if k in project.pipelines]
    releases = [project.pipelines[k] for k in repo.releases if k in project.pipelines]
    linked = builds + releases
    keys = {r.pipeline.key for r in linked}
    facts = [r.facts for r in linked]
    group_names = {g for f in facts for g in f.variable_groups}
    variables = [v for v in project.variables if v.get("pipeline_key") in keys or (v["scope_type"] == "group" and v["owner"] in group_names)]
    connection_names = {c for f in facts for c in f.service_connections}
    connections = [c for c in project.connections if c["name"] in connection_names]
    scan = repo.scan
    codeowners = []
    for pol in repo.policies:
        if "required reviewers" in pol.policy.lower():
            codeowners.append(f"{pol.branch}: {pol.settings}")
    url_bits = []
    if scan:
        for pid, label in (("AZDO_URL", "AZDO URLs"), ("STATUS_BADGE", "badges"), ("VSO_LOGGING_CMD", "##vso commands"),
                           ("ACCESS_TOKEN", "System.AccessToken"), ("PREDEFINED_VAR", "$(Build.*) vars"), ("PREDEFINED_ENV", "BUILD_* env vars")):
            if scan.counts.get(pid):
                url_bits.append(f"{label}: {scan.counts[pid]}")
        if scan.feeds:
            url_bits.append(f"feed configs: {compact({x['file'] for x in scan.feeds})}")
    url_summary = compact(url_bits, limit=10) if scan else "not scanned (inventory mode or repo not cloned)"
    edges = project.usage.edges
    names = {r.pipeline.name for r in linked}
    downstream = sorted({e.dst for e in edges if e.relation == "triggers" and e.src in names})
    script_constructs = []
    for f in facts:
        script_constructs += [f"##vso[{c}]" for c in f.vso_commands]
        if f.access_token:
            script_constructs.append("System.AccessToken")
    if scan:
        script_constructs += [f"{h.file}:{h.line} {h.match}" for h in scan.hits if h.pattern in ("VSO_LOGGING_CMD", "ACCESS_TOKEN")][:8]
    ar, prof = rules.archetype_rules, repo.profile
    windows = sorted({w for f in facts for w in f.windows_reasons})
    if not windows:
        windows = [f"{ar.label('stacks', s)} files" for s in prof.stacks if ar.rules["stacks"][s].windows]
    macos = [ar.label("stacks", s) for s in prof.stacks if ar.rules["stacks"][s].macos]
    runner_os = "; ".join(([f"Windows ({compact(windows)})"] if windows else []) + ([f"macOS ({compact(macos)})"] if macos else []))
    archetype_detail = []
    for section, _, title, _ in DIMENSIONS:
        values = prof.values(section)
        evidence = "; ".join(f"{v}: {', '.join(prof.evidence.get(f'{section}:{v}', [])[:2])}" for v in values)
        archetype_detail.append({"title": title, "found": ", ".join(values) or ("unknown" if section == "stacks" else "none"),
                                 "evidence": evidence or "—"})
    tools = set()
    for r in linked:
        for t in r.facts.tasks:
            name = t.split("@")[0]
            if name in ("Maven", "Gradle", "Ant", "Npm", "DotNetCoreCLI", "VSBuild", "MSBuild", "Docker", "HelmDeploy", "KubernetesManifest",
                        "Kubernetes", "AzureCLI", "TerraformTaskV4", "TerraformTaskV3", "Ansible", "SonarQubePrepare", "oc-cmd", "UsePythonVersion"):
                tools.add(name)
    pools = {j.pool for r in linked for j in r.pipeline.all_jobs() if j.pool}
    pool_usage = compact(f"{pool} ({project.pools[pool]['peak_concurrency']} / {project.pools[pool]['minutes_per_month']})"
                         for pool in sorted(pools) if pool in project.pools)
    yaml_deploys = []
    for b in builds:
        stages = [s for s in project.stages if s["pipeline_key"] == b.pipeline.key]
        if stages:
            yaml_deploys.append({"name": b.pipeline.name, "stages": stages, "approvals": compact(b.facts.approvals), "gates": compact(b.facts.gates)})
    cross_artifacts = []
    for r in linked:
        for s in r.pipeline.all_steps():
            name = (s.task or "").split("@")[0]
            if name == "UniversalPackages":
                cross_artifacts.append(f"{r.pipeline.name}: universal package {s.inputs.get('vstsFeedPackage') or s.inputs.get('vstsFeedPackagePublish') or ''}".strip())
            if name in ("DownloadPipelineArtifact", "DownloadBuildArtifacts", "downloadBuild") and str(s.inputs.get("source") or s.inputs.get("buildType") or "").lower() in ("specific", "specificbuild"):
                cross_artifacts.append(f"{r.pipeline.name}: downloads from pipeline {s.inputs.get('pipeline') or s.inputs.get('definition') or '?'}")
            if name == "download" and str(s.inputs.get("download")) not in ("current", "none"):
                cross_artifacts.append(f"{r.pipeline.name}: download {s.inputs.get('download')}")
    truncated = max(0, len(variables) - MAX_VARIABLE_ROWS)
    secrets = sum(1 for v in variables if v["scope_type"] != "group" and v["secret"])
    pipeline_vars = [v for v in variables if v["scope_type"] != "group"]
    invalid = sum(1 for v in variables if not v["valid_key"])
    kv = [g["name"] for g in project.groups if g["name"] in group_names and g["key_vault"]]
    hooks = compact(f"{h.get('consumerId')}:{h.get('eventType')}" for h in project.hooks)
    return {
        "generated": result.generated.strftime("%Y-%m-%d %H:%M UTC"),
        "fetched_at": project.raw.meta.get("fetched_at") or "?", "mode": "deep" if project.deep else "inventory",
        "project": project, "repo": repo, "o": _Override(repo.override),
        "serious": [f for f in repo.findings if f.severity in ("blocker", "high")],
        "n_builds": sum(1 for r in project.pipelines.values() if r.pipeline.kind != "classic_release"),
        "n_releases": sum(1 for r in project.pipelines.values() if r.pipeline.kind == "classic_release"),
        "builds": [build_view(r, rules) for r in builds], "releases": [release_view(r, project) for r in releases],
        "yaml_deploys": yaml_deploys,
        "last_run": max((r.last_activity for r in builds if r.last_activity), default=None),
        "last_deploy": max((r.last_activity for r in releases if r.last_activity), default=None),
        "size_mb": _size(repo.repo.get("size") or 0),
        "lfs": compact(scan.lfs_patterns) if scan else "", "default_branch": (repo.repo.get("defaultBranch") or "").replace("refs/heads/", ""),
        "codeowners": compact(codeowners, limit=4), "submodules": compact(s.get("url", "") for s in scan.submodules) if scan else "",
        "cross_repo": compact({c for f in facts for c in f.cross_repo}), "url_summary": url_summary,
        "pr_templates": compact(scan.pr_templates) if scan else "", "window": cfg.collection.history_days,
        "var_summary": f"{len(pipeline_vars)} ({secrets} secret, {invalid} invalid as GitLab keys incl. groups)",
        "groups_summary": compact(f"{g['name']} ({g['variables']} vars, {g['secrets']} secret, {g['proposed_level']})" for g in project.groups if g["name"] in group_names),
        "keyvault": compact(kv), "secure_files": compact({s for f in facts for s in f.secure_files}),
        "variables": variables[:MAX_VARIABLE_ROWS], "variables_truncated": truncated, "connections": connections,
        "feeds": compact(f"{x['feed']} ({x['file']})" for x in scan.feeds) if scan else "",
        "registries": compact({x["url"] for x in scan.registries}, limit=5) if scan else "",
        "base_images": compact({x["image"] for x in scan.base_images}) if scan else "",
        "cross_artifacts": compact(cross_artifacts), "upstream": compact({t for f in facts for t in f.cross_pipeline_triggers}),
        "downstream": compact(downstream), "template_repos": compact({c for f in facts for c in f.cross_repo if "templates" in c}),
        "hooks": hooks, "script_constructs": compact(script_constructs, limit=10),
        "approvers": compact({a for f in facts for a in f.approvers}),
        "runner_os": runner_os or "Linux containers should work", "archetype_detail": archetype_detail,
        "runner_tools": compact(sorted(tools)), "internal": compact({t for f in facts for t in f.internal_targets}),
        "pool_usage": pool_usage, "findings": repo.findings, "mermaid": repo_graph(project, repo),
    }


class _Override(dict):
    """Lets templates use o.wave / o.owner without failing on missing keys."""

    def __getattr__(self, item: str) -> Any:
        return self.get(item)


def write_dossiers(result: AnalysisResult, out_dir: Path) -> dict[str, Path]:
    env = environment(result.cfg.templates_path)
    template = env.get_template("dossier.md.j2")
    written: dict[str, Path] = {}
    for project in result.projects:
        if not project.deep:
            continue
        folder = out_dir / "dossiers" / safe_name(project.name)
        folder.mkdir(parents=True, exist_ok=True)
        for repo in project.repos:
            target = folder / f"{safe_name(repo.name)}.md"
            target.write_text(template.render(**repo_context(result, project, repo)), encoding="utf-8")
            written[repo.key] = target
    return written


def dossier_relpath(repo: RepoResult) -> str:
    return f"dossiers/{safe_name(repo.project)}/{safe_name(repo.name)}.md"
