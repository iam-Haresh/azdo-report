"""azdo-analyzer command line: doctor | inventory | analyze."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from azdo_analyzer.analyze import run_analysis
from azdo_analyzer.cache import RawStore
from azdo_analyzer.client import AzdoClient, AzdoHttpError, RedactingFilter
from azdo_analyzer.collect import CollectContext, Coverage, collect_all
from azdo_analyzer.collect.content import GIT_READ_COMMANDS, FileProvider, run_git
from azdo_analyzer.collect.repos import tfvc_capability, tfvc_probe_params
from azdo_analyzer.config import Config, ConfigError, get_pat, load_config, resolve_collection
from azdo_analyzer.report import write_reports
from azdo_analyzer.rules import load_rules
from azdo_analyzer.util import slugify, utcnow

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Read-only Azure DevOps Server analysis for planning an AZDO -> GitLab migration.")
console = Console()
ConfigOpt = typer.Option(None, "--config", "-c", help="Path to config.yaml (default: ./config.yaml)")
CollectionOpt = typer.Option(
    None, "--collection",
    help="Collection URL (https://server/DefaultCollection), or just a collection name on the server from config.yaml. "
         "Overrides azdo.collection_url and AZDO_COLLECTION_URL.")
OutputDirOpt = typer.Option(None, "--output-dir", help="Output folder (cache, clones, reports). Overrides output.dir.")


def _setup_logging(cfg: Config, client: AzdoClient | None, verbose: bool) -> Path:
    log_dir = cfg.out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    if client is not None:
        handler.addFilter(RedactingFilter(client.redact))
    root = logging.getLogger("azdo_analyzer")
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    return log_file


def _client(cfg: Config, pat: str) -> AzdoClient:
    return AzdoClient(cfg.azdo.collection_url, pat, api_version=cfg.azdo.api_version, verify=cfg.tls_verify,
                      timeout=cfg.azdo.timeout_seconds, max_retries=cfg.azdo.max_retries, concurrency=cfg.azdo.concurrency)


def _load(config: Optional[Path], collection: Optional[str] = None, output_dir: Optional[Path] = None) -> Config:
    try:
        cfg = load_config(config)
        if collection:
            cfg.azdo.collection_url = resolve_collection(collection, cfg.azdo.collection_url)
    except ConfigError as exc:
        console.print(f"[red]Config error:[/red] {exc}")
        raise typer.Exit(2) from None
    if output_dir:
        cfg.output.dir = str(output_dir.expanduser().resolve())  # relative to the current folder, like any CLI path
    return cfg


def _check_cache_collection(cfg: Config, store: RawStore) -> None:
    """One output folder holds one collection: stop instead of mixing cached data of two collections."""
    cached = (store.read("_org", "_meta.json", default={}) or {}).get("collection_url")
    current = cfg.azdo.collection_url
    if cached and current and cached.rstrip("/").lower() != current.rstrip("/").lower():
        console.print(f"[red]{cfg.out_dir} holds data from {cached}, not {current}.[/red] "
                      f"Use one output folder per collection, e.g. --output-dir out-<collection> "
                      f"(or delete {cfg.raw_dir} to start over).")
        raise typer.Exit(2)


def _require_url(cfg: Config) -> None:
    if not cfg.azdo.collection_url:
        console.print("[red]azdo.collection_url is not set[/red] (config.yaml or AZDO_COLLECTION_URL), "
                      "e.g. https://azdo.example.com/DefaultCollection")
        raise typer.Exit(2)


@app.command()
def doctor(config: Optional[Path] = ConfigOpt, collection: Optional[str] = CollectionOpt,
           output_dir: Optional[Path] = OutputDirOpt) -> None:
    """Check connectivity, TLS, API version and which collectors the PAT can use."""
    cfg = _load(config, collection, output_dir)
    _require_url(cfg)
    try:
        pat = get_pat(cfg.azdo)
    except ConfigError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(2) from None
    client = _client(cfg, pat)
    _setup_logging(cfg, client, verbose=True)
    console.print(f"Collection: [bold]{cfg.azdo.collection_url}[/bold]  TLS verify: {cfg.tls_verify}")
    try:
        who = client.connection_data().get("authenticatedUser") or {}
        console.print(f"Authenticated as: [bold]{who.get('providerDisplayName') or who.get('customDisplayName') or who.get('id')}[/bold]")
    except AzdoHttpError as exc:
        console.print(f"[red]Cannot authenticate:[/red] {exc.message}")
        raise typer.Exit(1) from None
    try:
        version = client.detect_api_version()
    except AzdoHttpError as exc:
        console.print(f"[red]API version detection failed:[/red] {exc.message}")
        raise typer.Exit(1) from None
    console.print(f"Newest REST API version accepted: [bold]{version}[/bold] (config uses {cfg.azdo.api_version})")
    client.api_version = version
    projects = client.get_list("projects", {"$top": 5})
    if not projects:
        console.print("[yellow]No projects visible to this PAT.[/yellow]")
        raise typer.Exit(1)
    project = projects[0]["name"]
    console.print(f"Probing project-scoped endpoints with project [bold]{project}[/bold]")
    has_tfvc = None
    try:
        details = client.get_json(f"projects/{projects[0]['id']}", {"includeCapabilities": "true"})
        has_tfvc = tfvc_capability(details)
        vc = ((details.get("capabilities") or {}).get("versioncontrol") or {}).get("sourceControlType", "?")
        console.print(f"Version control in {project}: {vc} (TFVC: {'yes' if has_tfvc else 'no' if has_tfvc is False else 'unknown'})")
    except AzdoHttpError:
        pass
    queues = []
    try:
        queues = client.get_list("distributedtask/queues", project=project)
    except AzdoHttpError:
        pass
    probes = [
        ("Project and Team (Read)", "projects", None, {"$top": 1}),
        ("Code (Read)", "git/repositories", project, None),
        ("Code (Read)", "policy/configurations", project, {"$top": 1}),
        ("Code (Read)", "tfvc/changesets", project, tfvc_probe_params(project)),
        ("Build (Read)", "build/definitions", project, {"$top": 1}),
        ("Build (Read)", "build/builds", project, {"$top": 1}),
        ("Build (Read)", "pipelines/checks/configurations", project,
         {"resourceType": "queue", "resourceId": queues[0]["id"]} if queues else None),
        ("Release (Read)", "release/definitions", project, {"$top": 1}),
        ("Variable Groups (Read)", "distributedtask/variablegroups", project, {"$top": 1}),
        ("Secure Files (Read)", "distributedtask/securefiles", project, None),
        ("Task Groups (Read)", "distributedtask/taskgroups", project, None),
        ("Service Connections (Read)", "serviceendpoint/endpoints", project, None),
        ("Agent Pools (Read)", "distributedtask/pools", None, None),
        ("Agent Pools (Read)", "distributedtask/queues", project, None),
        ("Environment (Read & manage)", "distributedtask/environments", project, {"$top": 1}),
        ("Deployment Groups (Read & manage)", "distributedtask/deploymentgroups", project, {"$top": 1}),
        ("Extensions (Read)", "extensionmanagement/installedextensions", None, None),
        ("Packaging (Read)", "packaging/feeds", None, None),
        ("Build/Code (Read) - service hooks", "hooks/subscriptions", None, None),
        ("Wiki (Read)", "wiki/wikis", project, None),
    ]
    table = Table(title="PAT coverage", show_lines=False)
    for col in ("PAT scope", "Endpoint", "Result"):
        table.add_column(col)
    for scope, path, proj, params in probes:
        if path == "pipelines/checks/configurations" and params is None:
            table.add_row(scope, path, "[yellow]skipped (no agent queue to probe)[/yellow]")
            continue
        try:
            client.get(path, params, project=proj)
            result = "[green]OK[/green]"
        except AzdoHttpError as exc:
            if path == "tfvc/changesets" and exc.status == 404:
                result = ("[yellow]404[/yellow] project has TFVC but this account cannot read it" if has_tfvc
                          else "[green]OK[/green] no TFVC repository (Git only) - nothing to convert")
            else:
                hint = "missing scope or permission" if exc.status in (401, 403) else exc.message[:80]
                result = f"[red]{exc.status}[/red] {hint}"
        table.add_row(scope, path, result)
    console.print(table)
    repos = client.get_list("git/repositories", project=project)
    repo = next((r for r in repos if r.get("remoteUrl") and not r.get("isDisabled")), None)
    if repo:
        ok, detail = run_git(cfg, pat, "ls-remote", "--heads", "--", repo["remoteUrl"], timeout=120)
        console.print(f"git ls-remote {repo['name']}: " + ("[green]OK[/green]" if ok else f"[red]failed[/red] {detail[-200:]}"))
    console.print(f"Read-only safeguards: REST = GET to allowlisted read endpoints on {client.host} only; "
                  f"git = {' / '.join(sorted(GIT_READ_COMMANDS))} only, pushes disabled, saved credentials ignored.")
    console.print("Tip: set azdo.api_version in config.yaml to the version shown above.")


def _run(cfg: Config, *, projects: list[str], all_projects: bool, deep: bool, refresh: bool, offline: bool,
         no_clone: bool, verbose: bool, label: str) -> None:
    try:
        rules = load_rules(cfg.rules_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Rules error:[/red] {exc}")
        raise typer.Exit(2) from None
    now = utcnow()
    store = RawStore(cfg.raw_dir)
    _check_cache_collection(cfg, store)
    client: AzdoClient | None = None
    if offline:
        _setup_logging(cfg, None, verbose)
        excluded = {n.lower() for n in cfg.scope.exclude_projects}
        names = [n for n in (projects or (store.scopes() if all_projects else [])) if n.lower() not in excluded]
        if not names:
            console.print("[red]--offline needs --project or --all with cached data[/red]")
            raise typer.Exit(2)
    else:
        _require_url(cfg)
        try:
            pat = get_pat(cfg.azdo)
        except ConfigError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(2) from None
        client = _client(cfg, pat)
        log_file = _setup_logging(cfg, client, verbose)
        if no_clone:
            cfg.collection.clone.enabled = False
        ctx = CollectContext(client=client, store=store, cfg=cfg, coverage=Coverage(), refresh=refresh, deep=deep, now=now,
                             progress=lambda msg: console.log(msg))
        try:
            selected = collect_all(ctx, requested=projects or None, all_projects=all_projects, pat=pat)
        except AzdoHttpError as exc:  # subclass of RuntimeError - must come first
            console.print(f"[red]Azure DevOps error:[/red] {exc}")
            raise typer.Exit(1) from None
        except (ValueError, RuntimeError) as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(1) from None
        names = [p["name"] for p in selected]
        console.log(f"collected {len(names)} project(s) with {client.stats.get('requests', 0)} API requests (log: {log_file})")
    provider = FileProvider(cfg, store, client)
    console.log("analyzing ...")
    result = run_analysis(cfg, rules, names, provider=provider, now=now)
    paths = write_reports(result, label, dossiers=deep)
    findings = result.all_findings()
    blockers = sum(1 for f in findings if f.severity == "blocker")
    table = Table(title="Result")
    for col in ("Project", "Mode", "Repos", "Pipelines", "Blockers", "High"):
        table.add_column(col)
    for p in result.projects:
        pf = p.all_findings()
        table.add_row(p.name, "deep" if p.deep else "inventory", str(len(p.repos)), str(len(p.pipelines)),
                      str(sum(1 for f in pf if f.severity == "blocker")), str(sum(1 for f in pf if f.severity == "high")))
    console.print(table)
    console.print(f"Workbook: [bold]{paths['workbook']}[/bold]")
    if paths["dossiers"]:
        console.print(f"Dossiers: {len(paths['dossiers'])} in {Path(paths['dir']) / 'dossiers'}")
    console.print(f"Project summaries: {', '.join(str(s) for s in paths['summaries'])}")
    console.print(f"Changes since last run: {paths['diff']}")
    if blockers:
        console.print(f"[yellow]{blockers} blocker finding(s) - see the Findings sheet.[/yellow]")


@app.command()
def inventory(
    all_projects: bool = typer.Option(False, "--all", help="All projects in the collection"),
    project: Optional[list[str]] = typer.Option(None, "--project", "-p", help="Limit to these projects (repeatable)"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch data even if cached"),
    offline: bool = typer.Option(False, "--offline", help="Use only cached data (no API calls)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config: Optional[Path] = ConfigOpt,
    collection: Optional[str] = CollectionOpt,
    output_dir: Optional[Path] = OutputDirOpt,
) -> None:
    """Fast metadata-only pass (no clones) for wave planning across projects."""
    cfg = _load(config, collection, output_dir)
    chosen = list(project or []) or ([] if all_projects else list(cfg.scope.projects))
    if not all_projects and not chosen:
        console.print("[red]Use --all, --project NAME, or list projects under scope.projects in config.yaml[/red]")
        raise typer.Exit(2)
    _run(cfg, projects=chosen, all_projects=all_projects, deep=False, refresh=refresh, offline=offline, no_clone=True,
         verbose=verbose, label="inventory")


@app.command()
def analyze(
    project: list[str] = typer.Option(..., "--project", "-p", help="Project(s) to analyse deeply (repeatable)"),
    refresh: bool = typer.Option(False, "--refresh", help="Re-fetch data and update clones"),
    offline: bool = typer.Option(False, "--offline", help="Use only cached data (no API calls)"),
    no_clone: bool = typer.Option(False, "--no-clone", help="Skip cloning (no content scan / YAML resolution from clones)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config: Optional[Path] = ConfigOpt,
    collection: Optional[str] = CollectionOpt,
    output_dir: Optional[Path] = OutputDirOpt,
) -> None:
    """Deep pass before a migration wave: full definitions, clones, YAML resolution, scan, dossiers."""
    cfg = _load(config, collection, output_dir)
    label = slugify(project[0]) if len(project) == 1 else "projects"
    _run(cfg, projects=project, all_projects=False, deep=True, refresh=refresh, offline=offline, no_clone=no_clone,
         verbose=verbose, label=label)


def main() -> None:  # pragma: no cover
    try:
        app()
    except KeyboardInterrupt:
        console.print("[yellow]interrupted[/yellow]")
        sys.exit(130)
