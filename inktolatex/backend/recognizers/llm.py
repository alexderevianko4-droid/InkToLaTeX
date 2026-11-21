"""Vision LLM recognizer using an OpenAI-compatible chat completions API."""

import os
import logging

import httpx

from .base import Recognizer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an OCR assistant. Recognize the handwritten text and math in this "
    "image. Output the text as-is, but wrap each mathematical formula in LaTeX: "
    "inline formulas in $...$ and display formulas in $$...$$. Only output the "
    "recognized text, nothing else."
)


class LLMRecognizer(Recognizer):
    """Recognizer that uses a vision-capable LLM via an OpenAI-compatible API.

    Configuration is read from environment variables:
        - LLM_API_KEY: API key for authentication (required).
        - LLM_API_BASE: Base URL of the API (default: https://api.openai.com/v1).
        - LLM_MODEL: Model identifier (default: gpt-4o).
    """

    def __init__(self) -> None:
        self.api_key: str = os.environ.get("LLM_API_KEY", "")
        self.api_base: str = os.environ.get(
            "LLM_API_BASE", "https://api.openai.com/v1"
        ).rstrip("/")
        self.model: str = os.environ.get("LLM_MODEL", "gpt-4o")

        if not self.api_key:
            logger.warning(
                "LLM_API_KEY is not set. LLM recognition will fail until it is configured."
            )

    async def recognize(self, png_base64: str) -> str:
        """Send a base64-encoded PNG to a vision LLM and return recognized text.

        Args:
            png_base64: A base64-encoded PNG image string (without data URI prefix).

        Returns:
            Recognized text with inline math in $...$ and display math in $$...$$.

        Raises:
            RuntimeError: If the API returns an error or is unreachable.
        """
        if not self.api_key:
            raise RuntimeError(
                "LLM_API_KEY is not configured. "
                "Set the LLM_API_KEY environment variable."
            )

        url = f"{self.api_base}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{png_base64}",
                            },
                        },
                    ],
                },
            ],
            "max_tokens": 4096,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            logger.error("LLM API request failed: %s", exc)
            raise RuntimeError(f"Failed to connect to LLM API: {exc}") from exc

        if response.status_code != 200:
            logger.error(
                "LLM API returned status %d: %s",
                response.status_code,
                response.text,
            )
            raise RuntimeError(
                f"LLM API error (HTTP {response.status_code}): {response.text}"
            )

        data = response.json()

        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            logger.error("Unexpected LLM API response structure: %s", data)
            raise RuntimeError(
                f"Unexpected response from LLM API: {data}"
            ) from exc

        return content.strip()
