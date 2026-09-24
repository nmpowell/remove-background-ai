import json
import pkgutil
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from remove_background_ai.cli import cli

from .conftest import FakeEditor

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"
WriteImage = Callable[..., Path]


class TestCli:
    def test_version_reports_the_package_version(self) -> None:
        result = CliRunner().invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert result.stdout == "remove-background-ai, version 0.1.0\n"

    def test_entry_point_resolves_to_the_command(self) -> None:
        scripts = tomllib.loads(PYPROJECT.read_text())["project"]["scripts"]

        assert pkgutil.resolve_name(scripts["remove-background-ai"]) is cli


class TestDefaultOutput:
    def test_writes_a_transparent_png_beside_the_image(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        output = source.with_name("source-no-bg.png")
        assert result.exit_code == 0
        assert result.stdout == f"{output}\n"
        assert result.stderr == f"Removing the background from {source}\n"
        with Image.open(output) as image:
            assert image.mode == "RGBA"
            assert image.size == (1024, 1024)


class TestOutputOptions:
    def test_output_writes_the_named_file(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        output = tmp_path / "custom.png"

        result = CliRunner().invoke(
            cli, [str(source), "-o", str(output)], obj={"editor": editor}
        )

        assert result.exit_code == 0
        assert result.stdout == f"{output}\n"
        assert output.is_file()

    def test_output_dir_is_created_with_its_parents(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        directory = tmp_path / "new" / "cutouts"

        result = CliRunner().invoke(
            cli, [str(source), "-d", str(directory)], obj={"editor": editor}
        )

        output = directory / "source-no-bg.png"
        assert result.exit_code == 0
        assert result.stdout == f"{output}\n"
        assert output.is_file()

    def test_generated_mode_writes_the_model_size(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1920, 1080), "red"))

        result = CliRunner().invoke(
            cli, [str(source), "--mode", "generated"], obj={"editor": editor}
        )

        assert result.exit_code == 0
        with Image.open(source.with_name("source-no-bg.png")) as image:
            assert image.size == (1920, 1088)

    def test_keep_and_remove_shape_the_prompt(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(
            cli,
            [str(source), "--keep", "the red backpack", "--remove", "the stand"],
            obj={"editor": editor},
        )

        assert result.exit_code == 0
        assert "KEEP: the red backpack." in editor.requests[0].prompt
        assert "REMOVE: the stand." in editor.requests[0].prompt

    def test_mask_is_sent_to_the_editor(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        mask = tmp_path / "mask.png"
        Image.new("L", (1024, 1024), 255).save(mask)

        result = CliRunner().invoke(
            cli, [str(source), "--mask", str(mask)], obj={"editor": editor}
        )

        assert result.exit_code == 0
        assert editor.requests[0].mask is not None


class TestInvocationChecks:
    @pytest.mark.parametrize("option", ["-o", "--mask"])
    def test_single_image_options_refuse_a_batch(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path, option: str
    ) -> None:
        first = write_image(Image.new("RGB", (1024, 1024), "red"), "one.png")
        second = write_image(Image.new("RGB", (1024, 1024), "blue"), "two.png")
        extra = tmp_path / "extra.png"
        Image.new("L", (1024, 1024), 255).save(extra)

        result = CliRunner().invoke(
            cli, [str(first), str(second), option, str(extra)], obj={"editor": editor}
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert editor.requests == []

    def test_output_and_output_dir_cannot_be_combined(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(
            cli,
            [str(source), "-o", str(tmp_path / "x.png"), "-d", str(tmp_path)],
            obj={"editor": editor},
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert editor.requests == []

    def test_two_inputs_cannot_share_an_output(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        first = write_image(Image.new("RGB", (1024, 1024), "red"), "photo.png")
        second = write_image(Image.new("RGB", (1024, 1024), "blue"), "photo.jpg")

        result = CliRunner().invoke(
            cli,
            [str(first), str(second), "-d", str(tmp_path / "new")],
            obj={"editor": editor},
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert editor.requests == []
        assert not (tmp_path / "new").exists()

    def test_default_output_cannot_replace_another_input(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        first = write_image(Image.new("RGB", (1024, 1024), "red"), "photo.png")
        second = write_image(Image.new("RGB", (1024, 1024), "blue"), "photo-no-bg.png")

        result = CliRunner().invoke(
            cli, [str(first), str(second)], obj={"editor": editor}
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert editor.requests == []

    @pytest.mark.parametrize("output_name", ["source.png", "mask.png"])
    def test_output_cannot_replace_an_input(
        self,
        editor: FakeEditor,
        write_image: WriteImage,
        tmp_path: Path,
        output_name: str,
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        mask = tmp_path / "mask.png"
        Image.new("L", (1024, 1024), 255).save(mask)
        output = tmp_path / output_name

        result = CliRunner().invoke(
            cli,
            [str(source), "--mask", str(mask), "-o", str(output), "--force"],
            obj={"editor": editor},
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert editor.requests == []

    @pytest.mark.parametrize("option", ["--keep", "--remove"])
    def test_blank_description_is_a_usage_error_before_processing(
        self, editor: FakeEditor, write_image: WriteImage, option: str
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(
            cli, [str(source), option, "   "], obj={"editor": editor}
        )

        assert result.exit_code == 2
        assert result.stdout == ""
        assert (
            f"Invalid value for '{option}': String should have at least 1 character"
            in result.stderr
        )
        assert editor.requests == []


class TestPerImageResults:
    def test_existing_output_is_untouched_and_never_sent(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        output = source.with_name("source-no-bg.png")
        output.write_bytes(b"previous")

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 3
        assert result.stdout == ""
        assert f"{output} already exists; use --force to replace it" in result.stderr
        assert output.read_bytes() == b"previous"
        assert editor.requests == []

    def test_force_replaces_existing_output(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        output = source.with_name("source-no-bg.png")
        output.write_bytes(b"previous")

        result = CliRunner().invoke(
            cli, [str(source), "--force"], obj={"editor": editor}
        )

        assert result.exit_code == 0
        assert output.read_bytes().startswith(b"\x89PNG")
        assert sorted(source.parent.iterdir()) == sorted([source, output])

    def test_missing_output_parent_is_reported_before_editing(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        directory = tmp_path / "missing"
        output = directory / "cutout.png"

        result = CliRunner().invoke(
            cli, [str(source), "-o", str(output)], obj={"editor": editor}
        )

        assert result.exit_code == 3
        assert result.stdout == ""
        assert str(directory) in result.stderr
        assert editor.requests == []
        assert not directory.exists()

    def test_output_dir_creation_error_names_the_directory(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        directory = tmp_path / "file"
        directory.write_text("occupied")

        result = CliRunner().invoke(
            cli, [str(source), "-d", str(directory)], obj={"editor": editor}
        )

        assert result.exit_code == 3
        assert result.stdout == ""
        assert str(directory) in result.stderr
        assert editor.requests == []

    def test_bad_image_fails_but_the_next_image_succeeds(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        good = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(cli, [str(bad), str(good)], obj={"editor": editor})

        assert result.exit_code == 3
        assert result.stdout == f"{tmp_path / 'source-no-bg.png'}\n"
        assert f"{bad}:" in result.stderr
        assert (tmp_path / "source-no-bg.png").is_file()

    def test_unusable_model_image_exits_four(self, write_image: WriteImage) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        editor = FakeEditor(response_png=b"garbage")

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 4
        assert result.stdout == ""
        assert "could not be decoded" in result.stderr

    def test_edit_failure_takes_priority_over_bad_input(
        self, write_image: WriteImage, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        good = write_image(Image.new("RGB", (1024, 1024), "red"))
        editor = FakeEditor(response_png=b"garbage")

        result = CliRunner().invoke(cli, [str(bad), str(good)], obj={"editor": editor})

        assert result.exit_code == 4
        assert result.stdout == ""
        assert f"{bad}:" in result.stderr
        assert f"{good}:" in result.stderr

    def test_missing_api_key_exits_four_before_processing(
        self, write_image: WriteImage, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        result = CliRunner().invoke(cli, [str(source)])

        assert result.exit_code == 4
        assert result.stdout == ""
        assert "Error: Set OPENAI_API_KEY" in result.stderr

    def test_success_leaves_no_temporary_files(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 0
        assert sorted(source.parent.iterdir()) == sorted(
            [source, source.with_name("source-no-bg.png")]
        )

    def test_refused_publish_leaves_no_temporary_files(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        output = source.with_name("source-no-bg.png")
        output.write_bytes(b"previous")

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 3
        assert sorted(source.parent.iterdir()) == sorted([source, output])

    def test_publish_race_preserves_the_other_file_and_removes_the_temp(
        self,
        editor: FakeEditor,
        write_image: WriteImage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))
        output = source.with_name("source-no-bg.png")

        def competing_link(temporary: Path, destination: Path) -> None:
            destination.write_bytes(b"other writer")
            raise FileExistsError(destination)

        monkeypatch.setattr("remove_background_ai.cli.os.link", competing_link)

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 3
        assert "already exists; use --force" in result.stderr
        assert output.read_bytes() == b"other writer"
        assert sorted(source.parent.iterdir()) == sorted([source, output])

    def test_publish_error_reports_the_output_and_removes_the_temp(
        self,
        editor: FakeEditor,
        write_image: WriteImage,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        def refusing_link(temporary: Path, destination: Path) -> None:
            raise PermissionError("denied")

        monkeypatch.setattr("remove_background_ai.cli.os.link", refusing_link)

        result = CliRunner().invoke(cli, [str(source)], obj={"editor": editor})

        assert result.exit_code == 3
        assert (
            f"cannot write {source.with_name('source-no-bg.png')}: denied"
            in result.stderr
        )
        assert result.stdout == ""
        assert list(source.parent.iterdir()) == [source]


class TestHelp:
    def test_help_has_examples_and_exit_codes(self) -> None:
        result = CliRunner().invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Examples:" in result.stdout
        assert "remove-background-ai photo.jpg" in result.stdout
        assert "Exit codes:" in result.stdout


class TestJsonResults:
    def test_success_has_cutout_metadata_and_chosen_model_and_quality(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(
            cli,
            [
                str(source),
                "--json",
                "--quality",
                "medium",
                "--model",
                "gpt-image-2.5-flare",
            ],
            obj={"editor": editor},
        )

        assert result.exit_code == 0
        assert json.loads(result.stdout) == [
            {
                "input": str(source),
                "output": str(tmp_path / "source-no-bg.png"),
                "mode": "original",
                "model": "gpt-image-2.5-flare",
                "quality": "medium",
                "source_size": "1024x1024",
                "model_size": "1024x1024",
                "output_size": "1024x1024",
                "request_id": "req_fake",
                "usage": None,
            }
        ]
        assert str(tmp_path / "source-no-bg.png") not in result.stdout.splitlines()

    def test_failure_stays_in_input_order_with_success(
        self, editor: FakeEditor, write_image: WriteImage, tmp_path: Path
    ) -> None:
        bad = tmp_path / "bad.png"
        bad.write_text("not an image")
        good = write_image(Image.new("RGB", (1024, 1024), "red"))

        result = CliRunner().invoke(
            cli, [str(bad), str(good), "--json"], obj={"editor": editor}
        )

        records = json.loads(result.stdout)
        assert result.exit_code == 3
        assert records[0]["input"] == str(bad)
        assert "cannot be read as an image" in records[0]["error"]
        assert set(records[0]) == {"input", "error"}
        assert records[1] == {
            "input": str(good),
            "output": str(tmp_path / "source-no-bg.png"),
            "mode": "original",
            "model": "gpt-image-2.5-sunburst-2026-09-08",
            "quality": "high",
            "source_size": "1024x1024",
            "model_size": "1024x1024",
            "output_size": "1024x1024",
            "request_id": "req_fake",
            "usage": None,
        }
