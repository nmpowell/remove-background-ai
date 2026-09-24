from email import message_from_bytes
from email.message import Message

import httpx2 as httpx
import openai
import pytest

from remove_background_ai.editor import OpenAIImageEditor
from remove_background_ai.errors import EditError
from remove_background_ai.models import EditRequest, ImageSize


def client_returning(
    response: httpx.Response, received: list[httpx.Request]
) -> openai.OpenAI:
    def handler(request: httpx.Request) -> httpx.Response:
        received.append(request)
        return response

    return openai.OpenAI(
        api_key="sk-test",
        base_url="https://api.test/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def multipart_parts(request: httpx.Request) -> dict[str, Message]:
    message = message_from_bytes(
        b"Content-Type: "
        + request.headers["content-type"].encode()
        + b"\r\nMIME-Version: 1.0\r\n\r\n"
        + request.content
    )
    return {
        part.get_param("name", header="content-disposition"): part
        for part in message.get_payload()
    }


def edit_request(**overrides: object) -> EditRequest:
    fields: dict[str, object] = {
        "image": b"source-png",
        "prompt": "Remove the background",
        "model": "gpt-image-2.5-flare",
        "quality": "high",
        "size": "1024x1024",
    }
    return EditRequest.model_validate(fields | overrides)


class TestOpenAIImageEditor:
    def test_missing_api_key_raises_edit_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with pytest.raises(EditError, match="OPENAI_API_KEY"):
            OpenAIImageEditor()

    def test_sends_a_single_edit_and_returns_the_image_and_request_id(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(
                200,
                json={"created": 0, "data": [{"b64_json": "aW1hZ2UtcG5n"}]},
                headers={"x-request-id": "req_123"},
            ),
            received,
        )
        request = EditRequest(
            image=b"source-png",
            prompt="Remove the background",
            model="gpt-image-2.5-sunburst-2026-09-08",
            quality="high",
            size=ImageSize(width=1024, height=1536),
        )

        result = OpenAIImageEditor(client).edit(request)

        assert result.image == b"image-png"
        assert result.request_id == "req_123"
        assert result.usage is None
        assert len(received) == 1
        assert received[0].method == "POST"
        assert received[0].url == "https://api.test/v1/images/edits"
        parts = multipart_parts(received[0])
        assert set(parts) == {
            "model",
            "image",
            "prompt",
            "background",
            "output_format",
            "quality",
            "size",
            "n",
        }
        assert (
            parts["model"].get_payload(decode=True)
            == b"gpt-image-2.5-sunburst-2026-09-08"
        )
        assert parts["image"].get_filename() == "image.png"
        assert parts["image"].get_content_type() == "image/png"
        assert parts["image"].get_payload(decode=True) == b"source-png"
        assert parts["prompt"].get_payload(decode=True) == b"Remove the background"
        assert parts["background"].get_payload(decode=True) == b"transparent"
        assert parts["output_format"].get_payload(decode=True) == b"png"
        assert parts["quality"].get_payload(decode=True) == b"high"
        assert parts["size"].get_payload(decode=True) == b"1024x1536"
        assert parts["n"].get_payload(decode=True) == b"1"

    def test_sends_the_mask_when_present(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(200, json={"created": 0, "data": [{"b64_json": "cG5n"}]}),
            received,
        )
        request = EditRequest(
            image=b"source-png",
            mask=b"mask-png",
            prompt="Remove the background",
            model="gpt-image-2.5-flare",
            quality="max",
            size=ImageSize(width=1536, height=1024),
        )

        result = OpenAIImageEditor(client).edit(request)

        assert result.image == b"png"
        assert result.request_id is None
        assert len(received) == 1
        parts = multipart_parts(received[0])
        assert "mask" in parts
        assert parts["mask"].get_filename() == "mask.png"
        assert parts["mask"].get_content_type() == "image/png"
        assert parts["mask"].get_payload(decode=True) == b"mask-png"

    def test_returns_usage_with_nested_token_details(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": "cG5n"}],
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 34,
                        "total_tokens": 46,
                        "input_tokens_details": {"image_tokens": 10, "text_tokens": 2},
                        "output_tokens_details": {"image_tokens": 30, "text_tokens": 4},
                    },
                },
            ),
            received,
        )
        request = EditRequest(
            image=b"source-png",
            prompt="Remove the background",
            model="gpt-image-2.5-flare",
            quality="max",
            size=ImageSize(width=1024, height=1024),
        )

        result = OpenAIImageEditor(client).edit(request)

        assert result.usage is not None
        assert result.usage.input_tokens == 12
        assert result.usage.output_tokens == 34
        assert result.usage.total_tokens == 46
        assert result.usage.input_tokens_details is not None
        assert result.usage.input_tokens_details.image_tokens == 10
        assert result.usage.input_tokens_details.text_tokens == 2
        assert result.usage.output_tokens_details is not None
        assert result.usage.output_tokens_details.image_tokens == 30
        assert result.usage.output_tokens_details.text_tokens == 4

    def test_ignores_usage_fields_it_does_not_know(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": "cG5n"}],
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 34,
                        "total_tokens": 46,
                        "cached_tokens": 5,
                    },
                },
            ),
            received,
        )

        result = OpenAIImageEditor(client).edit(edit_request())

        assert result.usage is not None
        assert result.usage.total_tokens == 46

    def test_drops_usage_it_cannot_read(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(
                200,
                json={
                    "created": 0,
                    "data": [{"b64_json": "cG5n"}],
                    "usage": {"total_tokens": 46},
                },
            ),
            received,
        )

        result = OpenAIImageEditor(client).edit(edit_request())

        assert result.image == b"png"
        assert result.usage is None

    def test_api_status_error_reports_safe_message_status_and_request_id(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Mask is invalid",
                        "image_data": "source-png",
                    }
                },
                headers={"x-request-id": "req_bad"},
            ),
            received,
        )
        request = edit_request()

        with pytest.raises(EditError) as caught:
            OpenAIImageEditor(client).edit(request)

        assert "400" in str(caught.value)
        assert "Mask is invalid" in str(caught.value)
        assert "req_bad" in str(caught.value)
        assert "source-png" not in str(caught.value)
        assert "sk-test" not in str(caught.value)
        assert len(received) == 1

    def test_api_message_never_contains_the_api_key(self) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(400, json={"error": {"message": "Bad key sk-test"}}),
            received,
        )

        with pytest.raises(EditError, match=r"Bad key \[redacted\]"):
            OpenAIImageEditor(client).edit(edit_request())

    @pytest.mark.parametrize(
        "failure, message",
        [
            (httpx.ConnectError("connection lost"), "Connection error"),
            (httpx.ReadTimeout("timed out"), "Request timed out"),
        ],
    )
    def test_transport_failures_raise_edit_error_naming_the_cause(
        self, failure: Exception, message: str
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise failure

        client = openai.OpenAI(
            api_key="sk-test",
            base_url="https://api.test/v1",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        request = edit_request()

        with pytest.raises(EditError, match=message):
            OpenAIImageEditor(client).edit(request)

    @pytest.mark.parametrize(
        "data",
        [
            None,
            [],
            [{}],
            [{"b64_json": "%%%"}],
            [None],
            [{"b64_json": 123}],
            {"b64_json": "cG5n"},
            123,
        ],
        ids=[
            "null-data",
            "empty-data",
            "missing-base64",
            "invalid-base64",
            "null-image",
            "numeric-base64",
            "object-data",
            "numeric-data",
        ],
    )
    def test_malformed_image_response_raises_edit_error(self, data: object) -> None:
        received: list[httpx.Request] = []
        client = client_returning(
            httpx.Response(200, json={"created": 0, "data": data}), received
        )
        request = edit_request()

        with pytest.raises(EditError, match="OpenAI image edit response"):
            OpenAIImageEditor(client).edit(request)
