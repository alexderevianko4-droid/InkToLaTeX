"""Abstract base class for handwriting/math recognizers."""

from abc import ABC, abstractmethod


class Recognizer(ABC):
    """Base class that all recognizers must implement."""

    @abstractmethod
    async def recognize(self, png_base64: str) -> str:
        """Takes base64-encoded PNG, returns text with LaTeX formulas.

        Args:
            png_base64: A base64-encoded PNG image string (without data URI prefix).

        Returns:
            Recognized text with inline math wrapped in $...$ and display math
            wrapped in $$...$$.
        """
        ...
