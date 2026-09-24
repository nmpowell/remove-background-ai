import remove_background_ai


def test_exports_the_public_interface() -> None:
    assert sorted(remove_background_ai.__all__) == [
        "Cutout",
        "EditError",
        "EditRequest",
        "EditResponse",
        "ImageEditor",
        "ImageSize",
        "InvalidInputError",
        "OpenAIImageEditor",
        "RemovalOptions",
        "RemoveBackgroundError",
        "Usage",
        "remove_background",
    ]
