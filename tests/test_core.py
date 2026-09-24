import io
from collections.abc import Callable
from pathlib import Path

from PIL import Image

from remove_background_ai import remove_background
from remove_background_ai.models import ImageSize

from .conftest import FakeEditor

SOURCE_RGB = (200, 30, 30)
WriteImage = Callable[..., Path]


def decode(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


class TestRemoveBackground:
    def test_puts_the_model_alpha_on_the_source_pixels(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), SOURCE_RGB))

        cutout = remove_background(source, editor=editor)

        result = decode(cutout.png)
        assert result.mode == "RGBA"
        assert result.size == (1024, 1024)
        assert result.getpixel((512, 512)) == (*SOURCE_RGB, 255)
        assert result.getpixel((0, 0)) == (*SOURCE_RGB, 0)

    def test_returns_the_source_size_when_the_model_needs_another(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1920, 1080), SOURCE_RGB))

        cutout = remove_background(source, editor=editor)

        result = decode(cutout.png)
        assert editor.requests[0].size == ImageSize(width=1920, height=1088)
        assert result.size == (1920, 1080)
        assert result.getpixel((960, 540)) == (*SOURCE_RGB, 255)
        assert result.getpixel((5, 5)) == (*SOURCE_RGB, 0)
