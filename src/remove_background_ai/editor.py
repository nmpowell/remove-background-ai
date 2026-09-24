import base64
from typing import Protocol

from openai import APIStatusError, OpenAI, OpenAIError, omit

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
                input_fidelity="high",
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
        if not response.data or response.data[0].b64_json is None:
            raise EditError("OpenAI image edit response has no image data")
        try:
            image = base64.b64decode(response.data[0].b64_json, validate=True)
        except ValueError:
            raise EditError("OpenAI image edit response has invalid base64") from None
        return EditResponse(
            image=image,
            request_id=response._request_id,
            usage=Usage.model_validate(response.usage.model_dump())
            if response.usage is not None
            else None,
        )
