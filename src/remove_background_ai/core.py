from pathlib import Path

from . import imaging
from .editor import ImageEditor
from .models import Cutout, EditRequest, ImageSize, RemovalOptions
from .sizing import model_size_for

PROMPT = "Remove the background. Make it fully transparent."
DEFAULT_OPTIONS = RemovalOptions()


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
            prompt=PROMPT,
            model=options.model,
            quality=options.quality,
            size=size,
        )
    )
    if options.mode == "generated":
        return Cutout(png=response.image)
    return Cutout(
        png=imaging.apply_alpha(source, imaging.decode_cutout(response.image))
    )
