"""Unit tests for ImageRetriever."""

import httpx
import pytest
from respx import MockRouter

from apps.api.workflow.retriever import ImageRetriever


@pytest.mark.asyncio
async def test_image_retriever_retrieve_success(respx_mock: MockRouter) -> None:
    url = "https://example.com/image.png"
    image_content = b"fake-image-data"
    respx_mock.get(url).mock(return_value=httpx.Response(200, content=image_content))

    retriever = ImageRetriever()
    result = await retriever.retrieve(url)

    assert result == image_content
    assert respx_mock.calls.called


@pytest.mark.asyncio
async def test_image_retriever_retrieve_failure(respx_mock: MockRouter) -> None:
    url = "https://example.com/notfound.png"
    respx_mock.get(url).mock(return_value=httpx.Response(404))

    retriever = ImageRetriever()
    with pytest.raises(httpx.HTTPStatusError):
        await retriever.retrieve(url)


def test_image_retriever_get_mime_type() -> None:
    retriever = ImageRetriever()
    assert retriever.get_mime_type("image/jpeg") == "image/jpeg"
    assert retriever.get_mime_type("application/json") == "image/png"
    assert retriever.get_mime_type(None) == "image/png"


def test_image_retriever_get_extension() -> None:
    retriever = ImageRetriever()
    assert retriever.get_extension("image/jpeg") == ".jpg"
    assert retriever.get_extension("image/png") == ".png"
    assert retriever.get_extension("image/webp") == ".webp"
    assert retriever.get_extension("unknown/type") == ".png"
