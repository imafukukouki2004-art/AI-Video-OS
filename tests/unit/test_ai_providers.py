import pytest

from apps.api.ai_providers import AIImageResponse, AIProviderFactory, AIResponse, MockAIProvider


@pytest.mark.asyncio
async def test_mock_ai_provider_generate_text():
    provider = MockAIProvider()
    response = await provider.generate_text("Hello")
    
    assert isinstance(response, AIResponse)
    assert "Hello" in response.content
    assert response.metadata["provider"] == "mock"

@pytest.mark.asyncio
async def test_mock_ai_provider_generate_image():
    provider = MockAIProvider()
    response = await provider.generate_image("A cat")
    
    assert isinstance(response, AIImageResponse)
    assert response.image_url == "https://example.com/mock-image.png"
    assert response.metadata["provider"] == "mock"

def test_ai_provider_factory_create_mock():
    provider = AIProviderFactory.create("mock")
    assert isinstance(provider, MockAIProvider)

def test_ai_provider_factory_create_unsupported():
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        AIProviderFactory.create("unsupported-provider")
