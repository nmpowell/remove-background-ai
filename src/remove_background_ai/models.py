from pydantic import BaseModel, ConfigDict, PositiveInt


class ImageSize(BaseModel):
    """Width and height of an image in pixels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    width: PositiveInt
    height: PositiveInt

    def __str__(self) -> str:
        return f"{self.width}x{self.height}"
