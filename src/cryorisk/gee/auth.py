from __future__ import annotations

import ee

_initialized: str | None = None


def authenticate() -> None:
    ee.Authenticate()


def init(project: str | None) -> None:
    # Has to run before any ee.Geometry/ee.Image is built, otherwise EE throws
    # "not initialized" at construction time (bit us in the old script 03).
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
