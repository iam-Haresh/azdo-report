"""CLI wiring: offline runs over the sample cache, config validation."""

from __future__ import annotations

import re

import pytest
from typer.testing import CliRunner

from azdo_analyzer.cli import app
from azdo_analyzer.config import PROJECT_ROOT, Config, ConfigError, load_config
from tests.fixtures.sample_data import COLLECTION, PROJECT, build_sample

runner = CliRunner()


def _config(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"azdo:\n  collection_url: {COLLECTION}\noutput:\n  dir: out\n", encoding="utf-8")
    build_sample(tmp_path / "out")
    return cfg_file


def test_example_config_is_valid():
    cfg = load_config(PROJECT_ROOT / "config.example.yaml")
    assert cfg.azdo.api_version == "7.0" and cfg.analysis.gitlab_tier == "premium"


def test_unknown_config_key_is_rejected(tmp_path):
    bad = tmp_path / "config.yaml"
    bad.write_text("azdo:\n  colection_url: x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="azdo.colection_url"):
        load_config(bad)


def test_analyze_offline(tmp_path):
    cfg_file = _config(tmp_path)
    result = runner.invoke(app, ["analyze", "--project", PROJECT, "--offline", "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    reports = list((tmp_path / "out" / "reports").glob("*/azdo-analysis-contoso-retail.xlsx"))
    assert reports, result.output
    assert list((tmp_path / "out" / "reports").glob("*/dossiers/Contoso Retail/legacy-web.md"))


def test_inventory_offline_all(tmp_path):
    cfg_file = _config(tmp_path)
    result = runner.invoke(app, ["inventory", "--all", "--offline", "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    assert list((tmp_path / "out" / "reports").glob("*/azdo-analysis-inventory.xlsx"))
    # the Result table counts build/YAML pipelines and classic releases separately
    assert re.search(r"Project\W+Mode\W+Repos\W+Pipelines\W+Releases\W+Blockers\W+High", result.output), result.output
    assert re.search(r"Contoso Retail\W+\w+\W+5\W+4\W+1\W", result.output), result.output


def test_inventory_requires_scope(tmp_path):
    result = runner.invoke(app, ["inventory", "--config", str(_config(tmp_path))])
    assert result.exit_code == 2


def test_inventory_uses_scope_projects_and_exclusions(tmp_path):
    cfg_file = _config(tmp_path)
    cfg_file.write_text(cfg_file.read_text() + f"scope:\n  projects: ['{PROJECT}']\n", encoding="utf-8")
    result = runner.invoke(app, ["inventory", "--offline", "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    assert list((tmp_path / "out" / "reports").glob("*/azdo-analysis-inventory.xlsx"))
    cfg_file.write_text(cfg_file.read_text() + f"  exclude_projects: ['{PROJECT.lower()}']\n", encoding="utf-8")
    result = runner.invoke(app, ["inventory", "--all", "--offline", "--config", str(cfg_file)])
    assert result.exit_code == 2  # the only cached project is excluded


def test_missing_pat_is_reported(tmp_path, monkeypatch):
    monkeypatch.delenv("AZDO_PAT", raising=False)
    result = runner.invoke(app, ["analyze", "-p", PROJECT, "--config", str(_config(tmp_path))])
    assert result.exit_code == 2 and "No PAT found" in result.output


def test_tls_verification_is_off_for_api_and_git(monkeypatch):
    import warnings

    import certifi

    from azdo_analyzer import cli
    from azdo_analyzer.client import AzdoClient
    from azdo_analyzer.collect.content import git_env

    for cfg in (Config(), load_config(PROJECT_ROOT / "config.example.yaml")):
        assert cfg.tls_verify is False
        env = git_env("pat", cfg)
        settings = {env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"] for i in range(int(env["GIT_CONFIG_COUNT"]))}
        assert settings["http.sslVerify"] == "false"
        captured = {}
        monkeypatch.setattr(cli, "AzdoClient", lambda *a, _seen=captured, **kw: _seen.update(kw))
        cfg.azdo.collection_url = COLLECTION
        cli._client(cfg, "pat")
        assert captured["verify"] is False
    # opting back in with a CA bundle builds an SSL context (no httpx deprecation warning)
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        AzdoClient(COLLECTION, "pat", verify=certifi.where()).close()


def test_example_config_documents_every_setting_with_default_values():
    import dataclasses

    example_path = PROJECT_ROOT / "config.example.yaml"
    text = example_path.read_text(encoding="utf-8")
    example, defaults = load_config(example_path), Config()
    for section in ("azdo", "scope", "collection", "analysis", "output"):
        got, want = dataclasses.asdict(getattr(example, section)), dataclasses.asdict(getattr(defaults, section))
        got.pop("collection_url", None), want.pop("collection_url", None)
        assert got == want, section  # the example shows the real defaults

    def names(obj):
        for f in dataclasses.fields(obj):
            if f.name == "base_dir":
                continue
            yield f.name
            value = getattr(obj, f.name)
            if dataclasses.is_dataclass(value):
                yield from names(value)

    undocumented = [n for n in names(defaults) if f"# {n}" not in text and f"{n}:" not in text]
    assert undocumented == []
    for n in names(defaults):  # every setting has an explanation comment with an example
        if n in ("azdo", "scope", "collection", "analysis", "output", "clone"):
            continue
        assert f"# {n}" in text, n
    assert text.count("Example") >= 25


def test_resolve_collection():
    from azdo_analyzer.config import resolve_collection

    assert resolve_collection("https://azdo.example.com/Other/", "") == "https://azdo.example.com/Other"
    assert resolve_collection("Payments", "https://azdo.example.com/DefaultCollection") == "https://azdo.example.com/Payments"
    assert resolve_collection("Payments", "https://tfs.example.com/tfs/DefaultCollection/") == "https://tfs.example.com/tfs/Payments"
    assert resolve_collection("My Coll", "https://azdo.example.com") == "https://azdo.example.com/My%20Coll"
    with pytest.raises(ConfigError, match="collection name"):
        resolve_collection("Payments", "")


def test_collection_option_and_cache_guard(tmp_path):
    cfg_file = _config(tmp_path)
    same = runner.invoke(app, ["analyze", "-p", PROJECT, "--offline", "--collection", "DefaultCollection", "--config", str(cfg_file)])
    assert same.exit_code == 0, same.output  # a name resolves against the configured server -> same collection
    other = runner.invoke(app, ["analyze", "-p", PROJECT, "--offline", "--collection", "https://other.example/Coll",
                                "--config", str(cfg_file)])
    assert other.exit_code == 2 and "holds data from" in other.output  # never mix two collections in one cache


def test_output_dir_option(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(f"azdo:\n  collection_url: {COLLECTION}\n", encoding="utf-8")
    build_sample(tmp_path / "alt")
    result = runner.invoke(app, ["inventory", "--all", "--offline", "--output-dir", str(tmp_path / "alt"), "--config", str(cfg_file)])
    assert result.exit_code == 0, result.output
    assert list((tmp_path / "alt" / "reports").glob("*/azdo-analysis-inventory.xlsx"))
    assert not (tmp_path / "out").exists()


def test_gitlab_ci_file():
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor("!reference", lambda loader, node: loader.construct_sequence(node))
    ci = yaml.load((PROJECT_ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"), Loader=Loader)  # noqa: S506
    assert ci["default"]["image"].startswith("python:3.")
    assert set(ci["stages"]) == {"test", "analyze"}
    assert ci["test"]["script"] == ["python -m pytest -q"]
    for job, command in (("inventory", "azdo-analyzer inventory --all"), ("analyze", "azdo-analyzer analyze --project")):
        assert ci[job]["extends"] == ".azdo-job" and ci[job]["script"][0] == [".azdo-prepare", "script"]
        assert any(line.startswith(command) and "--collection" in line for line in ci[job]["script"][1:])
    assert ci[".azdo-job"]["artifacts"]["paths"] == ["out/reports/", "out/logs/"]
    assert "AZDO_PAT" not in ci["variables"]  # the PAT only lives in masked CI/CD settings
