import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from apps.api.ai_providers.openai import OpenAIProvider
from apps.api.ai_providers.base import AIResponse

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
            "Hello OpenAI", 
            system_prompt="You are a bot",
            temperature=0.7
        )
        
        assert isinstance(response, AIResponse)
        assert response.content == "OpenAI response"
        assert response.metadata["provider"] == "openai"
        
        # Verify messages sent to OpenAI
        mock_client.chat.completions.create.assert_called_once()
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs["messages"]
        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "You are a bot"}
        assert messages[1] == {"role": "user", "content": "Hello OpenAI"}
        assert kwargs["temperature"] == 0.7

@pytest.mark.asyncio
async def test_openai_provider_generate_image_not_implemented():
    with patch("apps.api.ai_providers.openai.AsyncOpenAI"):
        provider = OpenAIProvider(api_key="sk-test")
        with pytest.raises(NotImplementedError):
            await provider.generate_image("A cat")

def test_openai_provider_factory_integration():
    from apps.api.ai_providers.factory import AIProviderFactory
    from apps.api.ai_providers.openai import OpenAIProvider
    from pydantic import SecretStr
    
    mock_settings = MagicMock()
    mock_settings.openai_api_key = SecretStr("sk-factory-test")
    mock_settings.openai_model = "gpt-4-turbo"
    
    with patch("apps.api.ai_providers.factory.get_settings", return_value=mock_settings), \
         patch("apps.api.ai_providers.openai.AsyncOpenAI"):
        provider = AIProviderFactory.create("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.model == "gpt-4-turbo"
