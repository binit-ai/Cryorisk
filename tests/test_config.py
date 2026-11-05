import os
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from cryorisk.config import CONFIG_DIR, GlacierSet, ProjectConfig, load_glaciers, load_project


def test_repo_configs_load():
    cfg = load_project()
    assert cfg.crs == "EPSG:32645"
    assert cfg.year_list[0] == cfg.years[0] and cfg.year_list[-1] == cfg.years[1]
    assert cfg.paths.data.is_absolute()

    gset = load_glaciers()
    assert {g.split for g in gset.glaciers} == {"train", "val", "test"}
    assert gset.get("ngozumpa").rgi_id == "RGI2000-v7.0-G-15-08305"


def test_glacier_slug_and_lookup():
    gset = load_glaciers()
    g = gset.get("imja_lhotse_shar")
    assert g.name == "Imja-Lhotse Shar"
    with pytest.raises(KeyError):
        gset.get("not-a-glacier")


def test_test_split_disjoint_from_train():
    gset = load_glaciers()
    train = {g.name for g in gset.by_split("train")}
    test = {g.name for g in gset.by_split("test")}
    assert train and test and not train & test


def _base_project() -> dict:
    return yaml.safe_load((Path(CONFIG_DIR) / "project.yaml").read_text())


def test_bad_bbox_rejected():
    d = _base_project()
    d["region_bbox"] = [87.0, 27.8, 86.5, 28.1]  # west > east
    with pytest.raises(ValidationError):
        ProjectConfig(**d)


def test_bad_season_rejected():
    d = _base_project()
    d["season"]["start"] = "13-01"
    with pytest.raises(ValidationError):
        ProjectConfig(**d)


def test_env_overrides_gee_project(monkeypatch):
    monkeypatch.setenv("CRYORISK_GEE_PROJECT", "my-other-project")
    assert ProjectConfig(**_base_project()).gee_project == "my-other-project"


def test_duplicate_rgi_ids_rejected():
    g = {"name": "A", "rgi_name": "A", "rgi_id": "X", "split": "train"}
    with pytest.raises(ValidationError):
        GlacierSet(glaciers=[g, {**g, "name": "B"}])


def test_season_date_range():
    cfg = load_project()
    assert cfg.season.date_range(2020) == ("2020-10-01", "2020-11-30")


def test_dotenv_fills_missing_vars_only(tmp_path, monkeypatch):
    from cryorisk.config import load_dotenv

    env = tmp_path / ".env"
    env.write_text('# comment\nCRYO_A=from_file\nCRYO_B="quoted"\n\nnot a pair\n')
    monkeypatch.delenv("CRYO_A", raising=False)
    monkeypatch.delenv("CRYO_B", raising=False)
    monkeypatch.setenv("CRYO_A", "from_shell")

    load_dotenv(env)
    assert os.environ["CRYO_A"] == "from_shell"
    assert os.environ["CRYO_B"] == "quoted"


def test_dotenv_missing_file_is_noop(tmp_path):
    from cryorisk.config import load_dotenv

    load_dotenv(tmp_path / "nope.env")
