import io
import os
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from remove_background_ai import RemovalOptions, remove_background

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        os.environ.get("RUN_LIVE_OPENAI_TESTS") != "1"
        or not os.environ.get("OPENAI_API_KEY"),
        reason="calls the paid API; needs RUN_LIVE_OPENAI_TESTS=1 and OPENAI_API_KEY",
    ),
]


def disc_on_a_gradient() -> Image.Image:
    """A red disc in the middle of a blue-to-green gradient, 1200x800."""
    image = Image.new("RGB", (1200, 800))
    draw = ImageDraw.Draw(image)
    for x in range(1200):
        draw.line([(x, 0), (x, 799)], fill=(0, x * 255 // 1199, 255 - x * 255 // 1199))
    draw.ellipse((400, 200, 800, 600), fill=(220, 20, 20))
    return image


def test_removes_the_background_around_a_disc(tmp_path: Path) -> None:
    source = tmp_path / "disc.png"
    disc_on_a_gradient().save(source)

    cutout = remove_background(
        source, options=RemovalOptions(keep="the red disc", quality="low")
    )

    result = Image.open(io.BytesIO(cutout.png))
    alpha = result.getchannel("A")
    assert result.size == (1200, 800)
    assert str(cutout.model_size) == "1200x800"
    assert alpha.getpixel((600, 400)) == 255
    assert alpha.getpixel((20, 20)) == 0
    assert alpha.getpixel((1180, 780)) == 0
