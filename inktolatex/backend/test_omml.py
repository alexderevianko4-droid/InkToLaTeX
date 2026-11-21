import unittest
from omml import text_to_ooxml, latex_to_omml


class TestOMMLConversion(unittest.TestCase):
    def test_single_formula(self):
        omml = latex_to_omml("x^2 + y^2 = z^2")
        self.assertIn("<m:oMath", omml)
        self.assertIn("<m:sSup>", omml)

    def test_fraction_and_root(self):
        omml = latex_to_omml(r"\frac{\sqrt{a+b}}{c}")
        self.assertIn("<m:oMath", omml)
        self.assertIn("<m:rad>", omml)
        self.assertIn("<m:f>", omml)

    def test_mixed_text_to_ooxml(self):
        text = "Нехай $x^2 + y^2 = z^2$, тоді результат очевидний."
        ooxml = text_to_ooxml(text)
        self.assertIn("Нехай", ooxml)
        self.assertIn("<m:oMath", ooxml)
        self.assertIn("тоді результат очевидний", ooxml)

    def test_display_math(self):
        text = r"Матриця: $$\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}$$"
        ooxml = text_to_ooxml(text)
        self.assertIn("<m:oMathPara>", ooxml)
        self.assertIn("<m:m>", ooxml)


if __name__ == "__main__":
    unittest.main()
