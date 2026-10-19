"""Collectors against a fake Azure DevOps Server (respx) backed by the sample data."""

from __future__ import annotations

import re
from pathlib import Path

import httpx
import respx

from azdo_analyzer.analyze import run_analysis
from azdo_analyzer.cache import RawStore
from azdo_analyzer.client import AzdoClient
from azdo_analyzer.collect import CollectContext, Coverage, collect_all
from azdo_analyzer.collect.content import FileProvider
from azdo_analyzer.config import Config
from tests.fixtures.sample_data import COLLECTION, NOW, PROJECT, REPO_FILES, SECURITY_TEAM, raw_files

BASE_PATH = "/DefaultCollection"


class FakeServer:
    """Serves sample raw files by REST path; records every request."""

    PREVIEW_ONLY = ("extensionmanagement/installedextensions", "distributedtask/securefiles")

    def __init__(self) -> None:
        self.files = raw_files()
        self.requests: list[httpx.Request] = []

    def data(self, *parts):
        return self.files.get(parts)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path[len(BASE_PATH):]
        params = request.url.params
        version = params.get("api-version", "")
        m = re.match(r"^(?:/(?P<project>[^/]+))?/_apis/(?P<route>.+)$", path)
        if not m:
            return httpx.Response(404, json={"message": "not found"})
        project, route = m.group("project"), m.group("route")
        if any(route.startswith(p) for p in self.PREVIEW_ONLY) and not version.endswith("-preview"):
            return httpx.Response(400, json={"typeKey": "VssInvalidPreviewVersionException",
                                             "message": "The -preview flag must be supplied in the api-version for such requests."})
        body = self.route(project, route, params)
        if isinstance(body, httpx.Response):
            return body
        if body is None:
            return httpx.Response(404, json={"message": f"{route} not found"})
        if isinstance(body, list):
            return httpx.Response(200, json={"count": len(body), "value": body})
        return httpx.Response(200, json=body)

    def route(self, project, route, params):  # noqa: C901 - a routing table is clearest here
        d = self.data
        if project is None:
            if route == "projects":
                return d("_org", "projects.json")
            if m := re.match(r"projects/([^/]+)$", route):
                return d("_org", "project_details", f"{m.group(1)}.json")
            if route == "distributedtask/tasks":
                return d("_org", "tasks.json")
            if route == "extensionmanagement/installedextensions":
                return d("_org", "extensions.json")
            if route == "distributedtask/pools":
                return d("_org", "pools.json")
            if m := re.match(r"distributedtask/pools/(\d+)/agents$", route):
                return d("_org", "agents", f"{m.group(1)}.json") or []
            if route == "packaging/feeds":
                return d("_org", "feeds.json")
            if route == "hooks/subscriptions":
                return d("_org", "hooks.json")
            if route == "connectionData":
                return {"authenticatedUser": {"providerDisplayName": "Reader Bot"}}
            if route == "identities":
                return [{"id": SECURITY_TEAM, "providerDisplayName": "[Contoso Retail]\\Security Team", "isContainer": True}]
            return None
        assert project == PROJECT, project
        p = PROJECT
        if route == "git/repositories":
            return d(p, "repos.json")
        if m := re.match(r"git/repositories/([^/]+)/stats/branches$", route):
            return d(p, "repo", m.group(1), "branch_stats.json")
        if m := re.match(r"git/repositories/([^/]+)/pullrequests$", route):
            prs = d(p, "repo", m.group(1), "open_prs.json") or []
            skip, top = int(params.get("$skip", 0)), int(params.get("$top", 100))
            return prs[skip:skip + top]
        if m := re.match(r"git/repositories/([^/]+)/items$", route):
            repo = next((r for r in d(p, "repos.json") if m.group(1) in (r["id"], r["name"])), None)
            path = params.get("path", "").lstrip("/")
            version = params.get("versionDescriptor.version")
            if repo and version and version not in ("main", "master"):
                cached = d(p, "files", repo["name"], version, *path.split("/"))
                content = cached["content"] if cached else None
            else:
                content = REPO_FILES.get(repo["name"] if repo else "", {}).get(path)
            return {"path": "/" + path, "content": content} if content is not None else None
        if m := re.match(r"git/repositories/([^/]+)/refs$", route):
            return d(p, "repo", m.group(1), "tags.json") or []
        if route == "policy/configurations":
            return d(p, "policy_configurations.json")
        if route == "tfvc/changesets":
            return []
        if route == "build/definitions":
            defs = d(p, "build_definitions.json")
            if params.get("continuationToken") == "page2":
                return defs[2:]
            return httpx.Response(200, json={"value": defs[:2]}, headers={"x-ms-continuationtoken": "page2"})
        if m := re.match(r"build/definitions/(\d+)$", route):
            return d(p, "build_definition", f"{m.group(1)}.json")
        if route == "build/builds":
            out = []
            for b in d(p, "builds.json"):
                full = dict(b)
                full["queue"] = {"id": b["queue"]["id"], "name": b["queue"]["name"], "pool": {"name": b["queue"]["pool"]}}
                full["requestedFor"] = {"displayName": b["requestedFor"]}
                out.append(full)
            return out
        if m := re.match(r"build/builds/(\d+)/timeline$", route):
            records = d(p, "timeline", f"{m.group(1)}.json")
            return {"records": records} if records is not None else None
        if route == "release/definitions":
            return d(p, "release_definitions.json")
        if m := re.match(r"release/definitions/(\d+)$", route):
            return d(p, "release_definition", f"{m.group(1)}.json")
        if route == "release/deployments":
            return d(p, "deployments.json")
        if route == "distributedtask/variablegroups":
            return d(p, "variable_groups.json")
        if route == "distributedtask/securefiles":
            return d(p, "secure_files.json")
        if route == "packaging/feeds":
            return d(p, "feeds.json")
        if route == "distributedtask/taskgroups":
            return d(p, "task_groups.json")
        if route == "wiki/wikis":
            return d(p, "wikis.json")
        if route == "serviceendpoint/endpoints":
            return d(p, "service_endpoints.json")
        if m := re.match(r"serviceendpoint/([^/]+)/executionhistory$", route):
            return d(p, "endpoint_history", f"{m.group(1)}.json") or []
        if route == "distributedtask/queues":
            return d(p, "queues.json")
        if route == "distributedtask/environments":
            return d(p, "environments.json")
        if m := re.match(r"distributedtask/environments/(\d+)$", route):
            return d(p, "environment", f"{m.group(1)}.json")
        if m := re.match(r"distributedtask/environments/(\d+)/environmentdeploymentrecords$", route):
            return d(p, "environment_deployments", f"{m.group(1)}.json") or []
        if route == "distributedtask/deploymentgroups":
            return httpx.Response(403, json={"message": "TF401444: needs Deployment Groups (Read & manage)"})
        if route == "pipelines/checks/configurations":
            return d(p, "checks", f"{params['resourceType']}_{params['resourceId']}.json") or []
        if m := re.match(r"pipelines/pipelinepermissions/([^/]+)/([^/]+)$", route):
            return d(p, "pipeline_permissions", f"{m.group(1)}_{m.group(2)}.json") or {"pipelines": []}
        return None


