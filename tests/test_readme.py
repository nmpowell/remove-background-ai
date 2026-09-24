from pathlib import Path

from cogapp import Cog

README = Path(__file__).parent.parent / "README.md"


def test_the_cli_reference_in_the_readme_is_up_to_date() -> None:
    assert Cog().main(["cog", "--check", "--diff", str(README)]) == 0
