"""Comprehensive test suite for InkToLaTeX FastAPI backend.

Tests:
1. Health check endpoint (/health)
2. Recognition endpoint (/recognize)
3. OOXML equation conversion endpoint (/to-ooxml)
4. Formula criteria (fractions, roots, integrals, sums, matrices, mixed text)
"""

import base64
import os
import unittest
from fastapi.testclient import TestClient

# Set environment before importing main
os.environ["RECOGNIZER"] = "mock"

from main import app, _build_recognizer
from omml import latex_to_omml, text_to_ooxml


class TestBackendAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_recognize_mock_success(self):
        # Create a 1x1 dummy PNG in base64
        dummy_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        response = self.client.post("/recognize", json={"image": dummy_png})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertTrue(len(data["result"]) > 0)
        self.assertIn("$", data["result"])

    def test_recognize_empty_image(self):
        response = self.client.post("/recognize", json={"image": ""})
        self.assertEqual(response.status_code, 400)

    def test_to_ooxml_endpoint(self):
        payload = {"text": "Нехай $x^2 + y^2 = z^2$, тоді результат очевидний."}
        response = self.client.post("/to-ooxml", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("ooxml", data)
        ooxml = data["ooxml"]
        self.assertIn("<m:oMath", ooxml)
        self.assertIn("Нехай", ooxml)

    def test_to_ooxml_empty_text(self):
        response = self.client.post("/to-ooxml", json={"text": ""})
        self.assertEqual(response.status_code, 400)


class TestFormulaCriteria(unittest.TestCase):
    """Section 6 of requirements:

    - x² + y² = z²
    - дріб, корінь, сума з межами, інтеграл, матриця 2×2
    - змішаний рядок: «Нехай ... тоді ...» (текст не псується)
    """

    def test_pythagorean(self):
        omml = latex_to_omml("x^2 + y^2 = z^2")
        self.assertIn("<m:oMath", omml)
        self.assertIn("<m:sSup>", omml)

    def test_fraction_and_root(self):
        # Fraction and square root
        omml = latex_to_omml(r"\frac{\sqrt{x^2+1}}{2}")
        self.assertIn("<m:f>", omml)
        self.assertIn("<m:rad>", omml)

    def test_sum_with_bounds(self):
        # Sum with bounds \sum_{i=1}^{n} i^2
        omml = latex_to_omml(r"\sum_{i=1}^{n} i^2")
        self.assertIn("<m:nary>", omml)

    def test_integral(self):
        # Definite integral \int_{0}^{\infty} e^{-x} dx
        omml = latex_to_omml(r"\int_{0}^{\infty} e^{-x} dx")
        self.assertIn("<m:nary>", omml)

    def test_matrix_2x2(self):
        # 2x2 matrix
        omml = latex_to_omml(r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}")
        self.assertIn("<m:m>", omml)

    def test_mixed_ukrainian_text(self):
        text = "Нехай $x^2+y^2=z^2$, тоді матриця $A = \\begin{pmatrix} 1 & 0 \\\\ 0 & 1 \\end{pmatrix}$ є одиничною."
        ooxml = text_to_ooxml(text)
        self.assertIn("Нехай", ooxml)
        self.assertIn("тоді матриця", ooxml)
        self.assertIn("є одиничною.", ooxml)
        self.assertIn("<m:oMath", ooxml)


if __name__ == "__main__":
    unittest.main()
