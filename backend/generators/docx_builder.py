"""
docx_builder.py — Professional DOCX builder using python-docx.
Applies StyleProfile extracted from template files to generate styled documents.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import uuid

from loguru import logger

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed: pip install python-docx")

from backend.tools.style_extractor import StyleProfile
from backend.config import settings


@dataclass
class DocumentSection:
    heading: str
    content: str
    level: int = 1  # heading level 1, 2, 3
    is_bullet_list: bool = False
    is_numbered_list: bool = False


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to (r, g, b) tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return r, g, b


def _set_font_color(run, hex_color: str):
    """Apply hex font color to a docx run."""
    try:
        r, g, b = _hex_to_rgb(hex_color)
        run.font.color.rgb = RGBColor(r, g, b)
    except Exception as e:
        logger.warning(f"Could not set font color {hex_color}: {e}")


def _add_heading(doc: "Document", text: str, level: int, style: StyleProfile):
    """Add a styled heading to the document."""
    heading = doc.add_heading(text, level=level)
    run = heading.runs[0] if heading.runs else heading.add_run(text)
    run.font.name = style.heading_font
    run.font.size = Pt(style.heading_font_size - (level - 1) * 2)
    if style.heading_color:
        _set_font_color(run, style.heading_color)
    return heading


def _add_paragraph(doc: "Document", text: str, style: StyleProfile):
    """Add a styled body paragraph with inline markdown bold/italic support."""
    import re
    para = doc.add_paragraph()
    # Split text on **bold** and *italic* markers
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            run = para.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = para.add_run(part[1:-1])
            run.italic = True
        else:
            run = para.add_run(part)
        run.font.name = style.body_font
        run.font.size = Pt(style.body_font_size)
        if style.body_color:
            _set_font_color(run, style.body_color)
    return para


def _add_bullet_list(doc: "Document", items: list[str], style: StyleProfile):
    """Add a bullet list with inline markdown bold/italic support."""
    import re
    for item in items:
        raw = item.strip("•- ")
        para = doc.add_paragraph(style="List Bullet")
        parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', raw)
        for part in parts:
            if part.startswith('**') and part.endswith('**'):
                run = para.add_run(part[2:-2])
                run.bold = True
            elif part.startswith('*') and part.endswith('*'):
                run = para.add_run(part[1:-1])
                run.italic = True
            else:
                run = para.add_run(part)
            run.font.name = style.body_font
            run.font.size = Pt(style.body_font_size)


def _add_numbered_list(doc: "Document", items: list[str], style: StyleProfile):
    """Add a numbered list."""
    for item in items:
        # Strip existing numbering
        clean = re.sub(r"^\d+[.)]\s*", "", item.strip())
        para = doc.add_paragraph(clean, style="List Number")
        if para.runs:
            para.runs[0].font.name = style.body_font
            para.runs[0].font.size = Pt(style.body_font_size)


def _parse_content_blocks(content: str) -> list[dict]:
    """
    Parse content string into structured blocks (paragraph, bullet, numbered).
    """
    blocks = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Detect bullet list
        if line.startswith(("• ", "- ", "* ", "– ")):
            bullet_items = []
            while i < len(lines) and lines[i].strip().startswith(("• ", "- ", "* ", "– ")):
                bullet_items.append(lines[i].strip())
                i += 1
            blocks.append({"type": "bullet", "items": bullet_items})
            continue

        # Detect numbered list
        if re.match(r"^\d+[.)]\s", line):
            numbered_items = []
            while i < len(lines) and re.match(r"^\d+[.)]\s", lines[i].strip()):
                numbered_items.append(lines[i].strip())
                i += 1
            blocks.append({"type": "numbered", "items": numbered_items})
            continue

        # Regular paragraph
        blocks.append({"type": "paragraph", "text": line})
        i += 1

    return blocks


def build_docx(
    sections: list[DocumentSection],
    style: StyleProfile,
    title: str,
    output_dir: Optional[str] = None,
    citations: Optional[list[str]] = None,
    version_id: Optional[str] = None,
) -> str:
    """
    Build a styled DOCX document from sections and a StyleProfile.

    Args:
        sections: List of DocumentSection objects.
        style: StyleProfile from template analysis.
        title: Document title.
        output_dir: Directory to save the file.
        citations: Optional list of citation strings.
        version_id: Optional version identifier.

    Returns:
        Absolute path to the generated .docx file.
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx required: pip install python-docx")

    doc = Document()

    # Set page margins
    margins = style.margins
    for section in doc.sections:
        section.top_margin = Inches(margins.get("top", 1.0))
        section.bottom_margin = Inches(margins.get("bottom", 1.0))
        section.left_margin = Inches(margins.get("left", 1.25))
        section.right_margin = Inches(margins.get("right", 1.25))

    # Set default font
    from docx.oxml.ns import qn
    normal_style = doc.styles["Normal"]
    normal_style.font.name = style.body_font
    normal_style.font.size = Pt(style.body_font_size)

    # Title
    title_para = doc.add_heading(title, level=0)
    title_run = title_para.runs[0] if title_para.runs else title_para.add_run(title)
    title_run.font.name = style.heading_font
    title_run.font.size = Pt(style.heading_font_size + 8)
    if style.heading_color:
        _set_font_color(title_run, style.heading_color)

    doc.add_paragraph("")  # spacer

    # Add each section
    for sec in sections:
        _add_heading(doc, sec.heading, sec.level, style)
        blocks = _parse_content_blocks(sec.content)
        for block in blocks:
            if block["type"] == "bullet":
                _add_bullet_list(doc, block["items"], style)
            elif block["type"] == "numbered":
                _add_numbered_list(doc, block["items"], style)
            else:
                _add_paragraph(doc, block["text"], style)
        doc.add_paragraph("")  # spacing between sections

    # Citations
    if citations:
        doc.add_page_break()
        _add_heading(doc, "References & Sources", level=1, style=style)
        for i, cite in enumerate(citations, 1):
            _add_paragraph(doc, f"[{i}] {cite}", style)

    # Save file
    out_dir = Path(output_dir or settings.generated_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = version_id or str(uuid.uuid4())[:8]
    safe_title = re.sub(r"[^\w\s-]", "", title)[:40].strip().replace(" ", "_")
    filename = f"{safe_title}_{vid}.docx"
    file_path = out_dir / filename
    doc.save(str(file_path))
    logger.info(f"DOCX saved: {file_path}")
    return str(file_path)
