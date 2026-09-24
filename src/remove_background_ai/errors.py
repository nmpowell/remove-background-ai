class RemoveBackgroundError(Exception):
    """Base class for every error this package raises."""


class InvalidInputError(RemoveBackgroundError, ValueError):
    """An input image, mask or setting cannot be sent to the model."""


class EditError(RemoveBackgroundError):
    """The OpenAI request failed or returned an unusable image."""
