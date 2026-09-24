import io
from pathlib import Path

from PIL import Image, ImageOps

from .models import ImageSize


def load_source(path: Path) -> Image.Image:
    """Decode a source image."""
    with Image.open(path) as image:
        image.load()
        return ImageOps.exif_transpose(image).convert("RGB")


def encode_request(image: Image.Image, size: ImageSize) -> bytes:
    """Encode the image as the PNG to send to the model, at the model size."""
    return _png(image.resize((size.width, size.height), Image.Resampling.LANCZOS))


def decode_cutout(png: bytes) -> Image.Image:
    """Decode the PNG the model returned."""
    with Image.open(io.BytesIO(png)) as image:
        image.load()
        return image.convert("RGBA")


def apply_alpha(source: Image.Image, cutout: Image.Image) -> bytes:
    """Return the source pixels with the cutout's alpha, as a PNG."""
    alpha = cutout.getchannel("A").resize(source.size, Image.Resampling.LANCZOS)
    result = source.convert("RGBA")
    result.putalpha(alpha)
    return _png(result)


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
