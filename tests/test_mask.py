import io
from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image

from remove_background_ai import remove_background
from remove_background_ai.errors import InvalidInputError

from .conftest import FakeEditor

WriteImage = Callable[..., Path]


def centre_mask(width: int, height: int, keep_level: int = 255) -> Image.Image:
    """Black, with a centre rectangle at keep_level."""
    mask = Image.new("L", (width, height), 0)
    mask.paste(keep_level, (width // 4, height // 4, 3 * width // 4, 3 * height // 4))
    return mask


@pytest.fixture
def source(write_image: WriteImage) -> Path:
    return write_image(Image.new("RGB", (1920, 1080), "white"))


class TestMask:
    def test_sends_the_white_area_as_the_protected_area_at_the_model_size(
        self, editor: FakeEditor, source: Path, write_image: WriteImage
    ) -> None:
        mask = write_image(centre_mask(1920, 1080), "mask.png")

        remove_background(source, editor=editor, mask=mask)

        sent_mask = editor.requests[0].mask
        assert sent_mask is not None
        edit_mask = Image.open(io.BytesIO(sent_mask))
        assert edit_mask.format == "PNG"
        assert edit_mask.size == (1920, 1088)
        assert edit_mask.getchannel("A").getpixel((960, 544)) == 255
        assert edit_mask.getchannel("A").getpixel((10, 10)) == 0

    def test_refuses_a_mask_that_does_not_match_the_source_size(
        self, editor: FakeEditor, source: Path, write_image: WriteImage
    ) -> None:
        mask = write_image(centre_mask(1080, 1920), "mask.png")

        with pytest.raises(
            InvalidInputError, match="1080x1920 but the image is 1920x1080"
        ):
            remove_background(source, editor=editor, mask=mask)

        assert editor.requests == []

    @pytest.mark.parametrize("level, expected_alpha", [(128, 255), (127, 0)])
    def test_keeps_grey_at_or_above_half_intensity(
        self,
        editor: FakeEditor,
        source: Path,
        write_image: WriteImage,
        level: int,
        expected_alpha: int,
    ) -> None:
        mask = write_image(centre_mask(1920, 1080, keep_level=level), "mask.png")

        remove_background(source, editor=editor, mask=mask)

        sent_mask = editor.requests[0].mask
        assert sent_mask is not None
        alpha = Image.open(io.BytesIO(sent_mask)).getchannel("A")
        assert alpha.getpixel((960, 544)) == expected_alpha

    def test_refuses_a_mask_that_is_not_an_image(
        self, editor: FakeEditor, source: Path, tmp_path: Path
    ) -> None:
        mask = tmp_path / "mask.png"
        mask.write_text("not an image")

        with pytest.raises(InvalidInputError, match="cannot be read as an image"):
            remove_background(source, editor=editor, mask=mask)

    def test_tells_the_model_the_mask_marks_the_subject(
        self, editor: FakeEditor, source: Path, write_image: WriteImage
    ) -> None:
        mask = write_image(centre_mask(1920, 1080), "mask.png")

        remove_background(source, editor=editor, mask=mask)

        assert "mask" in editor.requests[0].prompt
