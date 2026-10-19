"""CLI wiring: offline runs over the sample cache, config validation."""

from __future__ import annotations

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


def test_inventory_requires_scope(tmp_path):
    result = runner.invoke(app, ["inventory", "--config", str(_config(tmp_path))])
    assert result.exit_code == 2


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
