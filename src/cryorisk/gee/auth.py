"""Earth Engine authentication / initialization (ported from scripts/legacy/01_gee_auth.py)."""

from __future__ import annotations

import ee

_initialized: str | None = None


def authenticate() -> None:
    """Interactive browser login. Only needed once per machine."""
    ee.Authenticate()


def init(project: str | None) -> None:
    """Initialize EE once per process. Must run before any ee.Geometry/ee.Image is created."""
    global _initialized
    if not project:
        raise ValueError(
            "No GEE project set. Put gee_project in configs/project.yaml "
            "or export CRYORISK_GEE_PROJECT."
        )
    if _initialized == project:
        return
    ee.Initialize(project=project)
    _initialized = project
