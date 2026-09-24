from pathlib import Path

from . import imaging
from .editor import ImageEditor
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


def remove_background(
    image: Path,
    *,
    editor: ImageEditor,
    options: RemovalOptions = DEFAULT_OPTIONS,
) -> Cutout:
    """Remove the background from an image file."""
    source = imaging.load_source(image)
    size = model_size_for(ImageSize(width=source.width, height=source.height))
    response = editor.edit(
        EditRequest(
            image=imaging.encode_request(source, size),
            prompt=_prompt(options),
            model=options.model,
            quality=options.quality,
            size=size,
        )
    )
    cutout = imaging.decode_cutout(response.image, size)
    if options.mode == "generated":
        return Cutout(png=response.image)
    return Cutout(png=imaging.apply_alpha(source, cutout))


def _prompt(options: RemovalOptions) -> str:
    return _PROMPT.format(
        keep=(options.keep or "the main subject").rstrip("."),
        remove=(options.remove or "everything else").rstrip("."),
    )
