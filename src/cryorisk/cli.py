"""`cryorisk` command-line interface. One subcommand per pipeline stage (docs/DESIGN.md §11)."""

from __future__ import annotations

import typer

from cryorisk.config import load_glaciers, load_project

app = typer.Typer(help="CryoRisk glacier pipeline", no_args_is_help=True)
rgi_app = typer.Typer(help="Randolph Glacier Inventory outlines", no_args_is_help=True)
app.add_typer(rgi_app, name="rgi")


def _init_ee():
    from cryorisk.gee import auth

    auth.init(load_project().gee_project)


@app.command()
def auth():
    """Log in to Earth Engine (opens a browser) and verify initialization."""
    from cryorisk.gee import auth as gee_auth

    gee_auth.authenticate()
    _init_ee()
    typer.echo("Earth Engine authenticated and initialized.")


@app.command()
def glaciers():
    """Show configured study glaciers and whether their RGI ids are confirmed."""
    for g in load_glaciers().glaciers:
        status = g.rgi_id or "UNCONFIRMED (run `cryorisk rgi search`)"
        typer.echo(f"{g.split:5}  {g.name:18}  {status}")


@rgi_app.command("search")
def rgi_search(
    name: str = typer.Argument(None, help="Name substring, e.g. 'Khumbu'. Omit to list all."),
    min_area: float = typer.Option(1.0, help="Minimum area in km²"),
):
    """Search RGI7 inside the project region to find rgi_ids for configs/glaciers.yaml."""
    from cryorisk.gee import rgi

    _init_ee()
    cfg = load_project()
    rows = rgi.search(cfg.rgi_asset, cfg.region_bbox, name, min_area)
    if not rows:
        typer.echo("No matches.")
    for r in rows:
        typer.echo(f"{r['rgi_id']}  {r['glac_name'] or '-':25}  {r['area_km2']:.2f} km²")


@rgi_app.command("fetch")
def rgi_fetch():
    """Download RGI7 outlines for every confirmed glacier to data/rgi/<slug>.geojson."""
    from cryorisk.gee import rgi

    _init_ee()
    cfg = load_project()
    gset = load_glaciers()
    for g in gset.glaciers:
        if not g.rgi_id:
            typer.echo(f"skip  {g.name}: rgi_id not confirmed")
            continue
        feat = rgi.fetch(cfg.rgi_asset, g.rgi_id)
        out = rgi.save_geojson(feat, cfg.paths.data / "rgi" / f"{g.slug}.geojson")
        area = feat["properties"].get("area_km2")
        typer.echo(f"saved {g.name}: {area} km² -> {out}")


@app.command()
def availability(max_cloud: float = typer.Option(30, help="Max S2 cloudy pixel %")):
    """Count Sentinel-1/-2 scenes per year (total and in the post-monsoon season)."""
    from cryorisk.gee import availability as av
    from cryorisk.gee import rgi

    _init_ee()
    cfg = load_project()
    geom = rgi.region(cfg.region_bbox)
    start, end = f"{cfg.years[0]}-01-01", f"{cfg.years[1] + 1}-01-01"
    years = cfg.year_list

    s2 = av.s2_collection(geom, start, end, max_cloud)
    s1 = av.s1_collection(geom, start, end)
    s2_y, s2_s = av.counts_by_year(s2, years), av.seasonal_counts(s2, years, cfg.season)
    s1_y, s1_s = av.counts_by_year(s1, years), av.seasonal_counts(s1, years, cfg.season)

    typer.echo(f"{'year':>4}  {'S2 all':>7}  {'S2 season':>9}  {'S1 all':>7}  {'S1 season':>9}")
    for y in years:
        typer.echo(f"{y:>4}  {s2_y[y]:>7}  {s2_s[y]:>9}  {s1_y[y]:>7}  {s1_s[y]:>9}")


def _parse_years(years: str | None, default: list[int]) -> list[int]:
    if not years:
        return default
    if "-" in years:
        a, b = (int(x) for x in years.split("-"))
        return list(range(a, b + 1))
    return [int(y) for y in years.split(",")]


