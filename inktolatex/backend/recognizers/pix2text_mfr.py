"""Pix2Text-MFR (free, local) recognizer for handwritten and printed formulas.

Model: https://huggingface.co/breezedeus/pix2text-mfr  (MIT license, TrOCR-based).
Install:  pip install "transformers>=4.37.0" pillow "optimum[onnxruntime]"
"""

import asyncio
import base64
import io
import logging
from typing import Any

from .base import Recognizer
from .pix2tex import DEBUG_IMAGES, _save_debug

logger = logging.getLogger(__name__)

MODEL_NAME = "breezedeus/pix2text-mfr"


def _prepare(raw: Any, margin_ratio: float = 0.12) -> Any:
    """White background, crop to the ink, add a white margin.

    The model's own processor resizes the picture, so no scaling here.
    """
    import numpy as np
    from PIL import Image

    img = raw.convert("RGBA")
    white = Image.new("RGBA", img.size, (255, 255, 255, 255))
    img = Image.alpha_composite(white, img).convert("L")

    arr = np.array(img)
    ys, xs = np.where(arr < 128)
    if len(xs) == 0:
        return img.convert("RGB")  # empty canvas
    img = img.crop((int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1))

    margin = max(8, int(max(img.size) * margin_ratio))
    out = Image.new("L", (img.width + 2 * margin, img.height + 2 * margin), 255)
    out.paste(img, (margin, margin))
    return out.convert("RGB")


class Pix2TextMFRRecognizer(Recognizer):
    """Local recognizer based on the free Pix2Text-MFR model."""

    def __init__(self) -> None:
        try:
            from optimum.onnxruntime import ORTModelForVision2Seq
            from transformers import TrOCRProcessor
        except ImportError as exc:
            raise ImportError(
                "Install the packages with: "
                'pip install "transformers>=4.37.0" pillow "optimum[onnxruntime]"'
            ) from exc

        # The first run downloads the model from Hugging Face (one time only).
        self._processor = TrOCRProcessor.from_pretrained(MODEL_NAME)
        self._model = ORTModelForVision2Seq.from_pretrained(MODEL_NAME, use_cache=False)
        logger.info("Pix2Text-MFR model loaded successfully.")

    def _infer(self, image: Any) -> str:
        pixel_values = self._processor(images=[image], return_tensors="pt").pixel_values
        generated_ids = self._model.generate(pixel_values)
        return self._processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

    async def recognize(self, png_base64: str) -> str:
        """Decode a base64 PNG and return the LaTeX wrapped in $...$."""
        from PIL import Image

        try:
            raw = Image.open(io.BytesIO(base64.b64decode(png_base64)))
            raw.load()
        except Exception as exc:
            logger.error("Failed to decode base64 PNG: %s", exc)
            raise RuntimeError(f"Invalid base64 PNG image: {exc}") from exc

        try:
            image = _prepare(raw)
        except Exception as exc:
            logger.warning("Preprocessing failed, using the raw image: %s", exc)
            image = raw.convert("RGB")

        if DEBUG_IMAGES:
            _save_debug(raw, image)

        try:
            latex = await asyncio.to_thread(self._infer, image)
        except Exception as exc:
            logger.error("Pix2Text-MFR prediction failed: %s", exc)
            raise RuntimeError(f"Pix2Text-MFR prediction failed: {exc}") from exc

        latex = latex.strip()
        if not latex:
            logger.warning("Pix2Text-MFR returned empty LaTeX for the given image.")
            return ""
        return f"${latex}$"
