"""The report docs explain every workbook column and every finding, and their links work."""

from __future__ import annotations

import re
from pathlib import Path

import openpyxl
import yaml
from openpyxl.utils.cell import range_boundaries

from azdo_analyzer.analyze import run_analysis
from azdo_analyzer.config import PROJECT_ROOT
from azdo_analyzer.report import write_reports
from tests.fixtures.sample_data import NOW, PROJECT

DOCS = PROJECT_ROOT / "docs" / "reports"


def sheet_doc(sheet: str) -> Path:
    return DOCS / "workbook" / (sheet.lower().replace(" & ", "-and-").replace(" ", "-") + ".md")


def test_every_workbook_column_is_documented(sample_cfg, rules, provider):
    result = run_analysis(sample_cfg, rules, [PROJECT], provider=provider, now=NOW)
    workbook = openpyxl.load_workbook(write_reports(result, "docs", dossiers=False)["workbook"])
    index = (DOCS / "workbook" / "README.md").read_text(encoding="utf-8")
    missing = []
    for ws in workbook.worksheets:
        doc = sheet_doc(ws.title)
        assert doc.exists(), f"no doc for sheet {ws.title}: expected {doc.name}"
        assert f"| {ws.title} |" in index, f"sheet {ws.title} missing from workbook/README.md"
        text = doc.read_text(encoding="utf-8")
        for table in ws.tables.values():
            min_col, min_row, max_col, _ = range_boundaries(table.ref)
            for col in range(min_col, max_col + 1):
                header = str(ws.cell(row=min_row, column=col).value)
                cell = header.replace("|", "\\|")
                if not re.search(rf"^\| {re.escape(cell)} \|", text, re.M):
                    missing.append(f"{ws.title} → {header}")
    assert missing == []


def test_findings_catalogue_matches_rules():
    catalogue = yaml.safe_load((PROJECT_ROOT / "rules" / "findings.yaml").read_text(encoding="utf-8"))["findings"]
    text = (DOCS / "workbook" / "findings.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^\| `([A-Z_]+)` \|", text, re.M))
    assert documented == set(catalogue), (set(catalogue) - documented, documented - set(catalogue))
    for fid, meta in catalogue.items():
        assert re.search(rf"^\| `{fid}` \| {meta['severity']}\b", text, re.M), f"{fid}: severity should be {meta['severity']}"


