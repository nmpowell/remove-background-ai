from collections.abc import Callable
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from remove_background_ai import remove_background
from remove_background_ai.models import RemovalOptions

from .conftest import FakeEditor

WriteImage = Callable[..., Path]


@pytest.fixture
def source(write_image: WriteImage) -> Path:
    return write_image(Image.new("RGB", (1024, 1024), "white"))


class TestPrompt:
    def test_asks_for_the_main_subject_by_default(
        self, editor: FakeEditor, source: Path
    ) -> None:
        remove_background(source, editor=editor)

        prompt = editor.requests[0].prompt
        assert "KEEP: the main subject." in prompt
        assert "REMOVE: everything else." in prompt
        assert "fully transparent" in prompt

    def test_describes_what_to_keep_and_remove(
        self, editor: FakeEditor, source: Path
    ) -> None:
        options = RemovalOptions(
            keep="  the red backpack, both straps ", remove="the stand and its shadow"
        )

        remove_background(source, editor=editor, options=options)

        prompt = editor.requests[0].prompt
        assert "KEEP: the red backpack, both straps." in prompt
        assert "REMOVE: the stand and its shadow." in prompt


class TestRemovalOptions:
    @pytest.mark.parametrize("field", ["keep", "remove"])
    def test_refuses_a_blank_description(self, field: str) -> None:
        with pytest.raises(ValidationError, match="at least 1 character"):
            RemovalOptions.model_validate({field: "   "})

    def test_refuses_a_description_over_10000_characters(self) -> None:
        with pytest.raises(ValidationError, match="at most 10000 characters"):
            RemovalOptions(keep="x" * 10_001)
