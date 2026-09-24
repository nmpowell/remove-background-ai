import io
from pathlib import Path

import pytest
from PIL import Image

from remove_background_ai.models import EditRequest, EditResponse

MODEL_RGB = (0, 255, 0)


def png_bytes(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def cutout_png(width: int, height: int) -> bytes:
    """A model-style cutout: green, opaque in the centre half, transparent around it."""
    image = Image.new("RGBA", (width, height), (*MODEL_RGB, 0))
    image.paste(
        (*MODEL_RGB, 255), (width // 4, height // 4, 3 * width // 4, 3 * height // 4)
    )
    return png_bytes(image)


class FakeEditor:
    """Stands in for the OpenAI API: records requests and returns a centred cutout."""

    def __init__(self, response_png: bytes | None = None) -> None:
        self.requests: list[EditRequest] = []
        self._response_png = response_png

    def edit(self, request: EditRequest) -> EditResponse:
        self.requests.append(request)
        png = self._response_png or cutout_png(request.size.width, request.size.height)
        return EditResponse(image=png, request_id="req_fake", usage=None)


@pytest.fixture
def editor() -> FakeEditor:
    return FakeEditor()


@pytest.fixture
def write_image(tmp_path: Path):  # type: ignore[no-untyped-def]
    def write(
        image: Image.Image, name: str = "source.png", **save_options: object
    ) -> Path:
        path = tmp_path / name
        image.save(path, **save_options)
        return path

    return write
