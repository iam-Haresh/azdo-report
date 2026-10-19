"""Findings: migration risks with severity, evidence and remediation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from azdo_analyzer.analyze.activity import RepoActivity
from azdo_analyzer.analyze.facts import PipelineFacts
from azdo_analyzer.analyze.scan import RepoScan
from azdo_analyzer.model import Pipeline, Variable
from azdo_analyzer.rules import SEVERITY_ORDER, Rules
from azdo_analyzer.util import compact, is_valid_gitlab_key


@dataclass
class Finding:
    id: str
    severity: str
    title: str
    project: str
    repo: str | None = None
    pipeline: str | None = None
    pipeline_key: str | None = None
    detail: str = ""
    remediation: str = ""

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 9)


def make(rules: Rules, fid: str, project: str, detail: str, *, repo: str | None = None,
         pipeline: Pipeline | None = None, severity: str | None = None) -> Finding:
    meta = rules.finding(fid)
    return Finding(
        id=fid,
        severity=severity or meta.get("severity", "info"),
        title=meta.get("title", fid),
        project=project,
        repo=repo,
        pipeline=pipeline.name if pipeline else None,
        pipeline_key=pipeline.key if pipeline else None,
        detail=detail,
        remediation=meta.get("remediation", ""),
    )


def variable_issues(variables: Iterable[Variable], secret_pattern: str) -> tuple[list[str], list[str], int]:
    """(invalid names, plaintext secret names, secret count)."""
    regex = re.compile(secret_pattern)
    invalid, plaintext, secrets = [], [], 0
    for v in variables:
        if not is_valid_gitlab_key(v.name):
            invalid.append(v.name)
        if v.is_secret:
            secrets += 1
        elif v.value and regex.search(v.name) and not v.value.strip().startswith("$("):
            plaintext.append(v.name)
    return sorted(set(invalid)), sorted(set(plaintext)), secrets


def pipeline_findings(p: Pipeline, f: PipelineFacts, rules: Rules, *, repo: str | None, secret_pattern: str) -> list[Finding]:
    out: list[Finding] = []

    def add(fid: str, detail: str, severity: str | None = None) -> None:
        out.append(make(rules, fid, p.project, detail, repo=repo, pipeline=p, severity=severity))

    if f.windows_reasons:
        add("WINDOWS_TOOLCHAIN", compact(f.windows_reasons))
    if f.unknown_tasks:
        add("UNKNOWN_TASK", compact(f.unknown_tasks))
    if f.unmapped_tasks:
        add("UNMAPPED_TASK", compact(f.unmapped_tasks))
    if f.marketplace_tasks:
        add("MARKETPLACE_TASK", compact(f.marketplace_tasks))
    if f.task_groups:
        add("TASK_GROUP", compact(f.task_groups))
    if f.deployment_groups:
        add("DEPLOYMENT_GROUP", compact(f.deployment_groups))
    if f.approvals:
        add("APPROVALS", f"{compact(f.approvals)}; approvers: {compact(f.approvers) or '?'}")
    if f.gates:
        add("GATE", compact(f.gates))
    if f.manual_interventions:
        add("MANUAL_INTERVENTION", f"{f.manual_interventions} step(s)")
    if f.agentless_jobs:
        add("AGENTLESS_JOB", f"{f.agentless_jobs} agentless job(s)")
    if f.keyvault_groups:
        add("KEYVAULT", compact(f.keyvault_groups))
    if f.secure_files:
        add("SECURE_FILE", compact(f.secure_files))
    if f.hidden_ui:
        add("HIDDEN_UI_CONFIG", "; ".join(f.hidden_ui))
    if f.vso_commands:
        add("VSO_LOGGING_CMD", "inline scripts: " + compact(f.vso_commands))
    if f.access_token:
        add("ACCESS_TOKEN", "inline scripts or variables reference System.AccessToken")
    elif f.oauth_token_access:
        add("OAUTH_TOKEN_ACCESS", "'Allow scripts to access the OAuth token' is enabled")
    if f.predefined_vars:
        add("PREDEFINED_VARS", compact(f.predefined_vars, limit=10))
    if f.azdo_urls:
        add("AZDO_URL", "inline: " + compact(f.azdo_urls, limit=4))
    non_junit = [fmt for fmt in f.test_formats if "junit" not in fmt.lower()]
    if non_junit:
        add("TEST_FORMAT", compact(non_junit))
    if f.config_transforms:
        add("CONFIG_TRANSFORM", compact(f.config_transforms))
    if f.cross_pipeline_triggers:
        add("CROSS_PIPELINE_TRIGGER", "triggered by " + compact(f.cross_pipeline_triggers))
    if f.schedules:
        add("SCHEDULE", compact(f.schedules))
    if f.cross_repo or f.multi_repo:
        add("CROSS_REPO", compact(f.cross_repo + [f"checkout {r}" for r in f.multi_repo]))
    if f.unresolved_templates:
        add("UNRESOLVED_TEMPLATE", compact(f.unresolved_templates, limit=4))
    elif f.dynamic_templates:
        add("DYNAMIC_TEMPLATES", "conditional insertion / dynamic expressions in templates")
    if f.internal_targets:
        add("INTERNAL_TARGET", compact(f.internal_targets))
    if f.pr_trigger_ignored:
        add("PR_TRIGGER_IGNORED", "YAML defines pr: but the repo is Azure Repos")
    invalid, plaintext, secrets = variable_issues(p.all_variables(), secret_pattern)
    if invalid:
        add("INVALID_VAR_NAME", compact(invalid, limit=10))
    if plaintext:
        add("PLAINTEXT_SECRET", compact(plaintext))
    if secrets:
        add("SECRETS_TO_REENTER", f"{secrets} secret pipeline variable(s)")
    return out


def repo_findings(project: str, repo: dict, *, activity: RepoActivity, scan: RepoScan | None, status: str,
                  has_pipelines: bool, windows_stack: bool, windows_from_pipelines: bool, policies: list[Any],
                  cfg_tier: str, limit_gb: float, rules: Rules) -> list[Finding]:
    out: list[Finding] = []
    name = repo["name"]

    def add(fid: str, detail: str, severity: str | None = None) -> None:
        out.append(make(rules, fid, project, detail, repo=name, severity=severity))

    size_gb = (repo.get("size") or 0) / 1024**3
    if size_gb > limit_gb:
        add("REPO_SIZE", f"{size_gb:.1f} GB (limit {limit_gb:g} GB)", severity="blocker")
    elif size_gb > limit_gb / 2:
        add("REPO_SIZE", f"{size_gb:.1f} GB (limit {limit_gb:g} GB)")
    if activity.open_prs:
        add("OPEN_PRS", f"{activity.open_prs} open (oldest {activity.oldest_pr_days} days)")
    if not has_pipelines and not repo.get("isDisabled"):
        add("NO_PIPELINE", "no build/YAML pipeline or release uses this repository")
    if status in ("Dormant", "Dead", "Never"):
        last = activity.last_commit_any.date().isoformat() if activity.last_commit_any else "never"
        add("DORMANT", f"status {status}; last commit {last}")
    if windows_stack and not windows_from_pipelines:
        add("WINDOWS_TOOLCHAIN", ".NET Framework project files (TargetFramework net4x)")
    if scan:
        if scan.lfs_patterns:
            add("LFS", compact(scan.lfs_patterns))
        if scan.submodules:
            add("SUBMODULES", compact(s.get("url", "?") for s in scan.submodules))
        if scan.feeds:
            add("FEED_DEPENDENCY", compact(f"{x['feed']} ({x['file']})" for x in scan.feeds))
        counts = scan.counts
        if counts.get("AZDO_URL"):
            add("AZDO_URL", f"{counts['AZDO_URL']} hit(s) in files, e.g. " + compact((h.file for h in scan.hits_for("AZDO_URL")), limit=3))
        if counts.get("VSO_LOGGING_CMD"):
            add("VSO_LOGGING_CMD", f"{counts['VSO_LOGGING_CMD']} hit(s): " + compact({h.match for h in scan.hits_for("VSO_LOGGING_CMD")}))
        if counts.get("ACCESS_TOKEN"):
            add("ACCESS_TOKEN", f"{counts['ACCESS_TOKEN']} hit(s) in " + compact((h.file for h in scan.hits_for("ACCESS_TOKEN")), limit=3))
        predefined = counts.get("PREDEFINED_VAR", 0) + counts.get("PREDEFINED_ENV", 0)
        if predefined:
            names = {h.match for h in scan.hits if h.pattern in ("PREDEFINED_VAR", "PREDEFINED_ENV")}
            add("PREDEFINED_VARS", f"{predefined} hit(s): " + compact(sorted(names), limit=8))
        if counts.get("STATUS_BADGE"):
            add("STATUS_BADGE", compact(h.file for h in scan.hits_for("STATUS_BADGE")))
    if policies:
        add("BRANCH_POLICIES", compact(sorted({f"{p.branch}: {p.policy}" for p in policies}), limit=6))
        if cfg_tier != "ultimate" and any("status" == p.policy.lower() or p.policy.lower().startswith("status") for p in policies):
            add("ULTIMATE_ONLY", "status-check branch policy -> external status checks")
    return out


def project_findings(project: str, *, tfvc: dict | None, hooks: list[dict], unused_connections: list[str],
                     group_invalid: dict[str, list[str]], group_plaintext: dict[str, list[str]],
                     deep: bool, rules: Rules) -> list[Finding]:
    out: list[Finding] = []

    def add(fid: str, detail: str) -> None:
        out.append(make(rules, fid, project, detail))

    if tfvc:
        add("TFVC", f"last changeset {tfvc.get('last') or '?'} by {tfvc.get('author') or '?'}")
    if hooks:
        add("SERVICE_HOOKS", compact(f"{h.get('consumerId')}:{h.get('eventType')}" for h in hooks))
    for name in unused_connections:
        add("UNUSED_CONNECTION", name)
    for group, names in group_invalid.items():
        add("INVALID_VAR_NAME", f"variable group {group}: {compact(names, limit=10)}")
    for group, names in group_plaintext.items():
        add("PLAINTEXT_SECRET", f"variable group {group}: {compact(names)}")
    if not deep:
        add("INVENTORY_ONLY", "step-level analysis, content scan and checks were not collected")
    return out
