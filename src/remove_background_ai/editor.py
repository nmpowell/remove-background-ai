import base64
from typing import Protocol

from openai import APIStatusError, OpenAI, OpenAIError, omit
from pydantic import ValidationError

from .errors import EditError
from .models import EditRequest, EditResponse, Usage


class ImageEditor(Protocol):
    """Sends one edit to an image model and returns its result."""

    def edit(self, request: EditRequest) -> EditResponse: ...


class OpenAIImageEditor:
    """Send image edits through the OpenAI SDK."""

    def __init__(self, client: OpenAI | None = None) -> None:
        if client is None:
            try:
                client = OpenAI(timeout=300.0, max_retries=2)
            except OpenAIError:
                raise EditError("Set OPENAI_API_KEY to use the image editor") from None
        self._client = client

    def edit(self, request: EditRequest) -> EditResponse:
        """Send one image edit and return the decoded result."""
        try:
            response = self._client.images.edit(
                model=request.model,
                image=("image.png", request.image, "image/png"),
                mask=("mask.png", request.mask, "image/png")
                if request.mask is not None
                else omit,
                prompt=request.prompt,
                background="transparent",
                output_format="png",
                quality=request.quality,
                size=str(request.size),
                n=1,
            )
        except APIStatusError as error:
            body = error.body
            message = body.get("message") if isinstance(body, dict) else None
            message = message if isinstance(message, str) else "no error message"
            details = f"OpenAI image edit failed (HTTP {error.status_code}): {message}"
            if error.request_id is not None:
                details += f" (request ID: {error.request_id})"
            raise EditError(
                details.replace(self._client.api_key, "[redacted]")
            ) from None
        except OpenAIError as error:
            raise EditError(f"OpenAI image edit request failed: {error}") from None
        # The SDK does not validate responses against its own types.
        data = response.data
        first = data[0] if isinstance(data, list) and data else None
        encoded = getattr(first, "b64_json", None)
        if not isinstance(encoded, str):
            raise EditError("OpenAI image edit response has no image data")
        try:
            image = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise EditError("OpenAI image edit response has invalid base64") from None
        return EditResponse(
            image=image, request_id=response._request_id, usage=_usage(response.usage)
        )


def _usage(reported: object) -> Usage | None:
    """Return the reported token usage, or None if it is missing or unreadable."""
    try:
        return Usage.model_validate(reported, from_attributes=True)
    except ValidationError:
        return None
