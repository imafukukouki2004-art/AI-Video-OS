import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.ai_providers.base import AIImageResponse, AIResponse
from apps.api.ai_providers.openai import OpenAIProvider


@pytest.mark.asyncio
async def test_openai_provider_generate_text():
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = "OpenAI response"
    mock_completion.usage = MagicMock()
    mock_completion.usage.model_dump.return_value = {"prompt_tokens": 10, "completion_tokens": 5}

    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    with patch("apps.api.ai_providers.openai.AsyncOpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-test", model="gpt-4o")
        response = await provider.generate_text(
            "Hello OpenAI", system_prompt="You are a bot", temperature=0.7
        )

        assert isinstance(response, AIResponse)
        assert response.content == "OpenAI response"
        assert response.metadata["provider"] == "openai"

        # Verify messages sent to OpenAI
        mock_client.chat.completions.create.assert_called_once()
        _, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a bot"}
        assert messages[1] == {"role": "user", "content": "Hello OpenAI"}
        assert kwargs["temperature"] == 0.7


@pytest.mark.asyncio
async def test_openai_provider_generate_image():
    mock_client = MagicMock()
    mock_image_data = MagicMock()
    mock_image_data.url = "https://example.com/image.png"
    mock_image_data.b64_json = None
    mock_image_data.revised_prompt = "A cute cat"
    mock_response = MagicMock()
    mock_response.data = [mock_image_data]

    mock_client.images.generate = AsyncMock(return_value=mock_response)

    with patch("apps.api.ai_providers.openai.AsyncOpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-test")
        response = await provider.generate_image("A cat", size="1024x1024", quality="high")

        assert isinstance(response, AIImageResponse)
        assert response.image_url == "https://example.com/image.png"
        assert response.metadata["provider"] == "openai"
        assert response.metadata["revised_prompt"] == "A cute cat"

        # Verify arguments sent to OpenAI
        mock_client.images.generate.assert_called_once()
        _, kwargs = mock_client.images.generate.call_args
        assert kwargs["model"] == "gpt-image-2"
        assert kwargs["prompt"] == "A cat"
        assert kwargs["size"] == "1024x1024"
        assert kwargs["quality"] == "high"
        assert "response_format" not in kwargs


@pytest.mark.asyncio
async def test_openai_provider_decodes_base64_and_normalizes_legacy_quality():
    mock_client = MagicMock()
    mock_image_data = MagicMock(
        url=None,
        b64_json=base64.b64encode(b"generated-image").decode(),
        revised_prompt="A generated cat",
    )
    mock_response = MagicMock(data=[mock_image_data])
    mock_client.images.generate = AsyncMock(return_value=mock_response)

    with patch("apps.api.ai_providers.openai.AsyncOpenAI", return_value=mock_client):
        provider = OpenAIProvider(api_key="sk-test")
        response = await provider.generate_image(
            "A cat", response_format="b64_json", quality="standard"
        )

    assert response.image_url is None
    assert response.image_bytes == b"generated-image"
    _, kwargs = mock_client.images.generate.call_args
    assert kwargs["model"] == "gpt-image-2"
    assert kwargs["quality"] == "auto"
    assert "response_format" not in kwargs


def test_openai_provider_factory_integration():
    from pydantic import SecretStr

    from apps.api.ai_providers.factory import AIProviderFactory
    from apps.api.ai_providers.openai import OpenAIProvider

    mock_settings = MagicMock()
    mock_settings.openai_api_key = SecretStr("sk-factory-test")
    mock_settings.openai_model = "gpt-4-turbo"

    with (
        patch("apps.api.ai_providers.factory.get_settings", return_value=mock_settings),
        patch("apps.api.ai_providers.openai.AsyncOpenAI"),
    ):
        provider = AIProviderFactory.create("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4-turbo"
