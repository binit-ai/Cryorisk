"""Load and validate YAML configuration in configs/."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("CRYORISK_CONFIG_DIR", REPO_ROOT / "configs"))


class Season(BaseModel):
    start: str  # "MM-DD"
    end: str

    @field_validator("start", "end")
    @classmethod
    def _mm_dd(cls, v: str) -> str:
        month, day = (int(x) for x in v.split("-"))
        if not (1 <= month <= 12 and 1 <= day <= 31):
            raise ValueError(f"bad MM-DD: {v}")
        return v

    def date_range(self, year: int) -> tuple[str, str]:
        """Return ISO (start, end_exclusive-ish) dates for a given year."""
        return f"{year}-{self.start}", f"{year}-{self.end}"


class Paths(BaseModel):
    data: Path = Path("data")
    models: Path = Path("models")
    reports: Path = Path("reports")

    def resolve(self, root: Path) -> Paths:
        return Paths(**{k: (root / v if not v.is_absolute() else v) for k, v in self})


class ProjectConfig(BaseModel):
    gee_project: str | None = None
    crs: str = "EPSG:32645"
    resolution_m: float = 10
    years: tuple[int, int]
    season: Season
    region_bbox: tuple[float, float, float, float]
    aoi_buffer_m: float = 1500
    rgi_asset: str
    paths: Paths = Field(default_factory=Paths)

    @model_validator(mode="after")
    def _check(self) -> ProjectConfig:
        if self.years[0] > self.years[1]:
            raise ValueError("years must be [start, end] with start <= end")
        w, s, e, n = self.region_bbox
        if not (w < e and s < n):
            raise ValueError("region_bbox must be [west, south, east, north]")
        env = os.environ.get("CRYORISK_GEE_PROJECT")
        if env:
            self.gee_project = env
        self.paths = self.paths.resolve(REPO_ROOT)
        return self

    @property
    def year_list(self) -> list[int]:
        return list(range(self.years[0], self.years[1] + 1))


class Glacier(BaseModel):
    name: str
    rgi_name: str
    rgi_id: str | None = None
    split: Literal["train", "val", "test"]

    @property
    def slug(self) -> str:
        return self.name.lower().replace(" ", "_").replace("-", "_")


class GlacierSet(BaseModel):
    glaciers: list[Glacier]

    @model_validator(mode="after")
    def _unique(self) -> GlacierSet:
        ids = [g.rgi_id for g in self.glaciers if g.rgi_id]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rgi_id in glaciers.yaml")
        return self

    def get(self, name_or_slug: str) -> Glacier:
        key = name_or_slug.lower()
        for g in self.glaciers:
            if key in (g.name.lower(), g.slug):
                return g
        raise KeyError(f"unknown glacier: {name_or_slug}")

    def by_split(self, split: str) -> list[Glacier]:
        return [g for g in self.glaciers if g.split == split]

    @property
    def confirmed(self) -> list[Glacier]:
        return [g for g in self.glaciers if g.rgi_id]


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f) or {}


@lru_cache
def load_project(config_dir: Path = CONFIG_DIR) -> ProjectConfig:
    return ProjectConfig(**_load_yaml(Path(config_dir) / "project.yaml"))


@lru_cache
def load_glaciers(config_dir: Path = CONFIG_DIR) -> GlacierSet:
    return GlacierSet(**_load_yaml(Path(config_dir) / "glaciers.yaml"))
