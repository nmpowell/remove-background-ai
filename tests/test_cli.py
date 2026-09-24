import pkgutil
import tomllib
from pathlib import Path

from click.testing import CliRunner

from remove_background_ai.cli import cli

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


class TestCli:
    def test_version_reports_the_package_version(self) -> None:
        result = CliRunner().invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert result.stdout == "remove-background-ai, version 0.1.0\n"

    def test_entry_point_resolves_to_the_command(self) -> None:
        scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]

        assert pkgutil.resolve_name(scripts["remove-background-ai"]) is cli
