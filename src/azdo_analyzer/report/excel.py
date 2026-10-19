"""Excel workbook (XlsxWriter): one sheet per entity, filterable tables."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import xlsxwriter

from azdo_analyzer.analyze import AnalysisResult, PipelineResult, RepoResult
from azdo_analyzer.cache import safe_name
from azdo_analyzer.util import compact

TEXT, INT, FLOAT, DATE, BOOL, URL, LINK = "text", "int", "float", "date", "bool", "url", "link"
Column = tuple[str, int, str]
NOTE = ("⚠ For initial reference only, not 100% accurate: please do your own analysis as well. "
        "Test repos, pipelines and releases are not excluded.")
TOP = 2  # every sheet: row 1 = the amber note, row 2 = spacer, tables from row 3

_SEVERITY = {"blocker": "#F8696B", "high": "#FFB3B3", "medium": "#FFE699", "low": "#DDEBF7", "info": "#EDEDED"}
_LEVEL = {"High": "#FFB3B3", "Medium": "#FFE699", "Low": "#C6EFCE"}
_ACTIVITY = {"Active": "#C6EFCE", "Dormant": "#FFE699", "Dead": "#FFB3B3", "Never": "#FFB3B3", "Disabled": "#EDEDED"}
_STATUS = {"OK": "#C6EFCE", "CACHED": "#C6EFCE", "FORBIDDEN": "#FFB3B3", "ERROR": "#F8696B", "NOT_FOUND": "#FFE699", "MISSING_OFFLINE": "#FFE699"}


class Book:
    def __init__(self, path: Path):
        self.wb = xlsxwriter.Workbook(str(path), {
            "strings_to_numbers": False, "strings_to_formulas": False, "strings_to_urls": False, "remove_timezone": True,
        })
        self.header = self.wb.add_format({"bold": True})
        self.date = self.wb.add_format({"num_format": "yyyy-mm-dd"})
        self.title = self.wb.add_format({"bold": True, "font_size": 14})
        self.subtitle = self.wb.add_format({"bold": True, "font_size": 11, "font_color": "#1F4E79"})
        self.link = self.wb.add_format({"font_color": "#0563C1", "underline": 1})
        self.note = self.wb.add_format({"bold": True, "bg_color": "#FFC000", "font_color": "#3A2A00", "valign": "vcenter", "indent": 1})
        self._noted: set[str] = set()
        self.fills = {color: self.wb.add_format({"bg_color": color}) for color in
                      set(_SEVERITY.values()) | set(_LEVEL.values()) | set(_ACTIVITY.values()) | set(_STATUS.values())}
        self._tables = 0

    def close(self) -> None:
        self.wb.close()

    def sheet(self, name: str):
        ws = self.wb.add_worksheet(name[:31])
        ws.set_row(0, 24)
        ws.set_row(1, 6)
        return ws

    def add_note(self, ws, width: int) -> None:
        """The amber disclaimer across the top of the sheet, as wide as its first table."""
        if ws.name in self._noted:
            return
        self._noted.add(ws.name)
        if width > 1:
            ws.merge_range(0, 0, 0, width - 1, NOTE, self.note)
        else:
            ws.write_string(0, 0, NOTE, self.note)

    def write_cell(self, ws, row: int, col: int, value: Any, kind: str) -> None:
        if value is None or value == "":
            ws.write_blank(row, col, None)
            return
        if kind == DATE and isinstance(value, datetime):
            ws.write_datetime(row, col, value, self.date)
        elif kind in (INT, FLOAT) and isinstance(value, (int, float)) and not isinstance(value, bool):
            ws.write_number(row, col, value)
        elif kind == BOOL:
            ws.write_string(row, col, "yes" if value else "no")
        elif kind in (URL, LINK) and isinstance(value, (str, tuple)):
            target, label = value if isinstance(value, tuple) else (value, value)
            if kind == LINK:
                target = f"external:{target}"
            if len(str(target)) < 2000:
                ws.write_url(row, col, str(target), self.link, str(label)[:255])
            else:
                ws.write_string(row, col, str(label))
        else:
            text = value if isinstance(value, str) else str(value)
            ws.write_string(row, col, text[:32000])

    def table(self, ws, columns: list[Column], rows: Iterable[list[Any]], *, start_row: int = TOP, title: str | None = None,
              freeze: bool = True, colorize: dict[str, dict[str, str]] | None = None) -> int:
        rows = list(rows)
        self.add_note(ws, len(columns))
        if title:
            ws.write_string(start_row, 0, title, self.subtitle)
            start_row += 1
        if not rows:
            rows = [["(none)"] + [None] * (len(columns) - 1)]
        last_row = start_row + len(rows)
        self._tables += 1
        ws.add_table(start_row, 0, last_row, len(columns) - 1, {
            "columns": [{"header": h} for h, _, _ in columns],
            "style": "Table Style Light 9",
            "name": f"tbl_{self._tables}",
        })
        for c, (_, width, _) in enumerate(columns):
            ws.set_column(c, c, width)
        for r, row in enumerate(rows, start=start_row + 1):
            for c, (_, _, kind) in enumerate(columns):
                self.write_cell(ws, r, c, row[c] if c < len(row) else None, kind)
        if freeze and start_row == TOP:
            ws.freeze_panes(TOP + 1, 0)  # the note and the header stay visible
        for header, palette in (colorize or {}).items():
            col = next((i for i, (h, _, _) in enumerate(columns) if h == header), None)
            if col is None:
                continue
            for value, color in palette.items():
                ws.conditional_format(start_row + 1, col, last_row, col, {
                    "type": "cell", "criteria": "==", "value": f'"{value}"', "format": self.fills[color],
                })
        return last_row + 2


def _yn(value: Any) -> bool:
    return bool(value)


def _kinds(results: list[PipelineResult]) -> str:
    return compact(sorted({r.pipeline.kind_label for r in results})) or "none"


# A pipeline's or release's own archetype values (from its definition), plus the stacks of the repos it builds or deploys.
_OWN_COLUMNS: list[Column] = [("Repo stack", 20, TEXT), ("Build tools", 18, TEXT), ("Test & scan tools", 18, TEXT),
                              ("Deploy targets", 22, TEXT), ("Artifacts produced", 18, TEXT)]


def _own_values(r: PipelineResult) -> list[str]:
    stacks = ", ".join(r.repo_stacks) or ("unknown" if r.repo_keys else "")  # blank = no repo in this project
    prof = r.profile
    if prof is None:
        return [stacks, "", "", "", ""]
    return [stacks, prof.build_tool, ", ".join(prof.quality_tools) or "none", prof.deploy, prof.artifact]


def write_workbook(result: AnalysisResult, path: Path, dossier_link: Callable[[RepoResult], str] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    book = Book(path)
    try:
        _summary(book, result)
        _tracker(book, result, dossier_link)
        _repos(book, result)
        _pipelines(book, result)
        _releases(book, result)
        _stages(book, result)
        _tasks(book, result)
        _variables(book, result)
        _groups(book, result)
        _connections(book, result)
        _secure_files(book, result)
        _agents(book, result)
        _environments(book, result)
        _policies(book, result)
        _dependencies(book, result)
        _findings(book, result)
        _archetypes(book, result)
        _coverage(book, result)
    finally:
        book.close()
    return path


def _summary(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Summary")
    ws.write_string(TOP, 0, "AZDO -> GitLab migration analysis", book.title)
    info = [
        ("Generated", result.generated.strftime("%Y-%m-%d %H:%M UTC")),
        ("Collection", result.cfg.azdo.collection_url or "(offline)"),
        ("GitLab target tier", result.cfg.analysis.gitlab_tier),
        ("Projects", ", ".join(p.name for p in result.projects)),
        ("Activity windows", f"Active <= {result.cfg.analysis.active_days} days, Dormant <= {result.cfg.analysis.dormant_days} days; run history {result.cfg.collection.history_days} days"),
    ]
    for i, (k, v) in enumerate(info, start=TOP + 2):
        ws.write_string(i, 0, k, book.header)
        ws.write_string(i, 1, v)
    row = TOP + len(info) + 3
    project_rows = []
    for p in result.projects:
        statuses = Counter(r.status for r in p.repos)
        kinds = Counter(r.pipeline.kind for r in p.pipelines.values())
        levels = Counter(r.complexity for r in p.repos if r.status != "Disabled")
        findings = p.all_findings()
        project_rows.append([
            p.name, "deep" if p.deep else "inventory", len(p.repos), statuses.get("Active", 0), statuses.get("Dormant", 0),
            statuses.get("Dead", 0) + statuses.get("Never", 0), statuses.get("Disabled", 0), kinds.get("yaml", 0), kinds.get("classic_build", 0),
            kinds.get("classic_release", 0), levels.get("Low", 0), levels.get("Medium", 0), levels.get("High", 0),
            sum(1 for f in findings if f.severity == "blocker"), sum(1 for f in findings if f.severity == "high"),
            "yes" if p.tfvc else "no", p.raw.meta.get("fetched_at", ""),
        ])
    row = book.table(ws, [
        ("Project", 28, TEXT), ("Mode", 10, TEXT), ("Repos", 7, INT), ("Active", 7, INT), ("Dormant", 8, INT), ("Dead", 6, INT),
        ("Disabled", 8, INT), ("YAML", 6, INT), ("Classic build", 12, INT), ("Classic release", 14, INT), ("Low", 6, INT),
        ("Medium", 8, INT), ("High", 6, INT), ("Blocker findings", 15, INT), ("High findings", 12, INT), ("TFVC", 6, TEXT), ("Data as of", 20, TEXT),
    ], project_rows, start_row=row, title="Projects", freeze=False)
    counts = Counter((f.id, f.severity, f.title) for f in result.all_findings())
    row = book.table(ws, [("Finding", 24, TEXT), ("Severity", 9, TEXT), ("Title", 50, TEXT), ("Count", 7, INT)],
                     [[k[0], k[1], k[2], v] for k, v in sorted(counts.items(), key=lambda kv: (_rank(kv[0][1]), -kv[1]))],
                     start_row=row, title="Findings by type", freeze=False, colorize={"Severity": _SEVERITY})
    unmapped = [t for t in result.tasks if not t["mapped"] and t["source"] != "yaml"][:15]
    row = book.table(ws, [("Unmapped task", 34, TEXT), ("Source", 10, TEXT), ("Uses", 7, INT), ("Pipelines", 9, INT)],
                     [[t["task"], t["source"], t["uses"], t["pipelines"]] for t in unmapped], start_row=row, title="Top unmapped tasks", freeze=False)
    book.table(ws, [("Archetype", 50, TEXT), ("Name", 36, TEXT), ("Repos", 7, INT)],
               [[a["key"], a["name"], a["repo_count"]] for a in result.archetypes[:10]], start_row=row, title="Top archetypes", freeze=False)


def _rank(severity: str) -> int:
    return {"blocker": 0, "high": 1, "medium": 2, "low": 3, "info": 4}.get(severity, 9)


def _tracker(book: Book, result: AnalysisResult, dossier_link: Callable[[RepoResult], str] | None) -> None:
    ws = book.sheet("Tracker")
    rows = []
    for p in result.projects:
        for repo in p.repos:
            linked = [p.pipelines[k] for k in repo.pipelines + repo.releases if k in p.pipelines]
            serious = [f for f in repo.findings if f.severity in ("blocker", "high")]
            o = repo.override
            link = (dossier_link(repo), "dossier") if dossier_link and p.deep else None
            rows.append([
                p.name, repo.name, repo.gitlab_path + (" (slug collision!)" if repo.slug_collision else ""), repo.archetype,
                _kinds(linked) if linked or not repo.template_for else f"templates for {compact(repo.template_for, limit=3)}",
                len(repo.pipelines), len(repo.releases), repo.complexity, repo.score.points, "yes" if repo.score.blocker else "",
                compact(sorted({f.id for f in serious}), limit=6), repo.status, o.get("recommendation") or repo.recommendation,
                o.get("template") or repo.profile.template or "", o.get("wave"), o.get("owner"), o.get("status") or "Not started",
                o.get("notes"), link,
            ])
    book.table(ws, [
        ("Project", 22, TEXT), ("Repo", 30, TEXT), ("GitLab path", 34, TEXT), ("Archetype", 34, TEXT), ("Pipeline type", 24, TEXT),
        ("Build pipelines", 9, INT), ("Releases", 9, INT), ("Complexity", 11, TEXT), ("Score", 7, INT), ("Blocker", 8, TEXT),
        ("Blocker/high findings", 40, TEXT), ("Activity", 10, TEXT), ("Recommendation", 18, TEXT), ("Template", 24, TEXT),
        ("Wave", 7, TEXT), ("Owner", 16, TEXT), ("Status", 14, TEXT), ("Notes", 30, TEXT), ("Dossier", 10, LINK),
    ], rows, colorize={"Complexity": _LEVEL, "Activity": _ACTIVITY})


def _repos(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Repos")
    rows = []
    for p in result.projects:
        for r in p.repos:
            s, a = r.scan, r.activity
            rows.append([
                p.name, r.name, (r.repo.get("defaultBranch") or "").replace("refs/heads/", ""), round((r.repo.get("size") or 0) / 1024 / 1024, 1),
                _yn(r.repo.get("isDisabled")), _yn(r.repo.get("isFork")), a.branches, a.stale_branches, a.branching_model, a.tags, a.last_commit_any,
                a.open_prs, a.oldest_pr_days, r.profile.stack, r.profile.build_tool, ", ".join(r.profile.quality_tools) or "none",
                r.profile.deploy, r.profile.artifact, ", ".join(r.profile.markers),
                bool(s and s.lfs_patterns), bool(s and s.submodules), compact(sorted({f["feed"] for f in s.feeds})) if s else "",
                (s.counts.get("AZDO_URL", 0) if s else None), (s.counts.get("VSO_LOGGING_CMD", 0) if s else None),
                s.source if s else "not scanned", r.repo.get("webUrl"),
            ])
    book.table(ws, [
        ("Project", 20, TEXT), ("Repo", 28, TEXT), ("Default branch", 14, TEXT), ("Size MB", 9, FLOAT), ("Disabled", 8, BOOL),
        ("Fork", 6, BOOL), ("Branches", 9, INT), ("Stale branches", 9, INT), ("Branching model", 24, TEXT), ("Tags", 6, INT),
        ("Last commit", 11, DATE), ("Open PRs", 8, INT), ("Oldest PR days", 9, INT), ("Stack", 22, TEXT), ("Build tools", 18, TEXT),
        ("Test & scan tools", 20, TEXT), ("Deploy targets", 20, TEXT), ("Artifacts", 16, TEXT), ("Markers", 22, TEXT), ("LFS", 5, BOOL),
        ("Submodules", 6, BOOL), ("Azure Artifacts feeds", 24, TEXT),
        ("AZDO URL hits", 8, INT), ("##vso hits", 8, INT), ("Content", 10, TEXT), ("Web URL", 40, URL),
    ], rows)


def _pipelines(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Pipelines")
    rows = []
    for p in result.projects:
        for r in p.pipelines.values():
            pl, f, st = r.pipeline, r.facts, r.stats
            if pl.kind == "classic_release":
                continue
            jobs = pl.all_jobs()
            rows.append([
                p.name, pl.name, pl.id, pl.kind_label, pl.folder, pl.repo_name, pl.yaml_path, pl.enabled, pl.depth,
                compact({j.pool or j.vm_image or "" for j in jobs}), compact({d for j in jobs for d in j.demands}),
                compact(t.describe() for t in pl.triggers), compact(f.variable_groups), compact(f.service_connections),
                len(pl.all_steps()), len(f.tasks), compact(f.unmapped_tasks), compact(f.task_groups), len(pl.templates),
                *_own_values(r), r.last_activity, st.runs if st else 0, st.runs_90d if st else 0, st.success_rate if st else None,
                st.p50_minutes if st else None, st.p95_minutes if st else None, st.queue_p95_minutes if st else None,
                r.activity, r.fingerprint, r.score.points, r.score.level, r.score.describe(), compact(pl.warnings, limit=3), pl.url,
            ])
    book.table(ws, [
        ("Project", 18, TEXT), ("Pipeline", 30, TEXT), ("ID", 6, INT), ("Kind", 13, TEXT), ("Folder", 14, TEXT), ("Repo", 22, TEXT),
        ("YAML path", 24, TEXT), ("Enabled", 8, BOOL), ("Depth", 9, TEXT), ("Pools", 18, TEXT), ("Demands", 18, TEXT), ("Triggers", 40, TEXT),
        ("Variable groups", 22, TEXT), ("Service connections", 24, TEXT), ("Steps", 6, INT), ("Distinct tasks", 8, INT),
        ("Unmapped tasks", 24, TEXT), ("Task groups", 18, TEXT), ("Templates", 9, INT), *_OWN_COLUMNS, ("Last run", 11, DATE), ("Runs", 6, INT),
        ("Runs 90d", 7, INT), ("Success %", 8, FLOAT), ("p50 min", 7, FLOAT), ("p95 min", 7, FLOAT), ("Queue p95 min", 9, FLOAT),
        ("Activity", 9, TEXT), ("Fingerprint", 11, TEXT), ("Score", 6, INT), ("Complexity", 10, TEXT), ("Score reasons", 50, TEXT),
        ("Warnings", 30, TEXT), ("URL", 40, URL),
    ], rows, colorize={"Complexity": _LEVEL, "Activity": _ACTIVITY})


def _releases(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Releases")
    rows = []
    for p in result.projects:
        for r in p.pipelines.values():
            pl, f = r.pipeline, r.facts
            if pl.kind != "classic_release":
                continue
            deployments = sum(s["deployments"] or 0 for s in p.stages if s["pipeline_key"] == pl.key)
            rows.append([
                p.name, pl.name, pl.id, pl.folder, pl.enabled, pl.depth,
                compact(f"{a.alias} ({a.type}: {a.source_name})" for a in pl.artifacts), compact(t.describe() for t in pl.triggers),
                len(pl.stages), compact(f.approvals), compact(f.gates), compact(f.deployment_groups), compact(f.variable_groups),
                compact(f.service_connections), len(f.tasks), compact(f.unmapped_tasks), *_own_values(r), r.last_activity, deployments, r.activity,
                r.score.points, r.score.level, r.score.describe(), pl.url,
            ])
    book.table(ws, [
        ("Project", 18, TEXT), ("Release", 30, TEXT), ("ID", 6, INT), ("Folder", 14, TEXT), ("Enabled", 8, BOOL), ("Depth", 9, TEXT),
        ("Artifacts", 40, TEXT), ("Triggers", 30, TEXT), ("Stages", 7, INT), ("Approvals", 30, TEXT), ("Gates", 26, TEXT),
        ("Deployment groups", 20, TEXT), ("Variable groups", 22, TEXT), ("Service connections", 24, TEXT), ("Distinct tasks", 8, INT),
        ("Unmapped tasks", 24, TEXT), *_OWN_COLUMNS, ("Last deployment", 12, DATE), ("Deployments", 9, INT), ("Activity", 9, TEXT), ("Score", 6, INT),
        ("Complexity", 10, TEXT), ("Score reasons", 50, TEXT), ("URL", 40, URL),
    ], rows, colorize={"Complexity": _LEVEL, "Activity": _ACTIVITY})


def _stages(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Release Stages")
    rows = [[s["project"], s["pipeline"], s["kind"], s["stage"], s["rank"], s["trigger"], s["pre_approvers"], s["post_approvers"],
             s["required"], s["creator_can_approve"], s["gates"], s["jobs"], s["environment"], s["queue_policy"], s["variables"],
             s["tasks"], s["deployments"], s["last_deployed"], s["success_rate"]] for p in result.projects for s in p.stages]
    book.table(ws, [
        ("Project", 18, TEXT), ("Pipeline", 28, TEXT), ("Kind", 13, TEXT), ("Stage", 18, TEXT), ("Rank", 5, INT), ("Trigger", 30, TEXT),
        ("Pre-deploy approvers", 30, TEXT), ("Post-deploy approvers", 24, TEXT), ("Required approvals", 9, TEXT),
        ("Creator can approve", 9, TEXT), ("Gates", 26, TEXT), ("Jobs", 30, TEXT), ("Environment", 16, TEXT), ("Queue policy", 20, TEXT),
        ("Stage variables", 8, INT), ("Tasks", 50, TEXT), ("Deployments", 9, INT), ("Last deployed", 12, DATE), ("Success %", 8, FLOAT),
    ], rows)


def _tasks(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Tasks")
    rows = [[t["task"], t["friendly"], t["source"], t["extension"], t["uses"], t["pipelines"], t["repos"], t["mapped"], t["gitlab"],
             t["image"], t["effort"], t["windows"], t["category"], t["notes"], t["examples"]] for t in result.tasks]
    book.table(ws, [
        ("Task", 30, TEXT), ("Name", 26, TEXT), ("Source", 10, TEXT), ("Extension", 24, TEXT), ("Uses", 6, INT), ("Pipelines", 8, INT),
        ("Repos", 6, INT), ("Mapped", 7, BOOL), ("GitLab approach", 60, TEXT), ("Image hint", 28, TEXT), ("Effort", 8, TEXT),
        ("Windows", 8, BOOL), ("Category", 10, TEXT), ("Notes", 30, TEXT), ("Examples", 40, TEXT),
    ], rows, colorize={"Mapped": {"no": "#FFE699"}})


def _variables(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Variables")
    rows = [[v["project"], v["scope_type"], v["owner"], v["name"], v["secret"], v["settable"], v["value"], v["valid_key"],
             v["proposed_key"], v["proposed_level"], v["used_by"]] for p in result.projects for v in p.variables]
    book.table(ws, [
        ("Project", 18, TEXT), ("Scope", 12, TEXT), ("Owner", 30, TEXT), ("Variable", 30, TEXT), ("Secret", 7, BOOL),
        ("Settable at queue", 9, BOOL), ("Value", 30, TEXT), ("Valid GitLab key", 9, BOOL), ("Proposed key", 30, TEXT),
        ("Proposed GitLab level", 40, TEXT), ("Used by", 40, TEXT),
    ], rows, colorize={"Valid GitLab key": {"no": "#FFE699"}})


def _groups(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Variable Groups")
    rows = [[g["project"], g["name"], g["id"], g["type"], g["variables"], g["secrets"], g["key_vault"], g["shared_projects"],
             g["used_by"], g["repos"], g["proposed_level"]] for p in result.projects for g in p.groups]
    book.table(ws, [
        ("Project", 18, TEXT), ("Group", 28, TEXT), ("ID", 6, INT), ("Type", 14, TEXT), ("Variables", 9, INT), ("Secrets", 8, INT),
        ("Key Vault", 18, TEXT), ("Shared with projects", 24, TEXT), ("Used by pipelines", 40, TEXT), ("Repos", 40, TEXT),
        ("Proposed level", 20, TEXT),
    ], rows)


def _connections(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Service Connections")
    rows = [[c["project"], c["name"], c["type"], c["scheme"], c["url"], c["internal"], c["shared"], c["projects"], c["used_by"],
             c["executions"], c["last_used"], c["authorized"], c["gitlab"]] for p in result.projects for c in p.connections]
    book.table(ws, [
        ("Project", 18, TEXT), ("Name", 28, TEXT), ("Type", 16, TEXT), ("Auth scheme", 18, TEXT), ("URL", 36, TEXT),
        ("Internal host", 9, BOOL), ("Shared", 7, BOOL), ("Other projects", 20, TEXT), ("Used by (definitions)", 40, TEXT),
        ("Executions (recent)", 10, INT), ("Last used", 11, DATE), ("Authorized pipelines", 20, TEXT), ("GitLab replacement", 50, TEXT),
    ], rows, colorize={"Internal host": {"yes": "#FFE699"}})


def _secure_files(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Secure Files")
    rows = [[s["project"], s["name"], s["modified"], s["modified_by"], s["used_by"], s["authorized"], s["gitlab"]]
            for p in result.projects for s in p.secure_files]
    book.table(ws, [("Project", 18, TEXT), ("Name", 30, TEXT), ("Modified", 20, TEXT), ("Modified by", 20, TEXT), ("Used by", 40, TEXT),
                    ("Authorized", 20, TEXT), ("GitLab replacement", 50, TEXT)], rows)


def _agents(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Agents & Pools")
    rows = [[a["pool"], a["agent"], a["os"], a["version"], a["status"], a["enabled"], a["tools"], a["last_job"], a["peak"], a["minutes"], a["runs"]]
            for a in result.agents]
    book.table(ws, [
        ("Pool", 22, TEXT), ("Agent", 24, TEXT), ("OS", 30, TEXT), ("Agent version", 10, TEXT), ("Status", 8, TEXT), ("Enabled", 8, BOOL),
        ("Tools found in capabilities", 60, TEXT), ("Last job", 11, DATE), ("Pool peak concurrency", 10, INT),
        ("Pool build min/month", 10, FLOAT), ("Pool runs (window)", 10, INT),
    ], rows)


def _environments(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Environments & Deploy Groups")
    rows = [[e["project"], e["kind"], e["name"], e["targets"], e["tags"], e["checks"], e["deployments"], e["last_deployment"], e["used_by"], e["gitlab"]]
            for p in result.projects for e in p.environments]
    book.table(ws, [
        ("Project", 18, TEXT), ("Kind", 16, TEXT), ("Name", 24, TEXT), ("Targets / resources", 40, TEXT), ("Tags", 18, TEXT),
        ("Checks", 40, TEXT), ("Deployments", 9, INT), ("Last deployment", 12, DATE), ("Used by", 36, TEXT), ("GitLab mapping", 60, TEXT),
    ], rows)


def _policies(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Branch Policies")
    rows = [[x.project, x.repo, x.branch, x.policy, x.enabled, x.blocking, x.settings, x.gitlab] for p in result.projects for x in p.policies]
    book.table(ws, [("Project", 18, TEXT), ("Repo", 26, TEXT), ("Branch", 18, TEXT), ("Policy", 28, TEXT), ("Enabled", 8, BOOL),
                    ("Blocking", 8, BOOL), ("Settings", 60, TEXT), ("GitLab equivalent", 60, TEXT)], rows)


def _dependencies(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Dependencies")
    rows = [[e.project, e.src_kind, e.src, e.relation, e.dst_kind, e.dst, e.dst_project, e.evidence] for p in result.projects for e in p.usage.edges]
    book.table(ws, [("Project", 18, TEXT), ("From kind", 16, TEXT), ("From", 30, TEXT), ("Relation", 12, TEXT), ("To kind", 18, TEXT),
                    ("To", 30, TEXT), ("Other project", 16, TEXT), ("Evidence", 40, TEXT)], rows)


def _findings(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Findings")
    rows = [[f.severity, f.id, f.title, f.project, f.repo, f.pipeline, f.detail, f.remediation] for f in result.all_findings()]
    book.table(ws, [("Severity", 9, TEXT), ("ID", 22, TEXT), ("Title", 40, TEXT), ("Project", 18, TEXT), ("Repo", 24, TEXT),
                    ("Pipeline", 28, TEXT), ("Detail", 60, TEXT), ("Remediation", 80, TEXT)], rows, colorize={"Severity": _SEVERITY})


def _archetypes(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Archetypes")
    row = book.table(ws, [
        ("Archetype key (stack | build | deploy | artifact)", 50, TEXT), ("Stack", 22, TEXT), ("Build tools", 18, TEXT),
        ("Deploy targets", 20, TEXT), ("Artifacts", 16, TEXT), ("Named archetype", 36, TEXT), ("Proposed template", 24, TEXT),
        ("Repos", 7, INT), ("Pipelines", 9, INT), ("Avg score", 9, FLOAT), ("Complexity mix", 22, TEXT),
        ("Test & scan tools (repos)", 30, TEXT), ("Markers (repos)", 30, TEXT), ("Repos list", 80, TEXT),
    ], [[a["key"], a["stack"], a["build"], a["deploy"], a["artifact"], a["name"], a["template"], a["repo_count"], a["pipelines"],
         a["avg_points"], a["levels"], a["quality"], a["markers"], compact(a["repos"], limit=15)] for a in result.archetypes])
    row = book.table(ws, [
        ("Dimension", 16, TEXT), ("Value", 22, TEXT), ("What it is", 44, TEXT), ("Repos", 7, INT), ("Build pipelines", 9, INT),
        ("Releases", 9, INT), ("Found together with (repos)", 70, TEXT), ("Repos list", 60, TEXT), ("Releases list", 60, TEXT),
    ], [[c["dimension"], c["value"], c["label"], c["repo_count"], c["build_count"], c["release_count"], c["with"],
         compact(c["repos"], limit=15), compact(c["releases"], limit=15)]
        for c in result.components], start_row=row + 1, title="Archetype components (one row per value of each dimension)", freeze=False)
    book.table(ws, [("Clone type", 18, TEXT), ("Fingerprint", 11, TEXT), ("Pipelines", 60, TEXT), ("Count", 7, INT), ("Task sequence", 80, TEXT)],
               [[c["type"], c["fingerprint"], compact(c["pipelines"], limit=10), len(c["pipelines"]), c["tasks"]] for c in result.clones],
               start_row=row + 1, title="Pipeline clones (same or similar task sequence)", freeze=False)


def _coverage(book: Book, result: AnalysisResult) -> None:
    ws = book.sheet("Coverage")
    rows = [[c.get("scope"), c.get("collector"), c.get("endpoint"), c.get("status"), c.get("calls"), c.get("failed"), c.get("items"), c.get("message")]
            for c in sorted(result.coverage, key=lambda c: (c.get("scope") != "_org", c.get("scope"), c.get("collector"), c.get("endpoint")))]
    book.table(ws, [("Scope", 18, TEXT), ("Collector", 12, TEXT), ("Endpoint", 44, TEXT), ("Status", 14, TEXT), ("Calls", 7, INT),
                    ("Failed", 7, INT), ("Items", 7, INT), ("Message", 80, TEXT)], rows, colorize={"Status": _STATUS})


def workbook_name(label: str) -> str:
    return f"azdo-analysis-{safe_name(label)}.xlsx"
