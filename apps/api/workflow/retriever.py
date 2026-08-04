"""Utility for retrieving image data from external URLs."""

import logging

import httpx

logger = logging.getLogger(__name__)


class ImageRetriever:
    """Retrieves image data from external sources."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout

    async def retrieve(self, url: str) -> bytes:
        """
        Download image data from a URL.
        Returns the raw bytes of the image.
        """
        logger.info(f"Retrieving image from URL: {url}")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.content

    def get_mime_type(self, content_type_header: str | None) -> str:
        """
        Determine the MIME type from the Content-Type header.
        Defaults to image/png if not provided or recognized.
        """
        if not content_type_header:
            return "image/png"

        # Basic validation: ensure it starts with image/
        if content_type_header.startswith("image/"):
            return content_type_header

        return "image/png"

    def get_extension(self, mime_type: str) -> str:
        """Return the file extension based on the MIME type."""
        mapping = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }
        return mapping.get(mime_type, ".png")