@app.command()
def ingest(
    aoi: list[str] = typer.Option(None, help="Glacier name/slug (repeatable). Default: all."),
    years: str = typer.Option(None, help="e.g. 2023, 2016-2025 or 2018,2020"),
    to: str = typer.Option("drive", help="drive (Export to Google Drive) or local"),
    dry_run: bool = typer.Option(False, help="Only print grids and size estimates"),
    force: bool = typer.Option(False, help="Re-export even if a manifest already exists"),
):
    """Build 12-band post-monsoon stacks and export them on the AOI's fixed UTM grid."""
    if to not in ("drive", "local"):
        raise typer.BadParameter("--to must be 'drive' or 'local'")
    from cryorisk.data.grid import aoi_grid, load_polygon
    from cryorisk.gee import export, stack

    cfg = load_project()
    gset = load_glaciers()
    targets = [gset.get(a) for a in aoi] if aoi else gset.confirmed
    year_list = _parse_years(years, cfg.year_list)
    if not dry_run:
        _init_ee()

    total = 0
    for g in targets:
        poly_path = cfg.paths.data / "rgi" / f"{g.slug}.geojson"
        if not poly_path.exists():
            raise typer.BadParameter(f"{poly_path} missing — run `cryorisk rgi fetch` first")
        grid = aoi_grid(load_polygon(poly_path), cfg.crs, cfg.resolution_m, cfg.aoi_buffer_m)
        size_mb = export.estimated_bytes(grid) / 1e6
        for y in year_list:
            total += size_mb
            name = f"{g.slug}_{y}_stack"
            typer.echo(f"{name}: {grid.width}x{grid.height} px, ~{size_mb:.0f} MB uncompressed")
            if dry_run:
                continue
            raw_dir = cfg.paths.data / "raw" / g.slug / str(y)
            if (raw_dir / f"manifest_{to}.json").exists() and not force:
                typer.echo("  already exported (manifest exists); use --force to redo")
                continue
            start, end = cfg.season.date_range(y)
            geom = export.grid_geometry(grid)
            img, meta = stack.build_stack(geom, start, end)
            meta = meta.getInfo()
            if meta["s2_scenes"] == 0:
                typer.echo(f"  WARNING: no S2 scenes for {name}; skipping")
                continue
            task_id = None
            if to == "drive":
                task_id = export.export_to_drive(img, grid, name).id
                typer.echo(f"  Drive task started: {task_id} (folder '{export.DRIVE_FOLDER}')")
            else:
                out = export.download_local(img, grid, raw_dir / "stack.tif", progress=typer.echo)
                typer.echo(f"  saved {out}")
            # one manifest per target so a Drive run never clobbers a local stack's record
            export.write_manifest(
                raw_dir / f"manifest_{to}.json", aoi=g.slug, year=y, start=start, end=end,
                grid=grid, meta=meta, target=to, task_id=task_id,
            )
            typer.echo(f"  scenes: {meta}")
    typer.echo(f"Total ~{total / 1e3:.1f} GB uncompressed (GeoTIFFs are compressed, often 2-3x).")


@app.command()
def tasks(limit: int = typer.Option(20, help="How many recent tasks to show")):
    """Show recent Earth Engine export task status."""
    import ee

    _init_ee()
    for t in ee.data.getTaskList()[:limit]:
        typer.echo(f"{t.get('state', '?'):10} {t.get('description', '')}  {t.get('id', '')}")


@app.command()
def inspect(path: str):
    """Print per-band valid %, min/median/max (physical units) for a stack GeoTIFF."""
    from pathlib import Path

    from cryorisk.data.inspect import stack_report

    typer.echo(f"{'band':10} {'unit':12} {'valid%':>7} {'min':>9} {'median':>9} {'max':>9}")
    for r in stack_report(Path(path)):
        typer.echo(
            f"{r['band']:10} {r['unit']:12} {r['valid_pct']:7.1f} "
            f"{r['min']:9.3f} {r['median']:9.3f} {r['max']:9.3f}"
        )


if __name__ == "__main__":
    app()
