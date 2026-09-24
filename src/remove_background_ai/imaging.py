import io
from pathlib import Path

from PIL import Image, ImageChops, ImageCms, ImageOps

from .models import ImageSize


def load_source(path: Path) -> Image.Image:
    """Decode a source image as upright 8-bit RGB or RGBA.

    Its colour profile survives in ``info`` only when it describes RGB samples.
    """
    with Image.open(path) as image:
        image.load()
        oriented = ImageOps.exif_transpose(image)
        has_alpha = "A" in oriented.getbands() or "transparency" in oriented.info
        source = oriented.convert("RGBA" if has_alpha else "RGB")
    profile = source.info.get("icc_profile")
    source.info = {"icc_profile": profile} if _is_rgb_profile(profile) else {}
    return source


def encode_request(image: Image.Image, size: ImageSize) -> bytes:
    """Encode the image as the PNG to send to the model, at the model size."""
    return _png(image.resize((size.width, size.height), Image.Resampling.LANCZOS))


def decode_cutout(png: bytes) -> Image.Image:
    """Decode the PNG the model returned."""
    with Image.open(io.BytesIO(png)) as image:
        image.load()
        return image.convert("RGBA")


def apply_alpha(source: Image.Image, cutout: Image.Image) -> bytes:
    """Return the source pixels with the cutout's alpha, as a PNG.

    The cutout's alpha is total opacity, so it never raises the source's own alpha.
    """
    alpha = cutout.getchannel("A").resize(source.size, Image.Resampling.LANCZOS)
    if source.mode == "RGBA":
        alpha = ImageChops.darker(alpha, source.getchannel("A"))
    result = source.convert("RGBA")
    result.putalpha(alpha)
    return _png(result, icc_profile=source.info.get("icc_profile"))


def _is_rgb_profile(profile: object) -> bool:
    if not isinstance(profile, bytes):
        return False
    try:
        parsed = ImageCms.ImageCmsProfile(io.BytesIO(profile))
    except ImageCms.PyCMSError:
        return False
    return parsed.profile.xcolor_space == "RGB "


def _png(image: Image.Image, *, icc_profile: bytes | None = None) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", icc_profile=icc_profile)
    return buffer.getvalue()
