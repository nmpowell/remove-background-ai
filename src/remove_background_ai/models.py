from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    StringConstraints,
    model_serializer,
    model_validator,
)

ModelName = Literal[
    "gpt-image-2.5-sunburst-2026-09-08",
    "gpt-image-2.5-sunburst",
    "gpt-image-2.5-flare-2026-09-08",
    "gpt-image-2.5-flare",
]
Quality = Literal["low", "medium", "high", "xhigh", "max", "auto"]
OutputMode = Literal["original", "generated"]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10_000)
]

_FROZEN = ConfigDict(frozen=True, extra="forbid")
# The API may add usage fields; a new one must not fail a request that was paid for.
_FROZEN_IGNORING_EXTRA = ConfigDict(frozen=True, extra="ignore")


class ImageSize(BaseModel):
    """Width and height of an image in pixels."""

    model_config = _FROZEN

    width: PositiveInt
    height: PositiveInt

    @model_validator(mode="before")
    @classmethod
    def _parse_width_x_height(cls, value: object) -> object:
        if isinstance(value, str):
            width, _, height = value.partition("x")
            return {"width": width, "height": height}
        return value

    @model_serializer(mode="plain", when_used="json")
    def _serialise_as_width_x_height(self) -> str:
        return str(self)

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
    keep: Description | None = None
    """What to keep, e.g. "the red backpack, including both straps"."""
    remove: Description | None = None
    """What to remove besides the background, e.g. "the stand and its shadow"."""


class TokenDetails(BaseModel):
    """Image and text token counts."""

    model_config = _FROZEN_IGNORING_EXTRA

    image_tokens: int
    text_tokens: int


class Usage(BaseModel):
    """Token usage the API reported for one edit."""

    model_config = _FROZEN_IGNORING_EXTRA

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
    """A transparent PNG with the background removed, and how it was made.

    ``png`` is left out of ``model_dump()`` so the metadata can be logged or
    written as JSON.
    """

    model_config = _FROZEN

    png: bytes = Field(exclude=True, repr=False)
    mode: OutputMode
    model: ModelName
    quality: Quality
    source_size: ImageSize
    model_size: ImageSize
    output_size: ImageSize
    request_id: str | None
    usage: Usage | None
