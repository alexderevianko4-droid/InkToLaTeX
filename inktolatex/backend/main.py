"""FastAPI backend for the InkToLaTeX Word Add-in.

Provides an HTTP API that accepts base64-encoded PNG images of handwritten
text/math and returns recognized text with LaTeX-formatted formulas.
"""

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from recognizers.base import Recognizer
from omml import text_to_ooxml

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Recognizer factory
# ---------------------------------------------------------------------------

RECOGNIZER_NAME: str = os.environ.get("RECOGNIZER", "pix2tex").lower().strip()


def _build_recognizer(name: str) -> Recognizer:
    """Instantiate the recognizer identified by *name*.

    Args:
        name: One of ``"pix2tex"``, ``"mathpix"``, ``"llm"``, or ``"mock"``.

    Returns:
        A concrete :class:`Recognizer` instance.

    Raises:
        ValueError: If *name* is not a known recognizer.
    """
    if name == "mock":
        from recognizers.mock import MockRecognizer

        return MockRecognizer()
    if name == "mathpix":
        from recognizers.mathpix import MathpixRecognizer

        return MathpixRecognizer()
    if name == "llm":
        from recognizers.llm import LLMRecognizer

        return LLMRecognizer()
    if name == "pix2tex":
        from recognizers.pix2tex import Pix2TexRecognizer

        return Pix2TexRecognizer()
    if name == "pix2text":
        from recognizers.pix2text_mfr import Pix2TextMFRRecognizer

        return Pix2TextMFRRecognizer()
    raise ValueError(
        f"Unknown recognizer '{name}'. Choose from: mathpix, llm, pix2tex, mock."
    )


recognizer: Recognizer = _build_recognizer(RECOGNIZER_NAME)
logger.info("Using recognizer: %s", RECOGNIZER_NAME)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="InkToLaTeX Backend",
    description="Recognizes handwritten text and math from PNG images and returns LaTeX.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class RecognizeRequest(BaseModel):
    """Payload for the /recognize endpoint."""

    image: str
    """Base64-encoded PNG image (without the ``data:`` URI prefix)."""


class RecognizeResponse(BaseModel):
    """Response from the /recognize endpoint."""

    result: str
    """Recognized text with LaTeX math delimiters."""


class HealthResponse(BaseModel):
    """Response from the /health endpoint."""

    status: str


class ToOoxmlRequest(BaseModel):
    """Payload for the /to-ooxml endpoint."""

    text: str


class ToOoxmlResponse(BaseModel):
    """Response from the /to-ooxml endpoint."""

    ooxml: str

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/recognize", response_model=RecognizeResponse)
async def recognize_image(body: RecognizeRequest) -> RecognizeResponse:
    """Accept a base64-encoded PNG and return recognized text with LaTeX.

    Args:
        body: JSON body containing the ``image`` field.

    Returns:
        A :class:`RecognizeResponse` with the recognized text.
    """
    if not body.image:
        raise HTTPException(status_code=400, detail="The 'image' field is required and must not be empty.")

    try:
        result = await recognizer.recognize(body.image)
    except RuntimeError as exc:
        logger.error("Recognition failed: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Unexpected error during recognition.")
        raise HTTPException(status_code=500, detail="Internal server error.") from exc

    return RecognizeResponse(result=result)


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Simple health-check endpoint."""
    return HealthResponse(status="ok")


@app.post("/to-ooxml", response_model=ToOoxmlResponse)
async def convert_to_ooxml(body: ToOoxmlRequest) -> ToOoxmlResponse:
    """Convert text with LaTeX formulas into Word Flat OPC XML for native equation insertion."""
    if not body.text:
        raise HTTPException(status_code=400, detail="The 'text' field must not be empty.")
    try:
        ooxml = text_to_ooxml(body.text)
        return ToOoxmlResponse(ooxml=ooxml)
    except Exception as exc:
        logger.exception("OOXML conversion failed.")
        raise HTTPException(status_code=500, detail=f"Failed to generate OOXML: {exc}") from exc

# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