def test_collect_against_fake_server(tmp_path: Path, rules):
    server = FakeServer()
    cfg = Config(base_dir=tmp_path)
    cfg.azdo.collection_url = COLLECTION
    cfg.collection.clone.enabled = False
    store = RawStore(cfg.raw_dir)
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="azdo.contoso.local").mock(side_effect=server)
        client = AzdoClient(COLLECTION, "fake-pat-for-tests-1234567890", sleep=lambda _s: None)
        ctx = CollectContext(client=client, store=store, cfg=cfg, coverage=Coverage(), deep=True, now=NOW)
        selected = collect_all(ctx, requested=[PROJECT], all_projects=False, pat=None)

    assert [p["name"] for p in selected] == [PROJECT]
    assert {r.method for r in server.requests} == {"GET"}
    assert all("api-version" in r.url.params for r in server.requests)
    # paging fetched all four definitions across two pages; full GETs and timelines were collected
    assert len(store.read(PROJECT, "build_definitions.json")) == 4
    assert store.has(PROJECT, "build_definition", "12.json") and store.has(PROJECT, "timeline", "1104.json")
    assert store.read(PROJECT, "builds.json")[0]["queue"]["pool"] == "Linux-Docker"
    # preview-only routes succeeded after the automatic -preview retry
    assert store.read("_org", "extensions.json") and store.read(PROJECT, "secure_files.json")
    # a missing permission is a coverage gap, not a crash
    coverage = {(c["collector"], c["endpoint"]): c["status"] for c in store.read(PROJECT, "coverage.json")}
    assert coverage[("resources", "distributedtask/deploymentgroups")] == "FORBIDDEN"
    assert store.read(PROJECT, "identities.json")[SECURITY_TEAM]["displayName"].endswith("Security Team")
    assert store.read(PROJECT, "_meta.json")["depth"] == "deep"

    # the cache makes a second run free: no new requests without --refresh
    before = len(server.requests)
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="azdo.contoso.local").mock(side_effect=server)
        ctx2 = CollectContext(client=AzdoClient(COLLECTION, "fake-pat-for-tests-1234567890"), store=store, cfg=cfg,
                              coverage=Coverage(), deep=True, now=NOW)
        collect_all(ctx2, requested=[PROJECT], all_projects=False, pat=None)
    repeated = [r.url.path for r in server.requests[before:]]
    assert repeated and all(path.endswith("distributedtask/deploymentgroups") for path in repeated), repeated  # only the forbidden call is retried

    # analysis on the collected data (no clones: the YAML pipeline cannot be resolved offline and is flagged)
    result = run_analysis(cfg, rules, [PROJECT], provider=FileProvider(cfg, store, None), now=NOW)
    project = result.projects[0]
    assert len(project.pipelines) == 5
    legacy = next(r for r in project.pipelines.values() if r.pipeline.name == "legacy-web-CI")
    assert "VSBuild@1" in legacy.facts.tasks and legacy.facts.task_groups == ["Publish web", "Stamp version"]
    release = next(r for r in project.pipelines.values() if r.pipeline.kind == "classic_release")
    assert release.facts.deployment_groups == ["#3", "#4"]  # names unknown: deployment groups were forbidden
    yaml = next(r for r in project.pipelines.values() if r.pipeline.kind == "yaml")
    assert yaml.pipeline.flags.get("yaml_unresolved") and yaml.facts.unresolved_templates


