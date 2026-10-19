"""The tool can only read: REST is GET-only to allowlisted read endpoints, git is clone/ls-remote only."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import httpx
import pytest
import respx

from azdo_analyzer.cache import RawStore
from azdo_analyzer.client import READ_ENDPOINTS, AzdoClient, ReadOnlyViolation
from azdo_analyzer.collect.base import CollectContext, Coverage
from azdo_analyzer.collect.content import PUSH_DISABLED_URL, clone_repos, git_command, git_env, run_git
from azdo_analyzer.config import PROJECT_ROOT, Config

BASE = "https://azdo.example.local/DefaultCollection"
SRC = PROJECT_ROOT / "src" / "azdo_analyzer"


def client() -> AzdoClient:
    return AzdoClient(BASE, "pat-value-for-tests-123456", sleep=lambda _s: None)


# ------------------------------------------------------------------ REST
@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
def test_every_write_verb_is_refused_before_sending(method):
    c = client()
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route(host="azdo.example.local").mock(return_value=httpx.Response(200, json={}))
        with pytest.raises(ReadOnlyViolation):
            c.request(method, f"{BASE}/_apis/projects")
        with pytest.raises(ReadOnlyViolation):
            c._http.request(method, f"{BASE}/_apis/projects")  # bypassing AzdoClient still hits the httpx hook
        assert route.call_count == 0


@pytest.mark.parametrize("url", [
    f"{BASE}/P/_apis/git/repositories/r/pushes",          # a GET, but not an endpoint this tool uses
    f"{BASE}/P/_apis/build/builds/1/logs",
    f"{BASE}/_apis/tokens/pats",
    f"{BASE}/P/_git/repo/info/refs",                       # not a REST API path at all
    "https://other-host.example/DefaultCollection/_apis/projects",
])
def test_only_allowlisted_read_endpoints_on_the_collection_host(url):
    with pytest.raises(ReadOnlyViolation):
        client().check_read_only("GET", url)


def test_every_endpoint_the_tool_uses_is_allowlisted():
    samples = [
        "connectionData", "projects", "projects/6ce954b1", "identities", "hooks/subscriptions",
        "extensionmanagement/installedextensions", "packaging/feeds", "git/repositories",
        "git/repositories/r1/stats/branches", "git/repositories/r1/pullrequests", "git/repositories/r1/refs",
        "git/repositories/My Repo/items", "policy/configurations", "tfvc/changesets", "build/definitions",
        "build/definitions/12", "build/builds", "build/builds/1104/timeline", "release/definitions",
        "release/definitions/5", "release/deployments", "distributedtask/tasks", "distributedtask/pools",
        "distributedtask/pools/1/agents", "distributedtask/queues", "distributedtask/variablegroups",
        "distributedtask/securefiles", "distributedtask/taskgroups", "distributedtask/environments",
        "distributedtask/environments/2", "distributedtask/environments/2/environmentdeploymentrecords",
        "distributedtask/deploymentgroups", "wiki/wikis", "serviceendpoint/endpoints",
        "serviceendpoint/e1/executionhistory", "pipelines/checks/configurations",
        "pipelines/pipelinepermissions/endpoint/e1",
    ]
    c = client()
    for route in samples:
        c.check_read_only("GET", f"{BASE}/Contoso%20Retail/_apis/{route}")
    assert len(READ_ENDPOINTS) <= 30  # the list is short enough to review by eye


def test_no_other_module_talks_to_the_network():
    network_libs = re.compile(r"^\s*(?:import|from)\s+(?:requests|urllib\.request|urllib3|http\.client|socket|aiohttp|ftplib|smtplib)\b", re.M)
    offenders = []
    for py in SRC.rglob("*.py"):
        rel, text = py.relative_to(SRC).as_posix(), py.read_text(encoding="utf-8")
        if network_libs.search(text) or ("httpx" in text and rel != "client.py"):
            offenders.append(rel)
    assert offenders == []


def test_only_known_modules_run_external_commands():
    users = {py.relative_to(SRC).as_posix() for py in SRC.rglob("*.py") if re.search(r"\bsubprocess\.", py.read_text(encoding="utf-8"))}
    assert users == {"collect/content.py", "config.py"}  # git wrapper, and the macOS Keychain lookup (read)
    assert "subprocess.run(cmd" in (SRC / "collect/content.py").read_text(encoding="utf-8")
    keychain = (SRC / "config.py").read_text(encoding="utf-8")
    assert '"find-generic-password"' in keychain and "add-generic-password" not in keychain


# ------------------------------------------------------------------ git
@pytest.mark.parametrize("sub", ["push", "commit", "fetch", "pull", "reset", "clean", "config", "remote", "tag", "lfs", "gc"])
def test_git_wrapper_refuses_everything_but_clone_and_ls_remote(sub):
    with pytest.raises(ReadOnlyViolation):
        git_command("git", sub)
    assert git_command("git", "ls-remote", "--heads", "--", "u") == ["git", "ls-remote", "--heads", "--", "u"]


def test_git_environment_uses_only_the_pat_and_cannot_push():
    env = git_env("the-pat", Config())
    settings = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(int(env["GIT_CONFIG_COUNT"]))}
    assert settings["credential.helper"] == ""  # saved credentials are never used
    assert settings["remote.origin.pushurl"] == PUSH_DISABLED_URL
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def _git(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False,
                          env={"GIT_CONFIG_NOSYSTEM": "1", "HOME": str(cwd or Path.cwd()), "PATH": "/usr/bin:/bin:/opt/homebrew/bin"})


def test_real_clone_cannot_push_back(tmp_path: Path):
    # a local "server" repository with one commit
    work, bare = tmp_path / "work", tmp_path / "server.git"
    work.mkdir()
    assert _git("init", "-q", "-b", "main", cwd=work).returncode == 0
    (work / "README.md").write_text("hello\n")
    _git("add", ".", cwd=work)
    assert _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init", cwd=work).returncode == 0
    assert _git("clone", "-q", "--bare", str(work), str(bare), cwd=tmp_path).returncode == 0
    before = _git("rev-parse", "main", cwd=bare).stdout.strip()

    cfg = Config(base_dir=tmp_path)
    cfg.azdo.collection_url = BASE
    ctx = CollectContext(client=client(), store=RawStore(cfg.raw_dir), cfg=cfg, coverage=Coverage())
    repo = {"id": "r1", "name": "demo", "defaultBranch": "refs/heads/main", "size": 1024, "remoteUrl": bare.as_uri()}
    assert clone_repos(ctx, {"name": "Proj"}, [repo], "pat-value-for-tests-123456") == {"r1": "cloned"}
    clone = cfg.repos_dir / "Proj" / "demo"
    assert (clone / "README.md").read_text() == "hello\n"
    git_config = (clone / ".git" / "config").read_text()
    assert PUSH_DISABLED_URL in git_config and "pat-value" not in git_config

    # even a manual push from the clone cannot reach the server
    (clone / "evil.txt").write_text("x")
    _git("add", ".", cwd=clone)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "evil", cwd=clone)
    push = _git("push", "origin", "HEAD:main", cwd=clone)
    assert push.returncode != 0 and "read-only" in push.stderr
    assert _git("rev-parse", "main", cwd=bare).stdout.strip() == before  # server unchanged

    # and the tool's own git runner refuses to even try
    with pytest.raises(ReadOnlyViolation):
        run_git(cfg, "pat", "push", "origin")
