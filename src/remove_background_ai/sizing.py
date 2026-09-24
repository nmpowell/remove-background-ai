import math

from .errors import InvalidInputError
from .models import ImageSize

GRID = 16
MIN_PIXELS = 655_360
# Larger outputs, up to 8,294,400 pixels, are experimental; never request them.
MAX_PIXELS = 3_686_400
MAX_ASPECT = 3


def model_size_for(source: ImageSize) -> ImageSize:
    """Return the size to request from GPT Image 2.5 for a source image."""
    if not _within_aspect_limit(source):
        raise InvalidInputError(
            f"{source} has an aspect ratio beyond {MAX_ASPECT}:1, "
            "which GPT Image 2.5 cannot produce"
        )
    if is_supported(source):
        return source
    ratio = source.width / source.height
    area = source.width * source.height
    scale = math.sqrt(min(max(area, MIN_PIXELS), MAX_PIXELS) / area)
    candidates = [
        ImageSize(width=width, height=height)
        for width in _nearest_multiples(source.width * scale)
        for height in _nearest_multiples(source.height * scale)
    ]
    supported = [size for size in candidates if is_supported(size)]
    return min(
        supported,
        key=lambda size: (
            abs(math.log(size.width / size.height / ratio)),
            -size.width * size.height,
        ),
    )


def is_supported(size: ImageSize) -> bool:
    """Return whether GPT Image 2.5 can produce an image of this size."""
    return (
        size.width % GRID == 0
        and size.height % GRID == 0
        and MIN_PIXELS <= size.width * size.height <= MAX_PIXELS
        and _within_aspect_limit(size)
    )


def _within_aspect_limit(size: ImageSize) -> bool:
    return max(size.width, size.height) <= MAX_ASPECT * min(size.width, size.height)


def _nearest_multiples(length: float) -> set[int]:
    steps = length / GRID
    return {max(1, math.floor(steps)) * GRID, max(1, math.ceil(steps)) * GRID}
