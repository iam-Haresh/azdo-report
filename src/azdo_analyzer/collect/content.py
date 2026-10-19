"""Repository content: shallow clones, tree listings and template file fetches.

git is read-only by construction:
* only ``git clone`` and ``git ls-remote`` can be run (``git_command`` refuses anything else),
* every clone gets an unreachable push URL, so a push from it can never reach the server,
* saved git credentials are ignored (``credential.helper`` reset) - only the read-only PAT is used,
* the PAT reaches git only through GIT_CONFIG_* environment variables, never in a clone URL,
  .git/config or the process list.
"""

from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit, urlunsplit

from azdo_analyzer.cache import RawStore, safe_name
from azdo_analyzer.client import AzdoClient, AzdoHttpError, ReadOnlyViolation, Redactor
from azdo_analyzer.collect.base import CollectContext
from azdo_analyzer.config import Config
from azdo_analyzer.util import branch_name

GIT_READ_COMMANDS = frozenset({"clone", "ls-remote"})
PUSH_DISABLED_URL = "read-only://pushing-is-disabled-by-azdo-analyzer"
_REMOTE_SCHEMES = ("https", "http", "file")
SKIP_DIRS = {".git", "node_modules", "bin", "obj", "packages", "vendor", "dist", "target", ".gradle", ".idea", ".vs", "__pycache__", ".venv"}


def git_env(pat: str, cfg: Config) -> dict[str, str]:
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    entries = [
        ("http.extraHeader", f"Authorization: Basic {token}"),
        ("credential.helper", ""),  # ignore saved credentials: only the read-only PAT is ever used
        ("remote.origin.pushurl", PUSH_DISABLED_URL),  # a push from this process could never reach the server
    ]
    verify = cfg.tls_verify
    if verify is False:
        entries.append(("http.sslVerify", "false"))
    elif isinstance(verify, str):
        entries.append(("http.sslCAInfo", verify))
    env = dict(os.environ)
    env["GIT_CONFIG_COUNT"] = str(len(entries))
    for i, (key, value) in enumerate(entries):
        env[f"GIT_CONFIG_KEY_{i}"] = key
        env[f"GIT_CONFIG_VALUE_{i}"] = value
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_LFS_SKIP_SMUDGE": "1", "GCM_INTERACTIVE": "never"})
    return env


def git_command(git: str, subcommand: str, *args: str) -> list[str]:
    """Build a git command line. Only read-only subcommands can be built."""
    if subcommand not in GIT_READ_COMMANDS:
        raise ReadOnlyViolation(f"git {subcommand} is not allowed: azdo-analyzer only runs {', '.join(sorted(GIT_READ_COMMANDS))}")
    return [git, subcommand, *args]


