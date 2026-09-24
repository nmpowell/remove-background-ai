import io
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image, ImageCms
from pydantic import ValidationError

from remove_background_ai import remove_background
from remove_background_ai.errors import EditError, InvalidInputError
from remove_background_ai.models import ImageSize, RemovalOptions

from .conftest import FakeEditor, cutout_png, png_bytes

SOURCE_RGB = (200, 30, 30)
WriteImage = Callable[..., Path]


def icc(colour_space: ImageCms._CmsProfileCompatible) -> bytes:
    return ImageCms.ImageCmsProfile(ImageCms.createProfile(colour_space)).tobytes()


def jpeg_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


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


class TestRemoveBackgroundRejectsAnUnusableModelImage:
    @pytest.mark.parametrize(
        "model_image, message",
        [
            (b"not an image", "could not be decoded"),
            (jpeg_bytes(Image.new("RGB", (1024, 1024))), "JPEG, not PNG"),
            (cutout_png(1536, 1024), "1536x1024, not the requested 1024x1024"),
            (png_bytes(Image.new("RGB", (1024, 1024))), "no transparent pixels"),
            (
                png_bytes(Image.new("RGBA", (1024, 1024), (0, 0, 0, 255))),
                "no transparent pixels",
            ),
            (
                png_bytes(Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))),
                "entirely transparent",
            ),
        ],
        ids=["garbage", "jpeg", "wrong-size", "no-alpha", "opaque", "transparent"],
    )
    @pytest.mark.parametrize("mode", ["original", "generated"])
    def test_raises_edit_error(
        self, write_image: WriteImage, model_image: bytes, message: str, mode: str
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), SOURCE_RGB))
        editor = FakeEditor(response_png=model_image)

        with pytest.raises(EditError, match=message):
            remove_background(
                source,
                editor=editor,
                options=RemovalOptions.model_validate({"mode": mode}),
            )


class TestRemoveBackgroundRefusesAnUnusableSource:
    def test_refuses_a_file_that_is_not_an_image(
        self, editor: FakeEditor, tmp_path: Path
    ) -> None:
        source = tmp_path / "notes.png"
        source.write_text("not an image")

        with pytest.raises(InvalidInputError, match="cannot be read as an image"):
            remove_background(source, editor=editor)

        assert editor.requests == []

    def test_refuses_an_animated_image(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        frames = [Image.new("RGB", (1024, 1024), colour) for colour in ("red", "blue")]
        source = write_image(
            frames[0], "animation.gif", save_all=True, append_images=frames[1:]
        )

        with pytest.raises(InvalidInputError, match="animated"):
            remove_background(source, editor=editor)

        assert editor.requests == []


class TestCutoutMetadata:
    def test_describes_the_request_and_result_without_the_image(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1920, 1080), SOURCE_RGB))

        cutout = remove_background(
            source, editor=editor, options=RemovalOptions(quality="medium")
        )

        assert cutout.model_dump(mode="json") == {
            "mode": "original",
            "model": "gpt-image-2.5-sunburst-2026-09-08",
            "quality": "medium",
            "source_size": "1920x1080",
            "model_size": "1920x1088",
            "output_size": "1920x1080",
            "request_id": "req_fake",
            "usage": None,
        }

    def test_generated_mode_reports_the_model_size_as_the_output_size(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1920, 1080), SOURCE_RGB))

        cutout = remove_background(
            source, editor=editor, options=RemovalOptions(mode="generated")
        )

        assert cutout.output_size == ImageSize(width=1920, height=1088)


class TestImageSize:
    def test_parses_the_width_x_height_form(self) -> None:
        assert ImageSize.model_validate("1920x1080") == ImageSize(
            width=1920, height=1080
        )

    @pytest.mark.parametrize("text", ["1920", "1920xtall", "0x1080"])
    def test_refuses_text_that_is_not_a_positive_width_x_height(
        self, text: str
    ) -> None:
        with pytest.raises(ValidationError):
            ImageSize.model_validate(text)


class TestRemoveBackgroundArguments:
    def test_requires_a_path_not_a_string(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), SOURCE_RGB))

        with pytest.raises(ValidationError, match="instance of Path"):
            remove_background(str(source), editor=editor)  # type: ignore[arg-type]

    def test_requires_removal_options_not_a_dict(
        self, editor: FakeEditor, write_image: WriteImage
    ) -> None:
        source = write_image(Image.new("RGB", (1024, 1024), SOURCE_RGB))

        with pytest.raises(ValidationError, match="instance of RemovalOptions"):
            remove_background(source, editor=editor, options={"quality": "low"})  # type: ignore[arg-type]
