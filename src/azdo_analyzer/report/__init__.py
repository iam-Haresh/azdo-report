"""Report writers: Excel workbook, per-repo dossiers, project summaries, drift diff."""

from __future__ import annotations

from pathlib import Path

from azdo_analyzer.analyze import AnalysisResult
from azdo_analyzer.report.diff import write_diff
from azdo_analyzer.report.dossier import dossier_relpath, write_dossiers
from azdo_analyzer.report.excel import workbook_name, write_workbook
from azdo_analyzer.report.summary import write_summaries


def write_reports(result: AnalysisResult, label: str, *, dossiers: bool = True) -> dict[str, object]:
    out_dir: Path = result.cfg.reports_dir / result.generated.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    written_dossiers = write_dossiers(result, out_dir) if dossiers else {}
    workbook = write_workbook(result, out_dir / workbook_name(label), dossier_relpath if written_dossiers else None)
    summaries = write_summaries(result, out_dir)
    diff = write_diff(result, result.cfg.model_dir, out_dir / f"diff-{label}.md")
    return {"dir": out_dir, "workbook": workbook, "dossiers": written_dossiers, "summaries": summaries, "diff": diff}