def _slug(heading: str) -> str:
    """GitHub-style heading anchor."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def test_relative_links_and_anchors_resolve():
    broken = []
    for doc in sorted(DOCS.rglob("*.md")):
        text = re.sub(r"`[^`\n]*`", "", doc.read_text(encoding="utf-8"))  # code spans are not links (regexes contain "](")
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"^[a-z]+://", target):
                continue
            path_part, _, anchor = target.partition("#")
            resolved = (doc.parent / path_part).resolve() if path_part else doc
            if not resolved.exists():
                broken.append(f"{doc.relative_to(DOCS)} → {target}")
                continue
            if anchor and resolved.suffix == ".md":
                headings = {_slug(h) for h in re.findall(r"^#{1,6} (.+)$", resolved.read_text(encoding="utf-8"), re.M)}
                if anchor not in headings:
                    broken.append(f"{doc.relative_to(DOCS)} → {target} (no such heading)")
    assert broken == []


def test_archetype_values_page_matches_the_rules():
    from azdo_analyzer.report.archetype_doc import DOC_PATH, RULES_PATH, render

    expected = render(yaml.safe_load(RULES_PATH.read_text(encoding="utf-8")))
    assert DOC_PATH.read_text(encoding="utf-8") == expected, "regenerate it: python -m azdo_analyzer.report.archetype_doc"


def _pattern_counts() -> dict:
    """Counts shown in the docs, recomputed from rules/ and the findings code."""
    import inspect

    from azdo_analyzer.analyze import analyze_project
    from azdo_analyzer.analyze.findings import pipeline_findings, repo_findings

    rules_dir = PROJECT_ROOT / "rules"
    arch = yaml.safe_load((rules_dir / "archetypes.yaml").read_text(encoding="utf-8"))
    signals = ("tasks", "task_inputs", "commands", "script_regex", "endpoint_types", "deployment_group")
    dims: dict[str, int] = {}
    from_files: dict[str, int] = {}
    tasks: set[str] = set()
    endpoints: set[str] = set()
    commands = regexes = 0
    for section, label in (("build_tools", "Build tools"), ("quality_tools", "Test & scan tools"),
                           ("deploy_targets", "Deploy targets"), ("artifacts", "Artifacts")):
        specs = [spec or {} for spec in arch[section].values()]
        dims[label] = sum(1 for spec in specs if any(spec.get(k) for k in signals))
        from_files[label] = sum(1 for spec in specs if spec.get("files") or spec.get("match") or spec.get("markers"))
        for spec in specs:
            tasks |= {str(x).lower() for x in spec.get("tasks") or []} | {str(x).lower() for x in spec.get("task_inputs") or {}}
            endpoints |= set(spec.get("endpoint_types") or [])
            commands += len(spec.get("commands") or [])
            regexes += bool(spec.get("script_regex"))
    findings = set(re.findall(r'add\("([A-Z_]+)"', inspect.getsource(pipeline_findings)))
    findings |= set(re.findall(r'make\(rules, "([A-Z_]+)"', inspect.getsource(analyze_project)))
    variables = yaml.safe_load((rules_dir / "predefined_vars.yaml").read_text(encoding="utf-8"))["variables"]
    return {
        "dims": dims, "from_files": from_files, "tasks": len(tasks), "endpoints": len(endpoints), "commands": commands,
        "regexes": regexes, "findings": len(findings), "variables": len(variables),
        "prefixes": sum(1 for name in variables if name.endswith(".*")),
        "repo_findings": len(set(re.findall(r'add\("([A-Z_]+)"', inspect.getsource(repo_findings)))),
        "mapped": len(yaml.safe_load((rules_dir / "task_mapping.yaml").read_text(encoding="utf-8"))["tasks"]),
        "factors": len(yaml.safe_load((rules_dir / "scoring.yaml").read_text(encoding="utf-8"))["points"]),
        "stacks": len(arch["stacks"]), "markers": len(arch["markers"]),
    }


def test_pipeline_pattern_counts_match_the_rules():
    """The counts on the Pipelines and Releases pages."""
    c = _pattern_counts()
    pipelines = (DOCS / "workbook" / "pipelines.md").read_text(encoding="utf-8")
    releases = (DOCS / "workbook" / "releases.md").read_text(encoding="utf-8")
    expected = [f"| {label} | {n} |" for label, n in c["dims"].items()] + [
        f"| Findings | {c['findings']} |",
        f"| Tasks mapped to a GitLab approach | {c['mapped']} |",
        f"| Complexity factors | {c['factors']} |",
        f"| Azure DevOps variables mapped to GitLab `CI_*` variables | {c['variables']} | "
        f"{c['variables'] - c['prefixes']} variables plus {c['prefixes']} prefix families",
        f"{c['tasks']} task names, {c['commands']} script commands",
        f"{c['regexes']} script regexes and {c['endpoints']} service-connection types",
    ]
    for page, text in (("pipelines.md", pipelines), ("releases.md", releases)):
        expected_here = expected if page == "pipelines.md" else []
        for needle in expected_here + [f"{sum(c['dims'].values())} technology patterns", f"{c['findings']} kinds of findings"]:
            assert needle in text, f"{page}: expected {needle!r} (update the counts on the page)"


def test_readme_pattern_counts_match_the_rules():
    """The "What it identifies" section of the root README: totals, and group counts that add up to them."""
    c = _pattern_counts()
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    section = readme[readme.index("## What it identifies"):readme.index("## How it works")]
    ff = c["from_files"]
    expected = [
        f"| Stacks | {c['stacks']} |", f"| Markers | {c['markers']} |",
        f"| Also from files | {ff['Build tools'] + ff['Test & scan tools'] + ff['Artifacts']} |",
        f"**Build tools ({ff['Build tools']}):** from lock files", f"**Test & scan tools ({ff['Test & scan tools']}):** from config files",
        f"**Artifacts ({ff['Artifacts']}):**", f"{c['repo_findings']} kinds of findings",
        *(f"| {label} | {n} |" for label, n in c["dims"].items()),
        f"| Findings | {c['findings']} |", f"| Technology patterns and findings | {sum(c['dims'].values())} + {c['findings']} |",
        f"maps {c['mapped']} tasks", f"{c['variables']} Azure DevOps variables", f"{c['factors']} factors",
    ]
    for needle in expected:
        assert needle in section, f"README: expected {needle!r} (update the counts)"
    for row in re.findall(r"^\| [^|]+ \| (\d+) \| (.+) \|$", section, re.M):
        groups = [int(n) for n in re.findall(r"\*\*[^*]*\((\d+)\):\*\*", row[1])]
        if groups:
            assert sum(groups) == int(row[0]), f"README: groups add up to {sum(groups)}, not {row[0]}: {row[1][:60]}"
