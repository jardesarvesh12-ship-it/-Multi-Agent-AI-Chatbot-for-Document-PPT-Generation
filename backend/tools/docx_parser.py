"""
docx_parser.py — DOCX parsing using python-docx.
Extracts full text, headings, paragraphs, tables, styles and metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed. Install via: pip install python-docx")


@dataclass
class DocxStyle:
    """Captures style information from a DOCX document."""
    default_font: str = "Calibri"
    default_font_size: float = 11.0
    heading_font: str = "Calibri"
    body_font: str = "Calibri"
    heading_color: Optional[str] = None
    body_color: Optional[str] = None
    line_spacing: Optional[float] = None
    paragraph_spacing_before: float = 0.0
    paragraph_spacing_after: float = 8.0
    margins: dict = field(default_factory=dict)


@dataclass
class DocxParagraph:
    text: str
    style_name: str
    level: int  # heading level (0 = body)
    bold: bool = False
    italic: bool = False
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    alignment: str = "left"


@dataclass
class DocxTable:
    rows: int
    cols: int
    data: list[list[str]] = field(default_factory=list)


@dataclass
class DocxDocument:
    file_path: str
    paragraphs: list[DocxParagraph] = field(default_factory=list)
    tables: list[DocxTable] = field(default_factory=list)
    style: DocxStyle = field(default_factory=DocxStyle)
    full_text: str = ""
    metadata: dict = field(default_factory=dict)
    sections: list[dict] = field(default_factory=list)  # {heading, content}


def _rgb_to_hex(rgb: Optional[RGBColor]) -> Optional[str]:
    if rgb is None:
        return None
    try:
        return "#{:02X}{:02X}{:02X}".format(rgb.r, rgb.g, rgb.b)
    except Exception:
        return None


def _get_alignment(para) -> str:
    """Return alignment name as a string."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    align_map = {
        WD_ALIGN_PARAGRAPH.LEFT: "left",
        WD_ALIGN_PARAGRAPH.CENTER: "center",
        WD_ALIGN_PARAGRAPH.RIGHT: "right",
        WD_ALIGN_PARAGRAPH.JUSTIFY: "justify",
    }
    return align_map.get(para.alignment, "left")


def parse_docx(file_path: str | Path) -> DocxDocument:
    """
    Parse a DOCX file and extract structured content + style.

    Args:
        file_path: Path to the .docx file.

    Returns:
        DocxDocument with all extracted data.
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx required: pip install python-docx")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"DOCX not found: {path}")

    doc = Document(str(path))
    paragraphs: list[DocxParagraph] = []
    sections_list: list[dict] = []
    current_heading: Optional[str] = None
    current_content: list[str] = []

    for para in doc.paragraphs:
        text = para.text.strip()
        style_name = para.style.name if para.style else "Normal"
        level = 0

        # Determine heading level
        if style_name.startswith("Heading"):
            try:
                level = int(style_name.split()[-1])
            except ValueError:
                level = 1

        # Extract run-level formatting
        bold = any(run.bold for run in para.runs if run.text.strip())
        italic = any(run.italic for run in para.runs if run.text.strip())
        font_name = None
        font_size = None
        if para.runs:
            first_run = para.runs[0]
            font_name = first_run.font.name
            if first_run.font.size:
                font_size = first_run.font.size.pt

        paragraphs.append(DocxParagraph(
            text=text,
            style_name=style_name,
            level=level,
            bold=bold,
            italic=italic,
            font_name=font_name,
            font_size=font_size,
            alignment=_get_alignment(para),
        ))

        # Build section structure
        if level == 1 and text:
            if current_heading is not None:
                sections_list.append({"heading": current_heading, "content": "\n".join(current_content)})
            current_heading = text
            current_content = []
        elif text:
            current_content.append(text)

    # Final section
    if current_heading:
        sections_list.append({"heading": current_heading, "content": "\n".join(current_content)})

    # Parse tables
    tables: list[DocxTable] = []
    for tbl in doc.tables:
        rows = len(tbl.rows)
        cols = len(tbl.columns)
        data = [[cell.text.strip() for cell in row.cells] for row in tbl.rows]
        tables.append(DocxTable(rows=rows, cols=cols, data=data))

    # Extract document-level style
    style = DocxStyle()
    try:
        default_style = doc.styles["Normal"]
        if default_style.font.name:
            style.default_font = default_style.font.name
            style.body_font = default_style.font.name
        if default_style.font.size:
            style.default_font_size = default_style.font.size.pt
    except Exception:
        pass

    try:
        heading_style = doc.styles["Heading 1"]
        if heading_style.font.name:
            style.heading_font = heading_style.font.name
        if heading_style.font.color and heading_style.font.color.rgb:
            style.heading_color = _rgb_to_hex(heading_style.font.color.rgb)
    except Exception:
        pass

    # Extract page margins from first section
    try:
        sec = doc.sections[0]
        style.margins = {
            "top": sec.top_margin.inches,
            "bottom": sec.bottom_margin.inches,
            "left": sec.left_margin.inches,
            "right": sec.right_margin.inches,
        }
    except Exception:
        pass

    full_text = "\n".join(p.text for p in paragraphs if p.text)

    return DocxDocument(
        file_path=str(path),
        paragraphs=paragraphs,
        tables=tables,
        style=style,
        full_text=full_text,
        sections=sections_list,
    )


def docx_to_chunks(docx_doc: DocxDocument, chunk_size: int = 800, overlap: int = 80) -> list[dict]:
    """Split DOCX content into chunks for RAG indexing."""
    chunks = []
    text = docx_doc.full_text
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append({
            "text": text[start:end],
            "source": docx_doc.file_path,
            "type": "docx",
        })
        start += chunk_size - overlap
    return chunks
