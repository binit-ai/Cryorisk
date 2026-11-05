import pytest
from typer.testing import CliRunner

from cryorisk.cli import app

runner = CliRunner()


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("auth", "glaciers", "rgi", "availability"):
        assert cmd in result.output


def test_glaciers_command_runs_offline():
    result = runner.invoke(app, ["glaciers"])
    assert result.exit_code == 0
    assert "Ngozumpa" in result.output
    assert "RGI2000-v7.0-G-15-08305" in result.output


@pytest.mark.gee
def test_rgi_search_finds_ngozumpa():
    result = runner.invoke(app, ["rgi", "search", "Ngojumba"])
    assert result.exit_code == 0
    assert "RGI2000-v7.0-G-15-08305" in result.output
