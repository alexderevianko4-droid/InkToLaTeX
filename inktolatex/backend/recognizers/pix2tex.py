"""Pix2tex (LaTeX-OCR) local recognizer for mathematical expressions."""

import base64
import io
import logging
import os
from pathlib import Path
from typing import Any

from .base import Recognizer

logger = logging.getLogger(__name__)

# Height (px) of the formula after preprocessing. Try 64, 96, 128.
# Can be changed in backend/.env:  INK_TARGET_H=96
TARGET_HEIGHT: int = int(os.environ.get("INK_TARGET_H", "64"))

# Save the received and the processed image into backend/debug/.
# Disable in backend/.env:  INK_DEBUG=0
DEBUG_IMAGES: bool = os.environ.get("INK_DEBUG", "1") != "0"
DEBUG_DIR = Path(__file__).resolve().parents[1] / "debug"


def _preprocess(raw: Any, target_h: int = 64, pad: int = 16) -> Any:
    """Make a mouse drawing look like a printed formula.

    1. Transparent pixels -> white (convert("RGB") would make them black).
    2. Crop the empty canvas around the ink.
    3. Scale to a fixed height (strokes become thinner).
    4. Add a white margin.
    """
    import numpy as np
    from PIL import Image

    img = raw.convert("RGBA")
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(white, img).convert("L")

    arr = np.array(img)
    ys, xs = np.where(arr < 128)
    if len(xs) == 0:
        return img.convert("RGB")  # empty canvas, nothing to crop
    img = img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))

    w, h = img.size
    scale = target_h / h
    img = img.resize((max(1, round(w * scale)), target_h), Image.LANCZOS)

    out = Image.new("L", (img.width + 2 * pad, img.height + 2 * pad), 255)
    out.paste(img, (pad, pad))
    return out.convert("RGB")


def _save_debug(raw: Any, processed: Any) -> None:
    """Save what the backend received and what pix2tex gets. Never raises."""
    try:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        raw.save(DEBUG_DIR / "received.png")
        processed.save(DEBUG_DIR / "processed.png")
    except Exception as exc:  # debugging must never break recognition
        logger.warning("Could not save debug images: %s", exc)


class Pix2TexRecognizer(Recognizer):
    """Recognizer that uses the pix2tex (LaTeX-OCR) package for local inference.

    The pix2tex model is loaded once during initialization and reused for all
    subsequent predictions. The package must be installed separately
    (``pip install pix2tex``).
    """

    def __init__(self) -> None:
        self._model: Any = None
        try:
            from pix2tex.cli import LatexOCR  # type: ignore[import-untyped]

            self._model = LatexOCR()
            logger.info("pix2tex model loaded successfully.")
        except ImportError:
            logger.error(
                "The 'pix2tex' package is not installed. "
                "Install it with: pip install pix2tex"
            )
            raise ImportError(
                "The 'pix2tex' package is required for the Pix2TexRecognizer. "
                "Install it with: pip install pix2tex"
            )

    async def recognize(self, png_base64: str) -> str:
        """Decode a base64-encoded PNG and run pix2tex prediction.

        Args:
            png_base64: A base64-encoded PNG image string (without data URI prefix).

        Returns:
            The predicted LaTeX string wrapped in $...$ delimiters.

        Raises:
            RuntimeError: If the image cannot be decoded or prediction fails.
        """
        try:
            from PIL import Image  # noqa: F811
        except ImportError as exc:
            raise RuntimeError(
                "Pillow is required for image decoding. Install it with: pip install Pillow"
            ) from exc

        # Decode the base64 image to a PIL Image (keep the alpha channel!)
        try:
            image_bytes = base64.b64decode(png_base64)
            raw = Image.open(io.BytesIO(image_bytes))
            raw.load()
        except Exception as exc:
            logger.error("Failed to decode base64 PNG: %s", exc)
            raise RuntimeError(f"Invalid base64 PNG image: {exc}") from exc

        # Make the drawing look like a printed formula
        try:
            image = _preprocess(raw, TARGET_HEIGHT)
        except Exception as exc:
            logger.warning("Preprocessing failed, using the raw image: %s", exc)
            image = raw.convert("RGB")

        if DEBUG_IMAGES:
            _save_debug(raw, image)

        # Run pix2tex prediction
        try:
            latex: str = self._model(image)
        except Exception as exc:
            logger.error("pix2tex prediction failed: %s", exc)
            raise RuntimeError(f"pix2tex prediction failed: {exc}") from exc

        # pix2tex returns raw LaTeX without delimiters; wrap in inline math
        latex = latex.strip()
        if not latex:
            logger.warning("pix2tex returned empty LaTeX for the given image.")
            return ""

        return f"${latex}$"