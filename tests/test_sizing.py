import pytest
from hypothesis import given
from hypothesis import strategies as st

from remove_background_ai.errors import InvalidInputError
from remove_background_ai.models import ImageSize
from remove_background_ai.sizing import model_size_for


class TestModelSizeFor:
    @pytest.mark.parametrize(
        "width, height",
        [
            (1024, 1024),
            (1536, 1024),
            (1024, 1536),
        ],
    )
    def test_keeps_a_size_the_model_can_already_produce(
        self, width: int, height: int
    ) -> None:
        source = ImageSize(width=width, height=height)

        assert model_size_for(source) == source

    def test_rounds_edges_to_multiples_of_16_keeping_the_aspect_ratio(self) -> None:
        # 1080 / 16 = 67.5; 1920x1088 is closer in aspect than 1920x1072.
        source = ImageSize(width=1920, height=1080)

        assert model_size_for(source) == ImageSize(width=1920, height=1088)

    def test_scales_a_small_image_up_to_the_minimum_area(self) -> None:
        # sqrt(655,360) = 809.5; of 800 and 816 only 816x816 reaches the minimum.
        source = ImageSize(width=512, height=512)

        assert model_size_for(source) == ImageSize(width=816, height=816)

    @pytest.mark.parametrize(
        "source, expected",
        [
            # Ideal 2351.5x1567.7; 2352x1568 is over the cap, 2336x1552 has the
            # smallest aspect error of the rest.
            (ImageSize(width=6000, height=4000), ImageSize(width=2336, height=1552)),
            # Valid but experimental; 2560x1440 is exactly the cap.
            (ImageSize(width=3840, height=2160), ImageSize(width=2560, height=1440)),
        ],
    )
    def test_scales_a_large_image_down_to_the_largest_standard_area(
        self, source: ImageSize, expected: ImageSize
    ) -> None:
        assert model_size_for(source) == expected

    @pytest.mark.parametrize(
        "source",
        [ImageSize(width=3072, height=768), ImageSize(width=100, height=301)],
    )
    def test_refuses_an_aspect_ratio_beyond_3_to_1(self, source: ImageSize) -> None:
        with pytest.raises(InvalidInputError, match="aspect ratio"):
            model_size_for(source)


@st.composite
def sources_within_3_to_1(draw: st.DrawFn) -> ImageSize:
    short = draw(st.integers(min_value=1, max_value=12_000))
    long = draw(st.integers(min_value=short, max_value=3 * short))
    return draw(
        st.sampled_from(
            [ImageSize(width=long, height=short), ImageSize(width=short, height=long)]
        )
    )


@given(sources_within_3_to_1())
def test_every_source_within_3_to_1_maps_to_a_producible_size(
    source: ImageSize,
) -> None:
    size = model_size_for(source)

    assert size.width % 16 == 0
    assert size.height % 16 == 0
    assert 655_360 <= size.width * size.height <= 3_686_400
    assert max(size.width, size.height) <= 3 * min(size.width, size.height)
