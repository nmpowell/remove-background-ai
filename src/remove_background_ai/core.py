from pathlib import Path

from pydantic import ConfigDict, InstanceOf, SkipValidation, validate_call

from . import imaging
from .editor import ImageEditor, OpenAIImageEditor
from .models import Cutout, EditRequest, ImageSize, RemovalOptions
from .sizing import model_size_for

DEFAULT_OPTIONS = RemovalOptions()
_PROMPT = """\
Edit the supplied image to remove its background.

KEEP: {keep}.
REMOVE: {remove}.

Leave what is kept in its existing position, scale, orientation and pose on the \
original canvas. Preserve its geometry, colours, lighting, texture, lettering, logos \
and fine detail such as hair, fur and thin parts. Do not retouch, restyle, recentre, \
crop, sharpen or reconstruct hidden parts.

Make every removed region fully transparent, including background seen through gaps \
and openings. Use partially transparent pixels where an edge is soft. Add no \
scenery, outline, replacement background, white fill, checkerboard or new shadow."""
_MASK_NOTE = """

The supplied mask marks the subject: keep its opaque area and remove the background \
in its transparent area."""


@validate_call(config=ConfigDict(strict=True, arbitrary_types_allowed=True))
def remove_background(
    image: Path,
    *,
    editor: SkipValidation[ImageEditor | None] = None,
    options: InstanceOf[RemovalOptions] = DEFAULT_OPTIONS,
    mask: Path | None = None,
) -> Cutout:
    """Remove the background from an image file.

    ``mask`` is an optional image the size of the upright source: white keeps,
    black removes. ``editor`` defaults to the OpenAI API, authenticated by the
    ``OPENAI_API_KEY`` environment variable.
    """
    source = imaging.load_source(image)
    if editor is None:
        editor = OpenAIImageEditor()
    source_size = ImageSize(width=source.width, height=source.height)
    size = model_size_for(source_size)
    response = editor.edit(
        EditRequest(
            image=imaging.encode_request(source, size),
            mask=None if mask is None else imaging.encode_mask(mask, source_size, size),
            prompt=_prompt(options, masked=mask is not None),
            model=options.model,
            quality=options.quality,
            size=size,
        )
    )
    cutout = imaging.decode_cutout(response.image, size)
    if options.mode == "generated":
        png, output_size = response.image, size
    else:
        png, output_size = imaging.apply_alpha(source, cutout), source_size
    return Cutout(
        png=png,
        mode=options.mode,
        model=options.model,
        quality=options.quality,
        source_size=source_size,
        model_size=size,
        output_size=output_size,
        request_id=response.request_id,
        usage=response.usage,
    )


def _prompt(options: RemovalOptions, *, masked: bool) -> str:
    prompt = _PROMPT.format(
        keep=(options.keep or "the main subject").rstrip("."),
        remove=(options.remove or "everything else").rstrip("."),
    )
    return prompt + _MASK_NOTE if masked else prompt
