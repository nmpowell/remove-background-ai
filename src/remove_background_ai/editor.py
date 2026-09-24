from typing import Protocol

from .models import EditRequest, EditResponse


class ImageEditor(Protocol):
    """Sends one edit to an image model and returns its result."""

    def edit(self, request: EditRequest) -> EditResponse: ...
