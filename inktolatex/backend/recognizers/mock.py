"""Mock recognizer for offline testing and development without API keys."""

import base64
import hashlib
import logging

from .base import Recognizer

logger = logging.getLogger(__name__)

SAMPLE_FORMULAS = [
    "$x^2 + y^2 = z^2$",
    r"$\frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$",
    r"$\int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$",
    r"$\sum_{k=1}^{n} k^2 = \frac{n(n+1)(2n+1)}{6}$",
    r"Нехай $A = \begin{pmatrix} a & b \\ c & d \end{pmatrix}$, тоді $\det(A) = ad - bc$",
    r"$\lim_{x \to 0} \frac{\sin x}{x} = 1$",
]


class MockRecognizer(Recognizer):
    """Recognizer that deterministically maps image data to one of several

    standard mathematical formulas for testing purposes.
    """

    async def recognize(self, png_base64: str) -> str:
        if not png_base64:
            raise RuntimeError("Empty image data provided.")

        try:
            raw = base64.b64decode(png_base64)
        except Exception:
            raw = png_base64.encode("utf-8")

        # Deterministic choice based on hash of the drawing
        idx = int(hashlib.md5(raw).hexdigest(), 16) % len(SAMPLE_FORMULAS)
        result = SAMPLE_FORMULAS[idx]
        logger.info("MockRecognizer recognized formula #%d: %s", idx, result)
        return result