def run_git(cfg: Config, pat: str, subcommand: str, *args: str, timeout: int = 1800) -> tuple[bool, str]:
    """Run a read-only git command with the PAT injected via environment; returns (ok, redacted stderr)."""
    cmd = git_command(cfg.collection.clone.git_binary, subcommand, *args)
    redact = Redactor([pat, base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")])
    try:
        result = subprocess.run(cmd, env=git_env(pat, cfg), capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, redact(str(exc))
    return result.returncode == 0, redact(result.stderr.strip())[-400:]


def _remove_clone(cfg: Config, path: Path) -> None:
    """Delete one cached clone - refuses anything outside out/repos."""
    root = cfg.repos_dir.resolve()
    target = path.resolve()
    if target == root or root not in target.parents:
        raise RuntimeError(f"Refusing to delete {target}: it is not inside {root}")
    shutil.rmtree(target, ignore_errors=True)


def _strip_userinfo(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))


def repo_dir(cfg: Config, project: str, repo_name: str) -> Path:
    return cfg.repos_dir / safe_name(project) / safe_name(repo_name)


def clone_repos(ctx: CollectContext, project: dict, repos: list[dict], pat: str) -> dict[str, str]:
    """Shallow-clone each repo's default branch; very large repos get a tree listing instead."""
    p = project["name"]
    settings = ctx.cfg.collection.clone
    c = ctx.client

    def one(repo: dict) -> tuple[str, str]:
        rid, name = repo["id"], repo["name"]
        branch = branch_name(repo.get("defaultBranch"))
        if repo.get("isDisabled"):
            return rid, "disabled"
        if not branch or not repo.get("size"):
            return rid, "empty"
        if (repo.get("size") or 0) / (1024 * 1024) > settings.max_repo_mb:
            ctx.fetch(
                (p, "repo", rid, "tree.json"),
                lambda: [
                    i.get("path")
                    for i in c.get_list(
                        f"git/repositories/{rid}/items",
                        {"recursionLevel": "Full", "versionDescriptor.version": branch, "versionDescriptor.versionType": "branch"},
                        project=p,
                    )
                    if not i.get("isFolder")
                ],
                scope=p,
                collector="content",
                endpoint="git/repositories/{id}/items (tree)",
            )
            return rid, "tree-only"
        dest = repo_dir(ctx.cfg, p, name)
        if (dest / ".git").exists() and not ctx.refresh:
            return rid, "cached"
        url = _strip_userinfo(repo.get("remoteUrl") or "")
        if urlsplit(url).scheme not in _REMOTE_SCHEMES:
            ctx.coverage.record(p, "content", "git clone", "ERROR", message=f"{name}: unexpected remote URL {url!r}")
            return rid, "error"
        if dest.exists():  # --refresh re-clones (keeps git to clone/ls-remote only)
            _remove_clone(ctx.cfg, dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        ok, err = run_git(ctx.cfg, pat, "clone", "--quiet", "--depth", "1", "--single-branch", "--no-tags", "--branch", branch,
                          "--config", f"remote.origin.pushurl={PUSH_DISABLED_URL}", "--", url, str(dest))
        if not ok:
            if dest.exists():
                _remove_clone(ctx.cfg, dest)
            ctx.coverage.record(p, "content", "git clone", "ERROR", message=f"{name}: {err}")
            return rid, "error"
        ctx.coverage.record(p, "content", "git clone", "OK", 1)
        return rid, "cloned"

    if c is None:
        return {}
    ctx.progress(f"{p}: cloning {len(repos)} repositories (depth 1)")
    statuses = dict(ctx.pmap(one, repos, workers=settings.concurrency))
    ctx.store.write(statuses, p, "clone_status.json")
    return statuses


def _version_descriptor(ref: str) -> tuple[str, str]:
    if ref.startswith("refs/tags/"):
        return ref[len("refs/tags/"):], "tag"
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):], "branch"
    if len(ref) == 40 and all(ch in "0123456789abcdef" for ch in ref.lower()):
        return ref, "commit"
    return ref, "branch"


class FileProvider:
    """Reads files from local clones, the raw cache, or (online) the items API."""

    def __init__(self, cfg: Config, store: RawStore, client: AzdoClient | None = None):
        self.cfg = cfg
        self.store = store
        self.client = client
        self._repos: dict[str, dict[str, dict]] = {}
        self.api_fetches = 0

    def repo_info(self, project: str, repo: str) -> dict | None:
        key = project.lower()
        if key not in self._repos:
            index: dict[str, dict] = {}
            for r in self.store.read(project, "repos.json", default=[]) or []:
                index[r["name"].lower()] = r
                index[r["id"].lower()] = r
            self._repos[key] = index
        return self._repos[key].get(repo.lower())

    def get(self, project: str, repo: str, ref: str | None, path: str) -> str | None:
        path = path.lstrip("/")
        info = self.repo_info(project, repo)
        repo_name = info["name"] if info else repo
        default = branch_name(info.get("defaultBranch")) if info else None
        wanted = branch_name(ref) if ref else None
        if wanted is None or wanted == default:
            local = repo_dir(self.cfg, project, repo_name) / path
            if local.is_file():
                return local.read_text(encoding="utf-8", errors="replace")
        ref_key = wanted or "default"
        parts = (project, "files", repo_name, ref_key, *path.split("/"))
        if self.store.has(*parts):
            cached = self.store.read(*parts)
            return cached.get("content") if isinstance(cached, dict) else None
        if self.client is None:
            return None
        params: dict[str, Any] = {"path": "/" + path, "includeContent": "true", "$format": "json"}
        version, vtype = _version_descriptor(ref) if ref else (default, "branch")
        if version:
            params["versionDescriptor.version"] = version
            params["versionDescriptor.versionType"] = vtype
        repo_key = info["id"] if info else repo
        try:
            data = self.client.get_json(f"git/repositories/{repo_key}/items", params, project=project)
        except AzdoHttpError:
            self.store.write({"content": None}, *parts)
            return None
        self.api_fetches += 1
        content = data.get("content") if isinstance(data, dict) else None
        self.store.write({"content": content}, *parts)
        return content


class RepoContent:
    """Uniform access to a repo's files from a clone or (large repos) a tree listing."""

    def __init__(self, cfg: Config, store: RawStore, provider: FileProvider, project: str, repo: dict):
        self.project = project
        self.repo = repo
        self.dir = repo_dir(cfg, project, repo["name"])
        self.tree: list[str] | None = store.read(project, "repo", repo["id"], "tree.json")
        self.provider = provider
        self._files: list[str] | None = None

    @property
    def available(self) -> bool:
        return self.dir.is_dir() or bool(self.tree)

    @property
    def source(self) -> str:
        if self.dir.is_dir():
            return "clone"
        return "tree" if self.tree else "none"

    def files(self) -> list[str]:
        if self._files is None:
            if self.dir.is_dir():
                self._files = sorted(self._walk())
            elif self.tree:
                self._files = sorted(p.lstrip("/") for p in self.tree if p)
            else:
                self._files = []
        return self._files

    def _walk(self) -> Iterator[str]:
        for root, dirs, files in os.walk(self.dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            rel_root = Path(root).relative_to(self.dir)
            for name in files:
                yield (rel_root / name).as_posix()

    def size(self, rel: str) -> int | None:
        if self.dir.is_dir():
            try:
                return (self.dir / rel).stat().st_size
            except OSError:
                return None
        return None

    def read(self, rel: str, max_bytes: int = 512 * 1024) -> str | None:
        if self.dir.is_dir():
            target = self.dir / rel
            try:
                if target.stat().st_size > max_bytes:
                    return None
                return target.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None
        if self.tree:
            return self.provider.get(self.project, self.repo["name"], None, rel)
        return None
