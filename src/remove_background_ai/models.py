from typing import Literal

from pydantic import BaseModel, ConfigDict, PositiveInt

ModelName = Literal[
    "gpt-image-2.5-sunburst-2026-09-08",
    "gpt-image-2.5-sunburst",
    "gpt-image-2.5-flare-2026-09-08",
    "gpt-image-2.5-flare",
]
Quality = Literal["low", "medium", "high", "xhigh", "max", "auto"]
OutputMode = Literal["original", "generated"]

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class ImageSize(BaseModel):
    """Width and height of an image in pixels."""

    model_config = _FROZEN

    width: PositiveInt
    height: PositiveInt

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"


class RemovalOptions(BaseModel):
    """How to remove a background."""

    model_config = _FROZEN

    model: ModelName = "gpt-image-2.5-sunburst-2026-09-08"
    quality: Quality = "high"
    mode: OutputMode = "original"
    """``original`` puts the model's alpha on the source pixels at the source size;
    ``generated`` returns the model's own PNG at the model size."""


class TokenDetails(BaseModel):
    """Image and text token counts."""

    model_config = _FROZEN

    image_tokens: int
    text_tokens: int


class Usage(BaseModel):
    """Token usage the API reported for one edit."""

    model_config = _FROZEN

    input_tokens: int
    output_tokens: int
    total_tokens: int
    input_tokens_details: TokenDetails | None = None
    output_tokens_details: TokenDetails | None = None


class EditRequest(BaseModel):
    """One image edit to send to the model."""

    model_config = _FROZEN

    image: bytes
    mask: bytes | None = None
    prompt: str
    model: ModelName
    quality: Quality
    size: ImageSize


class EditResponse(BaseModel):
    """The image the model returned, with its request metadata."""

    model_config = _FROZEN

    image: bytes
    request_id: str | None
    usage: Usage | None


class Cutout(BaseModel):
    """A transparent PNG with the background removed."""

    model_config = _FROZEN

    png: bytes
