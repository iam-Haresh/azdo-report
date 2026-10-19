from __future__ import annotations

from pathlib import Path

import pytest

from azdo_analyzer.cache import RawStore
from azdo_analyzer.collect.content import FileProvider
from azdo_analyzer.config import PROJECT_ROOT, Config
from azdo_analyzer.rules import Rules, load_rules
from tests.fixtures.sample_data import COLLECTION, build_sample


@pytest.fixture(scope="session")
def rules() -> Rules:
    return load_rules(PROJECT_ROOT / "rules")


@pytest.fixture()
def sample_cfg(tmp_path: Path) -> Config:
    cfg = Config(base_dir=tmp_path)
    cfg.azdo.collection_url = COLLECTION
    build_sample(cfg.out_dir)
    return cfg


@pytest.fixture()
def provider(sample_cfg: Config) -> FileProvider:
    return FileProvider(sample_cfg, RawStore(sample_cfg.raw_dir), None)
