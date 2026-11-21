"""Converter from LaTeX formulas and mixed text to Word OMML/OOXML.

Converts LaTeX math to MathML using latex2mathml, then transforms MathML to
Word OMML (Office Math Markup Language) using Microsoft's MML2OMML.XSL stylesheet,
and packages it as a WordprocessingML Flat OPC package suitable for Word.insertOoxml().
"""

import os
import re
import html
import logging
from pathlib import Path
from typing import Optional

import lxml.etree as etree
from latex2mathml.converter import convert as latex_to_mathml

logger = logging.getLogger(__name__)

# Locate MML2OMML.XSL
_CURRENT_DIR = Path(__file__).resolve().parent
_XSL_PATH = _CURRENT_DIR / "MML2OMML.XSL"

_TRANSFORM: Optional[etree.XSLT] = None


def _get_transform() -> etree.XSLT:
    global _TRANSFORM
    if _TRANSFORM is None:
        if not _XSL_PATH.exists():
            # Fallback to Office directory if available
            office_paths = [
                Path(r"C:\Program Files\Microsoft Office\root\Office16\MML2OMML.XSL"),
                Path(r"C:\Program Files (x86)\Microsoft Office\root\Office16\MML2OMML.XSL"),
            ]
            for p in office_paths:
                if p.exists():
                    _TRANSFORM = etree.XSLT(etree.parse(str(p)))
                    return _TRANSFORM
            raise FileNotFoundError(f"MML2OMML.XSL not found at {_XSL_PATH}")
        _TRANSFORM = etree.XSLT(etree.parse(str(_XSL_PATH)))
    return _TRANSFORM


def latex_to_omml(latex_code: str) -> str:
    """Convert a single LaTeX math expression into an OMML (<m:oMath>) XML string."""
    tex = latex_code.strip()
    # Strip enclosing $ or $$ if present
    if tex.startswith("$$") and tex.endswith("$$") and len(tex) >= 4:
        tex = tex[2:-2].strip()
    elif tex.startswith("$") and tex.endswith("$") and len(tex) >= 2:
        tex = tex[1:-1].strip()

    mathml_str = latex_to_mathml(tex)
    mathml_dom = etree.fromstring(mathml_str.encode("utf-8"))
    transform = _get_transform()
    omml_dom = transform(mathml_dom)

    xml_text = etree.tostring(omml_dom, encoding="unicode")
    # Remove XML processing instruction <?xml ... ?> if present
    xml_text = re.sub(r"<\?xml[^>]*\?>", "", xml_text).strip()
    return xml_text


def text_to_ooxml(text: str) -> str:
    """Convert mixed text containing LaTeX formulas ($...$ and $$...$$) into

    a complete OpenXML (Flat OPC) package string ready for Word.insertOoxml.
    """
    # Regex for display math $$...$$ and inline math $...$
    pattern = re.compile(r"(\$\$.*?\$\$|\$.*?\$)", re.DOTALL)
    parts = pattern.split(text)

    body_elements = []

    for part in parts:
        if not part:
            continue
        if part.startswith("$$") and part.endswith("$$") and len(part) >= 4:
            # Display math
            tex = part[2:-2].strip()
            try:
                omml = latex_to_omml(tex)
                body_elements.append(f"<m:oMathPara>{omml}</m:oMathPara>")
            except Exception as e:
                logger.warning("Failed to convert display math %r: %s", tex, e)
                escaped = html.escape(part)
                body_elements.append(
                    f'<w:r><w:t xml:space="preserve">{escaped}</w:t></w:r>'
                )
        elif part.startswith("$") and part.endswith("$") and len(part) >= 2:
            # Inline math
            tex = part[1:-1].strip()
            try:
                omml = latex_to_omml(tex)
                body_elements.append(omml)
            except Exception as e:
                logger.warning("Failed to convert inline math %r: %s", tex, e)
                escaped = html.escape(part)
                body_elements.append(
                    f'<w:r><w:t xml:space="preserve">{escaped}</w:t></w:r>'
                )
        else:
            # Plain text
            escaped = html.escape(part)
            # Handle newlines as Word line breaks or paragraph breaks
            lines = escaped.split("\n")
            run_parts = []
            for i, line in enumerate(lines):
                if line:
                    run_parts.append(f'<w:t xml:space="preserve">{line}</w:t>')
                if i < len(lines) - 1:
                    run_parts.append("<w:br/>")
            if run_parts:
                body_elements.append(f"<w:r>{''.join(run_parts)}</w:r>")

    p_content = "".join(body_elements)

    # Complete Flat OPC XML Package for Word document
    ooxml = f"""<?xml version="1.0" standalone="yes"?>
<?mso-application progid="Word.Document"?>
<pkg:package xmlns:pkg="http://schemas.microsoft.com/office/2006/xmlPackage">
  <pkg:part pkg:name="/_rels/.rels" pkg:contentType="application/vnd.openxmlformats-package.relationships+xml" pkg:padding="512">
    <pkg:xmlData>
      <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
        <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
      </Relationships>
    </pkg:xmlData>
  </pkg:part>
  <pkg:part pkg:name="/word/document.xml" pkg:contentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml">
    <pkg:xmlData>
      <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                  xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
                  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
        <w:body>
          <w:p>
            {p_content}
          </w:p>
        </w:body>
      </w:document>
    </pkg:xmlData>
  </pkg:part>
</pkg:package>"""
    return ooxml
