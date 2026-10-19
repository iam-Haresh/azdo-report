"""Complexity scoring driven by rules/scoring.yaml."""

from __future__ import annotations

from dataclasses import dataclass, field

from azdo_analyzer.analyze.facts import PipelineFacts
from azdo_analyzer.model import Pipeline
from azdo_analyzer.rules import Rules

LEVELS = ("Low", "Medium", "High")


@dataclass
class Score:
    points: int = 0
    level: str = "Low"
    reasons: list[str] = field(default_factory=list)
    blocker: bool = False

    def describe(self) -> str:
        return ", ".join(self.reasons)


def level_for(points: int, rules: Rules) -> str:
    t = rules.scoring.get("thresholds") or {}
    if points <= int(t.get("low_max", 3)):
        return "Low"
    if points <= int(t.get("medium_max", 8)):
        return "Medium"
    return "High"


def score_pipeline(pipeline: Pipeline, facts: PipelineFacts, rules: Rules) -> Score:
    cfg = rules.scoring
    pts = cfg.get("points") or {}
    caps = cfg.get("caps") or {}
    score = Score()

    def add(name: str, count: int | bool = 1, label: str | None = None) -> None:
        if not count:
            return
        n = int(count)
        if name in caps:
            n = min(n, int(caps[name]))
        value = int(pts.get(name, 0)) * n
        if value:
            score.points += value
            score.reasons.append(f"{label or name.replace('_', ' ')} +{value}")

    base = int((cfg.get("base") or {}).get(pipeline.kind, 0))
    if base:
        score.points += base
        score.reasons.append(f"{pipeline.kind_label} +{base}")
    add("multi_stage_deploy", facts.deploy_stages >= 2, f"{facts.deploy_stages} deploy stages")
    add("extra_deploy_stage", max(0, facts.deploy_stages - 3))
    add("approvals", bool(facts.approvals))
    add("gates", bool(facts.gates))
    add("manual_intervention", facts.manual_interventions > 0)
    add("deployment_group", bool(facts.deployment_groups))
    add("unmapped_task", len(facts.unmapped_tasks), "unmapped tasks")
    mapped_marketplace = [t for t in facts.marketplace_tasks if t not in facts.unmapped_tasks]
    add("marketplace_task", len(mapped_marketplace), "marketplace tasks")
    add("task_group", len(facts.task_groups), "task groups")
    add("windows_toolchain", bool(facts.windows_reasons), "Windows toolchain")
    add("keyvault", bool(facts.keyvault_groups), "Key Vault")
    add("secure_file", len(facts.secure_files), "secure files")
    add("cross_repo", bool(facts.cross_repo), "cross-repo")
    add("cross_pipeline_trigger", bool(facts.cross_pipeline_triggers), "pipeline triggers")
    add("vso_logging", bool(facts.vso_commands), "##vso commands")
    add("access_token", facts.access_token, "System.AccessToken")
    add("config_transform", bool(facts.config_transforms), "config transforms")
    add("dynamic_templates", facts.dynamic_templates, "dynamic templates")
    add("unresolved_templates", bool(facts.unresolved_templates), "unresolved templates")
    add("hidden_ui_config", bool(facts.hidden_ui), "hidden UI config")
    add("multi_repo_checkout", bool(facts.multi_repo), "multi-repo checkout")
    score.level = level_for(score.points, rules)
    return score


def score_repo(pipeline_scores: list[Score], *, submodules: bool, lfs: bool, large: bool, blocker: bool, rules: Rules) -> Score:
    pts = rules.scoring.get("repo_points") or {}
    best = max(pipeline_scores, key=lambda s: s.points, default=Score())
    score = Score(points=best.points, reasons=list(best.reasons))
    for name, flag in (("submodules", submodules), ("lfs", lfs), ("large_repo", large)):
        if flag and pts.get(name):
            score.points += int(pts[name])
            score.reasons.append(f"{name.replace('_', ' ')} +{pts[name]}")
    score.level = level_for(score.points, rules)
    score.blocker = blocker
    return score
