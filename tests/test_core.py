import io
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageCms

from remove_background_ai import remove_background
from remove_background_ai.models import ImageSize, RemovalOptions

from .conftest import FakeEditor, cutout_png

SOURCE_RGB = (200, 30, 30)
WriteImage = Callable[..., Path]


def icc(colour_space: ImageCms._CmsProfileCompatible) -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile(colour_space)).tobytes()


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

    def test_applies_the_exif_orientation_before_sizing(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        stored = Image.new("RGB", (1200, 800), SOURCE_RGB)
        exif = stored.getexif()
        exif[0x0112] = 6  # Orientation: rotate 90° clockwise to display.
        source = write_image(stored, "photo.jpg", exif=exif)

        cutout = remove_background(source, editor=editor)

        assert editor.requests[0].size == ImageSize(width=800, height=1200)
        assert decode(cutout.png).size == (800, 1200)

    def test_never_makes_a_semi_transparent_source_more_opaque(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGBA", (1024, 1024), (*SOURCE_RGB, 128)))

        cutout = remove_background(source, editor=editor)

        result = decode(cutout.png)
        assert result.getpixel((512, 512)) == (*SOURCE_RGB, 128)
        assert result.getpixel((0, 0)) == (*SOURCE_RGB, 0)

    def test_keeps_an_rgb_colour_profile(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        profile = icc("sRGB")
        source = write_image(
            Image.new("RGB", (1024, 1024), SOURCE_RGB), icc_profile=profile
        )

        cutout = remove_background(source, editor=editor)

        assert decode(cutout.png).info.get("icc_profile") == profile

    def test_drops_a_colour_profile_that_does_not_describe_rgb(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(
            Image.new("RGB", (1024, 1024), SOURCE_RGB), icc_profile=icc("LAB")
        )

        cutout = remove_background(source, editor=editor)

        assert "icc_profile" not in decode(cutout.png).info

    @pytest.mark.parametrize(
        "image, name, expected_rgb",
        [
            (Image.new("L", (1024, 1024), 128), "grey.png", (128, 128, 128)),
            (
                Image.new("CMYK", (1024, 1024), (0, 255, 255, 0)),
                "cmyk.jpg",
                (255, 0, 0),
            ),
            (
                Image.new("RGB", (1024, 1024), SOURCE_RGB).quantize(),
                "palette.png",
                SOURCE_RGB,
            ),
        ],
    )
    def test_writes_8_bit_rgba_from_any_colour_mode(
        self,
        editor: FakeEditor,
        write_image: WriteImage,
        image: Image.Image,
        name: str,
        expected_rgb: tuple[int, int, int],
    ) -> None:
        source = write_image(image, name)

        cutout = remove_background(source, editor=editor)

        result = decode(cutout.png)
        assert result.mode == "RGBA"
        assert result.getpixel((512, 512)) == (*expected_rgb, 255)

    def test_generated_mode_returns_the_model_png_unchanged(
        self, write_image: WriteImage
    ) -> None:
        model_png = cutout_png(1920, 1088)
        editor = FakeEditor(response_png=model_png)
        source = write_image(Image.new("RGB", (1920, 1080), SOURCE_RGB))

        cutout = remove_background(
            source, editor=editor, options=RemovalOptions(mode="generated")
        )

        assert cutout.png == model_png
