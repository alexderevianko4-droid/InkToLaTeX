"""Mathpix API recognizer for handwritten text and math."""

import os
import logging

import httpx

from .base import Recognizer

logger = logging.getLogger(__name__)

MATHPIX_ENDPOINT = "https://api.mathpix.com/v3/text"


class MathpixRecognizer(Recognizer):
    """Recognizer that uses the Mathpix OCR API.

    Requires the environment variables MATHPIX_APP_ID and MATHPIX_APP_KEY to be
    set with valid Mathpix credentials.
    """

    def __init__(self) -> None:
        self.app_id: str = os.environ.get("MATHPIX_APP_ID", "")
        self.app_key: str = os.environ.get("MATHPIX_APP_KEY", "")
        if not self.app_id or not self.app_key:
            logger.warning(
                "MATHPIX_APP_ID and/or MATHPIX_APP_KEY are not set. "
                "Mathpix recognition will fail until they are configured."
            )

    async def recognize(self, png_base64: str) -> str:
        """Send a base64-encoded PNG to Mathpix and return recognized text.

        Args:
            png_base64: A base64-encoded PNG image string (without data URI prefix).

        Returns:
            Recognized text with inline math in $...$ and display math in $$...$$.

        Raises:
            RuntimeError: If the Mathpix API returns an error or is unreachable.
        """
        if not self.app_id or not self.app_key:
            raise RuntimeError(
                "Mathpix credentials are not configured. "
                "Set MATHPIX_APP_ID and MATHPIX_APP_KEY environment variables."
            )

        headers = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "Content-Type": "application/json",
        }

        payload = {
            "src": f"data:image/png;base64,{png_base64}",
            "formats": ["text"],
            "math_inline_delimiters": ["$", "$"],
            "math_display_delimiters": ["$$", "$$"],
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    MATHPIX_ENDPOINT, headers=headers, json=payload
                )
        except httpx.HTTPError as exc:
            logger.error("Mathpix API request failed: %s", exc)
            raise RuntimeError(f"Failed to connect to Mathpix API: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "Mathpix API returned status %d: %s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(
                f"Mathpix API error (HTTP {response.status_code}): {response.text}"
            )

        data = response.json()

        if "error" in data:
            error_msg = data["error"]
            logger.error("Mathpix API error: %s", error_msg)
            raise RuntimeError(f"Mathpix API error: {error_msg}")

        text: str = data.get("text", "")
        if not text:
            logger.warning("Mathpix returned empty text for the given image.")

        return text
