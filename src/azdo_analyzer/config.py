"""Configuration loading (YAML -> nested dataclasses) and PAT retrieval."""

from __future__ import annotations

import dataclasses
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ConfigError(ValueError):
    pass


@dataclass
class AzdoSettings:
    collection_url: str = ""
    api_version: str = "7.0"
    pat_env: str = "AZDO_PAT"
    keychain_service: str | None = None
    ca_bundle: str | None = None
    verify_tls: bool = True
    timeout_seconds: float = 60.0
    concurrency: int = 6
    max_retries: int = 5


@dataclass
class ScopeSettings:
    projects: list[str] = field(default_factory=list)
    exclude_projects: list[str] = field(default_factory=list)


@dataclass
class CloneSettings:
    enabled: bool = True
    max_repo_mb: int = 2048
    concurrency: int = 4
    git_binary: str = "git"


@dataclass
class CollectionSettings:
    history_days: int = 180
    timelines_for_active_only: bool = True
    clone: CloneSettings = field(default_factory=CloneSettings)


@dataclass
class AnalysisSettings:
    active_days: int = 90
    dormant_days: int = 365
    redact_values: bool = False
    gitlab_tier: str = "premium"
    gitlab_repo_limit_gb: float = 10.0
    internal_host_patterns: list[str] = field(
        default_factory=lambda: [
            r"\.local$",
            r"\.corp\.",
            r"\.internal$",
            r"\.lan$",
            r"^10\.",
            r"^192\.168\.",
            r"^172\.(1[6-9]|2[0-9]|3[01])\.",
            r"^[^.]+$",
        ]
    )
    secret_name_pattern: str = (
        r"(?i)(pass(word)?|pwd|secret|token|api[_.-]?key|private[_.-]?key|"
        r"connection[_.-]?string|credential|client[_.-]?secret)"
    )


@dataclass
class OutputSettings:
    dir: str = "out"
    overrides_file: str = "overrides.yaml"


@dataclass
class Config:
    azdo: AzdoSettings = field(default_factory=AzdoSettings)
    scope: ScopeSettings = field(default_factory=ScopeSettings)
    collection: CollectionSettings = field(default_factory=CollectionSettings)
    analysis: AnalysisSettings = field(default_factory=AnalysisSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    rules_dir: str | None = None
    templates_dir: str | None = None
    base_dir: Path = field(default=Path("."), repr=False)

    def resolve(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (self.base_dir / path).resolve()

    @property
    def out_dir(self) -> Path:
        return self.resolve(self.output.dir)

    @property
    def raw_dir(self) -> Path:
        return self.out_dir / "raw"

    @property
    def repos_dir(self) -> Path:
        return self.out_dir / "repos"

    @property
    def model_dir(self) -> Path:
        return self.out_dir / "model"

    @property
    def reports_dir(self) -> Path:
        return self.out_dir / "reports"

    @property
    def rules_path(self) -> Path:
        return self.resolve(self.rules_dir) if self.rules_dir else PROJECT_ROOT / "rules"

    @property
    def templates_path(self) -> Path:
        return self.resolve(self.templates_dir) if self.templates_dir else PROJECT_ROOT / "templates"

    @property
    def overrides_path(self) -> Path:
        return self.resolve(self.output.overrides_file)

    @property
    def tls_verify(self) -> bool | str:
        if not self.azdo.verify_tls:
            return False
        if self.azdo.ca_bundle:
            return str(self.resolve(self.azdo.ca_bundle))
        return True


def _build(cls: type, data: dict[str, Any] | None, where: str) -> Any:
    data = data or {}
    if not isinstance(data, dict):
        raise ConfigError(f"'{where}' must be a mapping")
    kwargs: dict[str, Any] = {}
    fields = {f.name: f for f in dataclasses.fields(cls) if f.name != "base_dir"}
    for key, value in data.items():
        if key not in fields:
            raise ConfigError(f"Unknown config key '{where}.{key}'" if where else f"Unknown config key '{key}'")
        f = fields[key]
        default = f.default_factory() if f.default_factory is not dataclasses.MISSING else f.default
        if dataclasses.is_dataclass(default):
            kwargs[key] = _build(type(default), value, f"{where}.{key}" if where else key)
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: Path | None) -> Config:
    """Load config YAML; without a file, defaults plus env vars are used."""
    if path is None:
        candidate = Path("config.yaml")
        path = candidate if candidate.exists() else None
    if path is None:
        cfg = Config(base_dir=Path.cwd())
    else:
        path = path.expanduser().resolve()
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        cfg = _build(Config, data, "")
        cfg.base_dir = path.parent
    env_url = os.environ.get("AZDO_COLLECTION_URL")
    if env_url:
        cfg.azdo.collection_url = env_url
    cfg.azdo.collection_url = cfg.azdo.collection_url.rstrip("/")
    if cfg.analysis.gitlab_tier not in ("premium", "ultimate", "free"):
        raise ConfigError("analysis.gitlab_tier must be one of: free, premium, ultimate")
    return cfg


def get_pat(settings: AzdoSettings) -> str:
    """Read the PAT from the environment, falling back to the macOS Keychain."""
    pat = os.environ.get(settings.pat_env, "").strip()
    if pat:
        return pat
    if settings.keychain_service:
        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", settings.keychain_service, "-w"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is not None and result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise ConfigError(
        f"No PAT found. Set the {settings.pat_env} environment variable"
        + (f" or add a Keychain item for service '{settings.keychain_service}'" if settings.keychain_service else "")
        + "."
    )
