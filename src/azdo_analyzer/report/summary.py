"""Per-project Markdown summary and Mermaid graph."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from azdo_analyzer.analyze import AnalysisResult, ProjectResult
from azdo_analyzer.cache import safe_name
from azdo_analyzer.report.dossier import environment
from azdo_analyzer.report.graph import project_graph
from azdo_analyzer.util import compact

_LEVEL_ORDER = {"Low": 0, "Medium": 1, "High": 2}
_STATUS_ORDER = {"Active": 0, "Dormant": 1, "Never": 2, "Dead": 2, "Disabled": 3}


class _Bag(Counter):
    def __getattr__(self, item: str) -> int:
        return self[item]


def project_context(result: AnalysisResult, project: ProjectResult) -> dict:
    statuses = _Bag(r.status for r in project.repos)
    kinds = _Bag(r.pipeline.kind for r in project.pipelines.values())
    levels = _Bag(r.complexity for r in project.repos if r.status != "Disabled")
    findings = project.all_findings()
    ordered = sorted(
        (r for r in project.repos if r.status != "Disabled"),
        key=lambda r: (r.score.blocker, _STATUS_ORDER.get(r.status, 9) > 0, _LEVEL_ORDER.get(r.complexity, 9), r.score.points, r.name.lower()),
    )
    for r in ordered:
        r.serious = compact(sorted({f.id for f in r.findings if f.severity in ("blocker", "high")}), limit=6)  # type: ignore[attr-defined]
    archetypes = Counter((r.profile.key, r.archetype) for r in project.repos if r.status != "Disabled")
    shared = []
    for g in project.groups:
        if g["repo_count"] > 1 or g["shared_projects"]:
            shared.append({"kind": "variable group", "name": g["name"], "users": g["used_by"], "level": g["proposed_level"]})
    for c in project.connections:
        if c["used_count"] > 1:
            shared.append({"kind": "service connection", "name": c["name"], "users": c["used_by"], "level": c["gitlab"]})
    grouped: dict[tuple[str, str, str], list] = defaultdict(list)
    for f in findings:
        grouped[(f.severity, f.id, f.title)].append(f)
    top = sorted(grouped.items(), key=lambda kv: (_rank(kv[0][0]), -len(kv[1])))[:15]
    return {
        "generated": result.generated.strftime("%Y-%m-%d %H:%M UTC"), "fetched_at": project.raw.meta.get("fetched_at") or "?",
        "mode": "deep" if project.deep else "inventory", "tier": result.cfg.analysis.gitlab_tier.title(), "project": project,
        "statuses": statuses, "kinds": kinds, "levels": levels, "blockers": sum(1 for f in findings if f.severity == "blocker"),
        "ordered": ordered, "archetypes": [{"key": k[0], "name": k[1], "count": n} for k, n in archetypes.most_common()],
        "shared": shared, "retire": [r for r in project.repos if r.status in ("Dead", "Never")],
        "top_findings": [{"severity": k[0], "id": k[1], "title": k[2], "count": len(v),
                          "example": " / ".join(x for x in (v[0].repo, v[0].pipeline, v[0].detail) if x)} for k, v in top],
        "mermaid": project_graph(project),
    }


def _rank(severity: str) -> int:
    return {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(severity, 9)


def write_summaries(result: AnalysisResult, out_dir: Path) -> list[Path]:
    env = environment(result.cfg.templates_path)
    template = env.get_template("project_summary.md.j2")
    written = []
    for project in result.projects:
        folder = out_dir / safe_name(project.name)
        folder.mkdir(parents=True, exist_ok=True)
        context = project_context(result, project)
        summary = folder / "summary.md"
        summary.write_text(template.render(**context), encoding="utf-8")
        (folder / "graph.mmd").write_text(context["mermaid"] + "\n", encoding="utf-8")
        written.append(summary)
    return written