def test_doctor_command(tmp_path: Path, monkeypatch):
    import subprocess

    from typer.testing import CliRunner

    from azdo_analyzer import cli

    server = FakeServer()
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"azdo:\n  collection_url: {COLLECTION}\noutput:\n  dir: out\n", encoding="utf-8")
    monkeypatch.setenv("AZDO_PAT", "fake-pat-for-tests-1234567890")
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs.get("env", {})))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="azdo.contoso.local").mock(side_effect=server)
        result = CliRunner().invoke(cli.app, ["doctor", "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    assert "Reader Bot" in result.output and "PAT coverage" in result.output
    assert {r.method for r in server.requests} == {"GET"}
    cmd, env = calls[0]
    assert cmd[1] == "ls-remote" and "fake-pat" not in " ".join(cmd)  # PAT only travels in GIT_CONFIG_* env vars
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"


def test_cli_analyze_online_without_clones(tmp_path: Path, monkeypatch):
    from typer.testing import CliRunner

    from azdo_analyzer import cli

    server = FakeServer()
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"azdo:\n  collection_url: {COLLECTION}\noutput:\n  dir: out\n", encoding="utf-8")
    monkeypatch.setenv("AZDO_PAT", "fake-pat-for-tests-1234567890")
    with respx.mock(assert_all_called=False) as mock:
        mock.route(host="azdo.contoso.local").mock(side_effect=server)
        result = CliRunner().invoke(cli.app, ["analyze", "-p", PROJECT, "--no-clone", "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    assert {r.method for r in server.requests} == {"GET"}
    items = [r for r in server.requests if r.url.path.endswith("/items")]
    assert items, "YAML files should be read through the items API when repos are not cloned"
    dossier = next((tmp_path / "out" / "reports").glob("*/dossiers/Contoso Retail/payments-api.md")).read_text()
    assert "Maven@3" in dossier and "SonarQubePrepare@5" in dossier  # templates resolved at refs/tags/v2 via the API
    assert "not scanned" in dossier  # no clone -> no repo content scan
