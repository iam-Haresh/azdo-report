"""Analysis orchestration: raw cache -> normalized pipelines -> facts, scores, findings, rows."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from azdo_analyzer.analyze.activity import (
    RepoActivity,
    RunStats,
    build_stats,
    classify,
    deployment_stats,
    pool_usage,
    recommendation,
    repo_activity,
)
from azdo_analyzer.analyze.archetype import RepoProfile, clone_clusters, fingerprint, profile_repo
from azdo_analyzer.analyze.facts import PipelineFacts, compute_facts, windows_pool_names
from azdo_analyzer.analyze.findings import Finding, make, pipeline_findings, project_findings, repo_findings, variable_issues
from azdo_analyzer.analyze.rows import (
    PolicyRow,
    agent_rows,
    connection_rows,
    environment_rows,
    group_rows,
    policy_rows,
    secure_file_rows,
    stage_rows,
    task_rows,
    variable_rows,
)
from azdo_analyzer.analyze.scan import RepoScan, Scanner
from azdo_analyzer.analyze.scoring import Score, score_pipeline, score_repo
from azdo_analyzer.analyze.usage import Usage, build_usage
from azdo_analyzer.cache import RawStore
from azdo_analyzer.collect.content import FileProvider, RepoContent
from azdo_analyzer.collect.repos import tfvc_capability
from azdo_analyzer.config import Config
from azdo_analyzer.model import Pipeline, Variable
from azdo_analyzer.normalize import normalize_project, save_model
from azdo_analyzer.normalize.catalog import TaskCatalog
from azdo_analyzer.rawdata import OrgRaw, ProjectRaw, load_org, load_project
from azdo_analyzer.rules import Rules
from azdo_analyzer.util import parse_dt, slugify, utcnow

log = logging.getLogger("azdo_analyzer.analyze")


@dataclass
class PipelineResult:
    pipeline: Pipeline
    facts: PipelineFacts
    score: Score
    stats: RunStats | None = None
    last_activity: datetime | None = None
    activity: str = "Never"
    fingerprint: str | None = None
    repo_keys: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)


@dataclass
class RepoResult:
    key: str
    project: str
    repo: dict
    gitlab_path: str
    activity: RepoActivity
    status: str
    recommendation: str
    scan: RepoScan | None
    profile: RepoProfile
    pipelines: list[str]
    releases: list[str]
    score: Score
    findings: list[Finding]
    policies: list[PolicyRow]
    bom: dict[str, list[str]]
    override: dict[str, Any]
    slug_collision: bool = False
    template_for: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return self.repo["name"]

    @property
    def archetype(self) -> str:
        return self.override.get("archetype") or self.profile.name

    @property
    def complexity(self) -> str:
        return self.override.get("complexity") or self.score.level


@dataclass
class ProjectResult:
    name: str
    raw: ProjectRaw
    repos: list[RepoResult]
    pipelines: dict[str, PipelineResult]
    usage: Usage
    findings: list[Finding]
    tfvc: dict | None
    hooks: list[dict]
    variables: list[dict]
    groups: list[dict]
    connections: list[dict]
    secure_files: list[dict]
    environments: list[dict]
    stages: list[dict]
    policies: list[PolicyRow]
    pools: dict[str, dict[str, float]]

    @property
    def deep(self) -> bool:
        return self.raw.deep

    def all_findings(self) -> list[Finding]:
        seen: set[int] = set()
        out: list[Finding] = []
        sources = [self.findings] + [r.findings for r in self.repos] + [r.findings for r in self.pipelines.values()]
        for findings in sources:
            for f in findings:
                if id(f) not in seen:
                    seen.add(id(f))
                    out.append(f)
        return sorted(out, key=lambda f: (f.rank, f.project, f.repo or "", f.pipeline or "", f.id))


@dataclass
class AnalysisResult:
    generated: datetime
    cfg: Config
    rules: Rules
    org: OrgRaw
    projects: list[ProjectResult]
    tasks: list[dict]
    archetypes: list[dict]
    clones: list[dict]
    agents: list[dict]
    coverage: list[dict]

    def all_findings(self) -> list[Finding]:
        return sorted((f for p in self.projects for f in p.all_findings()), key=lambda f: (f.rank, f.project, f.repo or "", f.pipeline or "", f.id))

    def all_pipelines(self) -> list[PipelineResult]:
        return [r for p in self.projects for r in p.pipelines.values()]

    def all_repos(self) -> list[RepoResult]:
        return [r for p in self.projects for r in p.repos]


def load_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k).lower(): (v or {}) for k, v in (data.get("repos") or {}).items()}


def _tfvc(raw: ProjectRaw) -> dict | None:
    if raw.tfvc_changesets:
        cs = raw.tfvc_changesets[0]
        created = parse_dt(cs.get("createdDate"))
        return {"last": created.date().isoformat() if created else None, "author": (cs.get("author") or {}).get("displayName"),
                "changeset": cs.get("changesetId")}
    if tfvc_capability(raw.details):  # TFVC exists but its changesets were not readable
        return {"last": None, "author": None, "changeset": None}
    return None


def analyze_project(org: OrgRaw, raw: ProjectRaw, *, cfg: Config, rules: Rules, store: RawStore, provider: FileProvider | None,
                    scanner: Scanner, overrides: dict[str, dict[str, Any]], now: datetime) -> ProjectResult:
    deep = raw.deep
    a = cfg.analysis
    pipelines = normalize_project(org, raw, web_base=cfg.azdo.collection_url, provider=provider, deep=deep)
    save_model(cfg.model_dir, raw.name, pipelines)
    usage = build_usage(raw, pipelines)
    stats_by_def = build_stats(raw.builds, now)
    dep_stats, last_deploy = deployment_stats(raw.deployments)
    win_pools = windows_pool_names(org)
    listed_builds = {int(d["id"]): d for d in raw.build_definitions}
    listed_releases = {int(d["id"]): d for d in raw.release_definitions}
    repos_by_id = {r["id"]: r for r in raw.repos}
    pipeline_names = {p.key: p.name for p in pipelines}

    results: dict[str, PipelineResult] = {}
    for p in pipelines:
        inline_counts, inline_hits = scanner.scan_pipeline(p) if deep else ({}, [])
        facts = compute_facts(p, raw, org, rules, inline_hits=inline_hits, internal_patterns=a.internal_host_patterns, windows_pools=win_pools)
        score = score_pipeline(p, facts, rules)
        result = PipelineResult(pipeline=p, facts=facts, score=score, fingerprint=fingerprint(p))
        if p.kind == "classic_release":
            listed = listed_releases.get(p.id) or {}
            last_release = parse_dt(((listed.get("lastRelease") or {}).get("createdOn")))
            result.last_activity = max([d for d in (last_deploy.get(p.id), last_release) if d], default=None)
        else:
            result.stats = stats_by_def.get(p.id)
            listed = listed_builds.get(p.id) or {}
            latest = parse_dt((listed.get("latestBuild") or {}).get("finishTime")) or parse_dt((listed.get("latestBuild") or {}).get("queueTime"))
            result.last_activity = max([d for d in (latest, result.stats.last_run if result.stats else None) if d], default=None)
        result.activity = classify(result.last_activity, now, a.active_days, a.dormant_days)
        result.repo_keys = [f"{raw.name}/{repos_by_id[r]['name']}" for r in usage.pipeline_repos.get(p.key, []) if r in repos_by_id]
        repo_label = result.repo_keys[0].split("/", 1)[1] if result.repo_keys else (p.repo_name if p.kind != "classic_release" else None)
        result.findings = pipeline_findings(p, facts, rules, repo=repo_label, secret_pattern=a.secret_name_pattern)
        if p.key in usage.orphans:
            result.findings.append(make(rules, "ORPHAN", raw.name, f"repository {p.repo_name or p.repo_id}", pipeline=p))
        if p.key in usage.external:
            result.findings.append(make(rules, "EXTERNAL_REPO", raw.name, f"{p.repo_type}: {p.repo_name}", pipeline=p))
        results[p.key] = result

    endpoint_types = {str(e.get("id")): str(e.get("type") or "").lower() for e in raw.endpoints}
    policies = policy_rows(raw, pipelines, a.gitlab_tier)
    slugs = Counter(slugify(r["name"]) for r in raw.repos)
    repo_results: list[RepoResult] = []
    for repo in sorted(raw.repos, key=lambda r: r["name"].lower()):
        rid = repo["id"]
        content = RepoContent(cfg, store, provider, raw.name, repo) if provider is not None else None
        scan = scanner.scan_repo(content) if deep and content is not None and content.available else None
        files = scan.files if scan else []
        read = (lambda rel, c=content: c.read(rel)) if content is not None else (lambda rel: None)
        linked_keys = usage.repo_pipelines.get(rid, []) + usage.repo_releases.get(rid, [])
        linked = [results[k].pipeline for k in linked_keys if k in results]
        profile = profile_repo(files, read, linked, endpoint_types, rules)
        act = repo_activity(raw.branch_stats.get(rid, []), raw.tags.get(rid, []), raw.open_prs.get(rid, []), repo.get("defaultBranch"),
                            now, a.dormant_days)
        users_keys = linked_keys + list(usage.template_users.get(rid, set()))
        last_pipeline = max((results[k].last_activity for k in users_keys if k in results and results[k].last_activity), default=None)
        last = max([d for d in (act.last_commit_any, last_pipeline) if d], default=None)
        status = "Disabled" if repo.get("isDisabled") else classify(last, now, a.active_days, a.dormant_days)
        repo_policies = [pol for pol in policies if pol.repo in (repo["name"], "(all repositories)")]
        windows_from_pipelines = any(results[k].facts.windows_reasons for k in linked_keys if k in results)
        template_for = sorted(results[k].pipeline.name for k in usage.template_users.get(rid, set()) if k in results)
        if template_for and profile.stack == "unknown" and not linked_keys:
            profile.key, profile.name = "yaml-templates | none | none | none", "AZDO YAML template repository"
        findings = [] if status == "Disabled" else repo_findings(
            raw.name, repo, activity=act, scan=scan, status=status, has_pipelines=bool(linked_keys or template_for),
            windows_stack=profile.windows, windows_from_pipelines=windows_from_pipelines, policies=repo_policies,
            cfg_tier=a.gitlab_tier, limit_gb=a.gitlab_repo_limit_gb, rules=rules,
        )
        for k in linked_keys:
            if k in results:
                findings.extend(f for f in results[k].findings if f not in findings)
        size_gb = (repo.get("size") or 0) / 1024**3
        blocker = any(f.severity == "blocker" for f in findings)
        score = score_repo([results[k].score for k in linked_keys if k in results],
                           submodules=bool(scan and scan.submodules), lfs=bool(scan and scan.lfs_patterns),
                           large=size_gb > a.gitlab_repo_limit_gb / 2, blocker=blocker, rules=rules)
        bom: dict[str, set[str]] = defaultdict(set)
        for p in linked:
            for ref in p.refs("variable_group") + p.resources:
                if ref.kind in ("queue", "container"):
                    bom["agent queue" if ref.kind == "queue" else "container image"].add(ref.name)
                else:
                    bom[ref.kind.replace("_", " ")].add(ref.name)
            for g in results[p.key].facts.task_groups:
                bom["task group"].add(g)
        if scan:
            for feed in scan.feeds:
                bom["azure artifacts feed"].add(feed["feed"])
        key = f"{raw.name}/{repo['name']}"
        repo_results.append(RepoResult(
            key=key, project=raw.name, repo=repo, gitlab_path=f"{slugify(raw.name)}/{slugify(repo['name'])}",
            activity=act, status=status, recommendation="Skip (disabled)" if status == "Disabled" else recommendation(status),
            scan=scan, profile=profile, pipelines=usage.repo_pipelines.get(rid, []), releases=usage.repo_releases.get(rid, []),
            score=score, findings=sorted(findings, key=lambda f: (f.rank, f.id)), policies=repo_policies,
            bom={k: sorted(v) for k, v in sorted(bom.items())}, override=overrides.get(key.lower(), {}),
            slug_collision=slugs[slugify(repo["name"])] > 1, template_for=template_for,
        ))

    def repo_names(keys: set[str]) -> list[str]:
        names: set[str] = set()
        for k in keys:
            if k in results:
                names.update(results[k].repo_keys)
        return sorted(names)

    variables = variable_rows(raw, pipelines, usage, repo_names, a.redact_values, a.secret_name_pattern)
    groups = group_rows(raw, usage, pipeline_names, repo_names)
    connections = connection_rows(raw, usage, pipeline_names, a.internal_host_patterns)
    unused = [c["name"] for c in connections if not c["used_count"] and not c["executions"]] if deep else []
    group_invalid: dict[str, list[str]] = {}
    group_plaintext: dict[str, list[str]] = {}
    for g in raw.variable_groups:
        vars_ = [Variable(n, None if (s or {}).get("isSecret") or (s or {}).get("value") is None else str((s or {}).get("value")),
                          bool((s or {}).get("isSecret"))) for n, s in (g.get("variables") or {}).items()]
        invalid, plaintext, _ = variable_issues(vars_, a.secret_name_pattern)
        if invalid:
            group_invalid[g.get("name")] = invalid
        if plaintext:
            group_plaintext[g.get("name")] = plaintext
    project_id = raw.id
    hooks = [h for h in org.hooks if (h.get("publisherInputs") or {}).get("projectId") == project_id]
    tfvc = _tfvc(raw)
    p_findings = project_findings(raw.name, tfvc=tfvc, hooks=hooks, unused_connections=unused, group_invalid=group_invalid,
                                  group_plaintext=group_plaintext, deep=deep, rules=rules)
    for repo_result in repo_results:
        groups_used = {g for k in repo_result.pipelines + repo_result.releases if k in results for g in results[k].facts.variable_groups}
        for f in p_findings:
            if any(f.detail.startswith(f"variable group {g}") for g in groups_used) and f not in repo_result.findings:
                repo_result.findings.append(f)
        repo_result.findings.sort(key=lambda f: (f.rank, f.id))
    return ProjectResult(
        name=raw.name, raw=raw, repos=repo_results, pipelines=results, usage=usage, findings=p_findings, tfvc=tfvc, hooks=hooks,
        variables=variables, groups=groups, connections=connections,
        secure_files=secure_file_rows(raw, usage, pipeline_names),
        environments=environment_rows(raw, usage, pipeline_names),
        stages=stage_rows(raw, pipelines, dep_stats), policies=policies,
        pools=pool_usage(raw.builds, cfg.collection.history_days),
    )


def run_analysis(cfg: Config, rules: Rules, project_names: list[str], *, provider: FileProvider | None,
                 now: datetime | None = None) -> AnalysisResult:
    now = now or utcnow()
    store = RawStore(cfg.raw_dir)
    org = load_org(store)
    scanner = Scanner(rules, cfg.azdo.collection_url)
    overrides = load_overrides(cfg.overrides_path)
    projects = []
    for name in project_names:
        meta = org.project(name) or {}
        raw = load_project(store, name, meta.get("id"))
        if not raw.repos and not raw.build_definitions and not raw.release_definitions:
            log.warning("no cached data for project %s - skipped", name)
            continue
        projects.append(analyze_project(org, raw, cfg=cfg, rules=rules, store=store, provider=provider, scanner=scanner,
                                        overrides=overrides, now=now))

    all_pipelines = [r.pipeline for p in projects for r in p.pipelines.values()]
    by_key = {r.pipeline.key: r for p in projects for r in p.pipelines.values()}
    tasks = task_rows(all_pipelines, lambda p: by_key[p.key].repo_keys, TaskCatalog(org.tasks), rules)

    archetypes: dict[str, dict[str, Any]] = {}
    for p in projects:
        for repo in p.repos:
            if repo.status == "Disabled":
                continue
            entry = archetypes.setdefault(repo.profile.key, {"key": repo.profile.key, "name": repo.profile.name, "template": repo.profile.template,
                                                             "repos": [], "pipelines": 0, "points": [], "levels": Counter()})
            entry["repos"].append(repo.key)
            entry["pipelines"] += len(repo.pipelines) + len(repo.releases)
            entry["points"].append(repo.score.points)
            entry["levels"][repo.score.level] += 1
    archetype_rows = sorted(
        ({**e, "repo_count": len(e["repos"]), "avg_points": round(sum(e["points"]) / len(e["points"]), 1) if e["points"] else 0,
          "levels": ", ".join(f"{k} {v}" for k, v in sorted(e["levels"].items()))} for e in archetypes.values()),
        key=lambda e: (-e["repo_count"], e["key"]),
    )
    pool_stats: dict[str, dict[str, float]] = {}
    for p in projects:
        for pool, stats in p.pools.items():
            agg = pool_stats.setdefault(pool, {"runs": 0, "peak_concurrency": 0, "minutes_per_month": 0.0})
            agg["runs"] += stats["runs"]
            agg["peak_concurrency"] = max(agg["peak_concurrency"], stats["peak_concurrency"])
            agg["minutes_per_month"] += stats["minutes_per_month"]
    coverage = list(org.coverage) + [row for p in projects for row in p.raw.coverage]
    return AnalysisResult(
        generated=now, cfg=cfg, rules=rules, org=org, projects=projects, tasks=tasks, archetypes=archetype_rows,
        clones=clone_clusters(all_pipelines), agents=agent_rows(org, pool_stats), coverage=coverage,
    )
