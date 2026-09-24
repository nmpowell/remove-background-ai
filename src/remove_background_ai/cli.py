import json
import os
import secrets
from pathlib import Path
from typing import NoReturn, cast, get_args

import click
from pydantic import ValidationError

from .core import remove_background
from .editor import ImageEditor, OpenAIImageEditor
from .errors import EditError, InvalidInputError
from .models import Cutout, ModelName, OutputMode, Quality, RemovalOptions

EXIT_REFUSED = 3
EXIT_EDIT_FAILED = 4


@click.command(
    name="remove-background-ai",
    epilog=(
        "Exit codes: 0 success; 1 general failure; 2 usage error; "
        "3 input or output refused; 4 image edit failed."
    ),
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    metavar="FILE",
    help="Write the PNG to FILE.",
)
@click.option(
    "-d",
    "--output-dir",
    type=click.Path(path_type=Path),
    metavar="DIRECTORY",
    help="Write PNGs to DIRECTORY.",
)
@click.option("--force", is_flag=True, help="Replace output files that already exist.")
@click.option(
    "--keep", help="What to keep, for example the red backpack and its straps."
)
@click.option("--remove", help="What to remove besides the background.")
@click.option(
    "--mask",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Mask FILE: white keeps, black removes; same size as the image.",
)
@click.option(
    "--mode",
    type=click.Choice(get_args(OutputMode)),
    default="original",
    show_default=True,
    help="Keep original pixels and size, or use the generated image.",
)
@click.option(
    "--model",
    type=click.Choice(get_args(ModelName)),
    default="gpt-image-2.5-sunburst-2026-09-08",
    show_default=True,
    help="GPT Image model to use.",
)
@click.option(
    "--quality",
    type=click.Choice(get_args(Quality)),
    default="high",
    show_default=True,
    help="Image edit quality.",
)
@click.option("--json", "as_json", is_flag=True, help="Write a JSON array to stdout.")
@click.version_option(
    package_name="remove-background-ai", prog_name="remove-background-ai"
)
@click.argument(
    "images",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.pass_context
def cli(
    ctx: click.Context,
    images: tuple[Path, ...],
    output: Path | None,
    output_dir: Path | None,
    force: bool,
    keep: str | None,
    remove: str | None,
    mask: Path | None,
    mode: str,
    model: str,
    quality: str,
    as_json: bool,
) -> None:
    """Send each image to GPT Image 2.5 and write a transparent PNG. By default,
    the result keeps the original pixels and size and takes only transparency
    from the model. Set OPENAI_API_KEY before running this command.

    Examples:

    \b
        remove-background-ai photo.jpg
        remove-background-ai photo.jpg -o portrait.png
        remove-background-ai photo.jpg other.png -d cutouts --json
        remove-background-ai photo.jpg --keep "the red backpack, including both straps"
    """
    try:
        options = RemovalOptions(
            keep=keep,
            remove=remove,
            mode=cast("OutputMode", mode),
            model=cast("ModelName", model),
            quality=cast("Quality", quality),
        )
    except ValidationError as error:
        first = error.errors()[0]
        raise click.BadParameter(
            first["msg"], param_hint=f"'--{first['loc'][0]}'"
        ) from None
    if output is not None and len(images) != 1:
        raise click.UsageError("-o/--output requires exactly one image")
    if mask is not None and len(images) != 1:
        raise click.UsageError("--mask requires exactly one image")
    if output is not None and output_dir is not None:
        raise click.UsageError("-o/--output and -d/--output-dir cannot be combined")
    destinations = tuple(
        output or (output_dir or image.parent) / f"{image.stem}-no-bg.png"
        for image in images
    )
    resolved = [destination.resolve() for destination in destinations]
    if len(set(resolved)) != len(resolved):
        raise click.UsageError("two images would write the same output")
    inputs = {image.resolve() for image in images}
    if mask is not None:
        inputs.add(mask.resolve())
    if any(destination in inputs for destination in resolved):
        raise click.UsageError("an output path cannot be an input image or mask")
    try:
        editor: ImageEditor = (
            ctx.obj["editor"]
            if ctx.obj and "editor" in ctx.obj
            else OpenAIImageEditor()
        )
    except EditError as error:
        _fail_every_image(images, str(error), EXIT_EDIT_FAILED, as_json=as_json)
    if output_dir is not None:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            message = f"cannot create {output_dir}: {error}"
            _fail_every_image(images, message, EXIT_REFUSED, as_json=as_json)
    results: list[dict[str, object]] = []
    exit_code = 0
    for image, destination in zip(images, destinations, strict=True):
        click.echo(f"Removing the background from {image}", err=True)
        try:
            cutout = _process_one(
                image,
                destination,
                options=options,
                mask=mask,
                editor=editor,
                force=force,
            )
        except _ImageFailed as failure:
            click.echo(f"{image}: {failure.message}", err=True)
            results.append({"input": str(image), "error": failure.message})
            exit_code = max(exit_code, failure.exit_code)
            continue
        results.append(
            {
                "input": str(image),
                "output": str(destination),
                **cutout.model_dump(mode="json"),
            }
        )
        if not as_json:
            click.echo(str(destination))
    if as_json:
        click.echo(json.dumps(results, indent=2))
    if exit_code:
        raise SystemExit(exit_code)


def _process_one(
    image: Path,
    output: Path,
    *,
    options: RemovalOptions,
    mask: Path | None,
    editor: ImageEditor,
    force: bool,
) -> Cutout:
    already_exists = f"{output} already exists; use --force to replace it"
    if output.exists() and not force:
        raise _ImageFailed(already_exists, EXIT_REFUSED)
    if not output.parent.is_dir():
        raise _ImageFailed(
            f"output directory {output.parent} does not exist", EXIT_REFUSED
        )
    try:
        cutout = remove_background(image, options=options, mask=mask, editor=editor)
    except InvalidInputError as error:
        raise _ImageFailed(str(error), EXIT_REFUSED) from None
    except EditError as error:
        raise _ImageFailed(str(error), EXIT_EDIT_FAILED) from None
    try:
        _write_atomic(output, cutout.png, force=force)
    except FileExistsError:
        raise _ImageFailed(already_exists, EXIT_REFUSED) from None
    except OSError as error:
        raise _ImageFailed(f"cannot write {output}: {error}", EXIT_REFUSED) from None
    return cutout


def _fail_every_image(
    images: tuple[Path, ...], message: str, exit_code: int, *, as_json: bool
) -> NoReturn:
    click.echo(f"Error: {message}", err=True)
    if as_json:
        records = [{"input": str(image), "error": message} for image in images]
        click.echo(json.dumps(records, indent=2))
    raise SystemExit(exit_code)


class _ImageFailed(Exception):
    def __init__(self, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def _write_atomic(output: Path, png: bytes, *, force: bool) -> None:
    # A plain exclusive open, unlike tempfile, leaves the permissions to the umask.
    temporary = output.with_name(f".{output.name}.{secrets.token_hex(8)}.tmp")
    try:
        with temporary.open("xb") as file:
            file.write(png)
        if force:
            os.replace(temporary, output)
        else:
            os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
