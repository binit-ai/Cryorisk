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


if __name__ == "__main__":
    app()
