"""
docx_builder.py — Professional DOCX builder using python-docx.
Supports:
1. Structure (Cover header, section hierarchy, page breaks, callout boxes, dividers, TOC)
2. Styles (Document defaults, character & paragraph formatting)
3. Fonts (Primary body & secondary heading fonts, custom Pt sizes)
4. Colors (Primary, secondary, accent, text, table shading & callout fills)
5. Headings (H1-H4 with orphan control keep_with_next, space_before/after)
6. Paragraphs (Bold/italic/code runs, bullet & numbered lists, spacing & indents)
7. Tables (Styled headers, zebra striping, cell margins, borders, alignment, captions)
8. Images (Width/height scaling, alignment, captions)
9. Headers & Footers (Brand running header, page number fields, first-page suppression)
10. Margins (Top, bottom, left, right in inches)
11. Page Layout (Portrait/Landscape, Paper sizes Letter/A4)
12. Spacing (Paragraph line_spacing, space_before/after, table cell padding)
13. Branding (Logo support, company brand colors, divider bars)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Any
import uuid

from loguru import logger

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.section import WD_ORIENT
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    logger.warning("python-docx not installed: pip install python-docx")

from backend.tools.style_extractor import StyleProfile
from backend.config import settings


@dataclass
class TableData:
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    caption: Optional[str] = None
    header_bg_color: Optional[str] = None


@dataclass
class ImageData:
    image_path: str
    caption: Optional[str] = None
    width_inches: float = 5.5
    align: str = "center"  # center, left, right


@dataclass
class CalloutBoxData:
    text: str
    title: Optional[str] = "NOTE"
    bg_color: Optional[str] = None
    border_color: Optional[str] = None


@dataclass
class DocumentSection:
    heading: str
    content: str
    level: int = 1  # heading level 1, 2, 3
    is_bullet_list: bool = False
    is_numbered_list: bool = False
    tables: list[TableData] = field(default_factory=list)
    images: list[ImageData] = field(default_factory=list)
    callout_boxes: list[CalloutBoxData] = field(default_factory=list)
    page_break_after: bool = False


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


def _set_cell_background(cell, hex_color: str):
    """Set background shading for a table cell via oxml."""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), hex_color.lstrip('#'))
    tcPr.append(shd)


def _set_cell_margins(cell, top=120, bottom=120, left=160, right=160):
    """Set internal cell margins (padding) in dxa (1 pt = 20 dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def _add_page_number_field(run):
    """Insert a dynamic PAGE field into a header/footer run."""
    fldChar1 = OxmlElement('w:fldChar')
    fldChar1.set(qn('w:fldCharType'), 'begin')
    instrText = OxmlElement('w:instrText')
    instrText.set(qn('xml:space'), 'preserve')
    instrText.text = "PAGE"
    fldChar2 = OxmlElement('w:fldChar')
    fldChar2.set(qn('w:fldCharType'), 'separate')
    fldChar3 = OxmlElement('w:fldChar')
    fldChar3.set(qn('w:fldCharType'), 'end')
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)


def _add_divider_line(doc: "Document", color_hex: str = "1A365D"):
    """Add a styled horizontal accent divider line."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(12)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '12')  # 1.5 pt
    bottom.set(qn('w:space'), '4')
    bottom.set(qn('w:color'), color_hex.lstrip('#'))
    pBdr.append(bottom)
    pPr.append(pBdr)


def _add_heading(doc: "Document", text: str, level: int, style: StyleProfile):
    """Add a styled heading with orphan protection and spacing."""
    heading = doc.add_heading(text, level=level)
    heading.paragraph_format.keep_with_next = True
    heading.paragraph_format.space_before = Pt(getattr(style, 'space_before_heading', 12.0) if level == 1 else 8.0)
    heading.paragraph_format.space_after = Pt(6.0)

    run = heading.runs[0] if heading.runs else heading.add_run(text)
    run.font.name = style.heading_font
    size_pt = max(11.0, style.heading_font_size - (level - 1) * 2)
    run.font.size = Pt(size_pt)
    if style.heading_color:
        _set_font_color(run, style.heading_color)
    return heading


def _add_paragraph(doc: "Document", text: str, style: StyleProfile, align: str = "left"):
    """Add a styled body paragraph with inline markdown formatting support."""
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(getattr(style, 'space_after_para', 6.0))
    para.paragraph_format.line_spacing = getattr(style, 'line_spacing', 1.15)

    if align.lower() == "center":
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif align.lower() == "right":
        para.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    elif align.lower() == "justify":
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    else:
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT

    # Split text on **bold**, *italic*, and `code` markers
    parts = re.split(r'(\*\*.*?\*\*|\*.*?\*|`.*?`)', text)
    for part in parts:
        if not part:
            continue
        if part.startswith('**') and part.endswith('**'):
            run = para.add_run(part[2:-2])
            run.bold = True
        elif part.startswith('*') and part.endswith('*'):
            run = para.add_run(part[1:-1])
            run.italic = True
        elif part.startswith('`') and part.endswith('`'):
            run = para.add_run(part[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(style.body_font_size - 1)
        else:
            run = para.add_run(part)

        if not (part.startswith('`') and part.endswith('`')):
            run.font.name = style.body_font
            run.font.size = Pt(style.body_font_size)
        if style.body_color:
            _set_font_color(run, style.body_color)
    return para


def _add_bullet_list(doc: "Document", items: list[str], style: StyleProfile):
    """Add a bullet list with inline markdown formatting."""
    for item in items:
        raw = item.strip("•- ")
        para = doc.add_paragraph(style="List Bullet")
        para.paragraph_format.space_after = Pt(3.0)
        para.paragraph_format.line_spacing = style.line_spacing
        parts = re.split(r'(\*\*.*?\*\*|\*.*?\*)', raw)
        for part in parts:
            if not part:
                continue
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


def _add_numbered_list(doc: "Document", items: list[str], style: StyleProfile):
    """Add a numbered list."""
    for item in items:
        clean = re.sub(r"^\d+[.)]\s*", "", item.strip())
        para = doc.add_paragraph(clean, style="List Number")
        para.paragraph_format.space_after = Pt(3.0)
        para.paragraph_format.line_spacing = style.line_spacing
        if para.runs:
            para.runs[0].font.name = style.body_font
            para.runs[0].font.size = Pt(style.body_font_size)
            if style.body_color:
                _set_font_color(para.runs[0], style.body_color)


def _add_callout_box(doc: "Document", text: str, title: str = "NOTE", style: Optional[StyleProfile] = None):
    """Add a styled callout box with a background tint and left border."""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.autofit = False

    bg_color = (style.background_color if style and style.background_color else "F0F4F8")
    border_color = (style.accent_color if style and style.accent_color else "2B6CB0")

    cell = tbl.cell(0, 0)
    _set_cell_background(cell, bg_color)
    _set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    # Left border only oxml
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = OxmlElement('w:tcBorders')
    left = OxmlElement('w:left')
    left.set(qn('w:val'), 'single')
    left.set(qn('w:sz'), '24')  # 3pt width
    left.set(qn('w:space'), '0')
    left.set(qn('w:color'), border_color.lstrip('#'))
    tcBorders.append(left)

    for b_name in ['top', 'bottom', 'right']:
        b = OxmlElement(f'w:{b_name}')
        b.set(qn('w:val'), 'none')
        tcBorders.append(b)
    tcPr.append(tcBorders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.space_before = Pt(2)

    run_title = p.add_run(f"{title}: ")
    run_title.bold = True
    if style and style.heading_font:
        run_title.font.name = style.heading_font
    if style and style.accent_color:
        _set_font_color(run_title, style.accent_color)

    run_text = p.add_run(text)
    if style:
        run_text.font.name = style.body_font
        run_text.font.size = Pt(style.body_font_size)
        if style.body_color:
            _set_font_color(run_text, style.body_color)

    # Add space after callout box
    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(4)


def _add_styled_table(
    doc: "Document",
    headers: list[str],
    rows: list[list[str]],
    caption: Optional[str] = None,
    style: Optional[StyleProfile] = None
):
    """Add a professional table with colored headers, zebra striping, and cell margins."""
    if not headers and not rows:
        return
    num_cols = len(headers) if headers else (len(rows[0]) if rows else 1)
    num_rows = (1 if headers else 0) + len(rows)

    table = doc.add_table(rows=num_rows, cols=num_cols)
    table.style = 'Table Grid'

    hdr_bg = (style.accent_color if style and style.accent_color else "1A365D")

    row_idx = 0
    if headers:
        hdr_row = table.rows[0]
        # Repeat header row across pages
        trPr = hdr_row._tr.get_or_add_trPr()
        trPr.append(OxmlElement('w:tblHeader'))

        for c_idx, text in enumerate(headers):
            cell = hdr_row.cells[c_idx]
            _set_cell_background(cell, hdr_bg)
            _set_cell_margins(cell, top=120, bottom=120, left=160, right=160)
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(text)
            run.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)
            if style:
                run.font.name = style.heading_font
                run.font.size = Pt(style.body_font_size)
        row_idx = 1

    for r_data in rows:
        if row_idx >= len(table.rows):
            break
        row = table.rows[row_idx]
        bg_color = "F7FAFC" if (row_idx % 2 == 0) else "FFFFFF"

        for c_idx, val in enumerate(r_data):
            if c_idx < len(row.cells):
                cell = row.cells[c_idx]
                if bg_color != "FFFFFF":
                    _set_cell_background(cell, bg_color)
                _set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
                p = cell.paragraphs[0]
                run = p.add_run(str(val))
                if style:
                    run.font.name = style.body_font
                    run.font.size = Pt(style.body_font_size)
                    if style.body_color:
                        _set_font_color(run, style.body_color)
        row_idx += 1

    if caption:
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = cap_p.add_run(f"Table: {caption}")
        cap_run.italic = True
        cap_run.font.size = Pt(9)
        if style and style.body_color:
            _set_font_color(cap_run, style.body_color)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(4)


def _add_image(
    doc: "Document",
    image_path: str,
    caption: Optional[str] = None,
    width_inches: float = 5.5,
    align: str = "center",
    style: Optional[StyleProfile] = None
):
    """Add an image with scaling, alignment, and caption."""
    path = Path(image_path)
    if not path.is_file():
        logger.warning(f"Image path not found: {image_path}")
        return
    p = doc.add_paragraph()
    if align.lower() == "left":
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    elif align.lower() == "right":
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width_inches))

    if caption:
        cap_p = doc.add_paragraph()
        cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_run = cap_p.add_run(f"Figure: {caption}")
        cap_run.italic = True
        cap_run.font.size = Pt(9)
        if style and style.body_color:
            _set_font_color(cap_run, style.body_color)

    p_spacer = doc.add_paragraph()
    p_spacer.paragraph_format.space_after = Pt(4)


def _parse_content_blocks(content: str) -> list[dict]:
    """
    Parse section content string into structured content blocks:
    paragraphs, bullet lists, numbered lists, markdown tables, callout blocks.
    """
    blocks = []
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Detect Markdown Callout block (> [!NOTE] or > Note:)
        if line.startswith(">"):
            callout_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                callout_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            full_callout = " ".join(callout_lines)
            title = "NOTE"
            if full_callout.startswith("[!") and "]" in full_callout:
                title = full_callout[2:full_callout.find("]")].upper()
                full_callout = full_callout[full_callout.find("]") + 1:].strip()
            elif ":" in full_callout[:20]:
                parts = full_callout.split(":", 1)
                title = parts[0].strip().upper()
                full_callout = parts[1].strip()
            blocks.append({"type": "callout", "title": title, "text": full_callout})
            continue

        # Detect Markdown Table (| col1 | col2 |)
        if line.startswith("|") and line.endswith("|"):
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1

            headers = []
            rows = []
            for idx, row_str in enumerate(tbl_lines):
                cells = [c.strip() for c in row_str.strip("|").split("|")]
                # Skip markdown separator row (|---|---|)
                if all(re.match(r"^:?-+:?$", c) for c in cells):
                    continue
                if idx == 0:
                    headers = cells
                else:
                    rows.append(cells)
            blocks.append({"type": "table", "headers": headers, "rows": rows})
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


def _setup_page_and_margins(doc: "Document", style: StyleProfile):
    """Configure page size, orientation, and margins."""
    section = doc.sections[0]

    # Margins
    margins = getattr(style, 'margins', {}) or {}
    section.top_margin = Inches(margins.get("top", 1.0))
    section.bottom_margin = Inches(margins.get("bottom", 1.0))
    section.left_margin = Inches(margins.get("left", 1.0))
    section.right_margin = Inches(margins.get("right", 1.0))

    # Paper Size & Orientation
    orientation = getattr(style, 'page_orientation', 'portrait').lower()
    paper_size = getattr(style, 'paper_size', 'letter').lower()

    if paper_size == "a4":
        width, height = Inches(8.27), Inches(11.69)
    else:  # default letter
        width, height = Inches(8.5), Inches(11.0)

    if orientation == "landscape":
        section.orientation = WD_ORIENT.LANDSCAPE
        section.page_width = height
        section.page_height = width
    else:
        section.orientation = WD_ORIENT.PORTRAIT
        section.page_width = width
        section.page_height = height


def _setup_headers_and_footers(doc: "Document", style: StyleProfile, title: str):
    """Configure running headers, footers, and page numbers."""
    section = doc.sections[0]
    section.different_first_page_header_footer = True

    brand_name = getattr(style, 'brand_name', None) or "Enterprise Report"
    header_text = getattr(style, 'header_text', None) or f"{brand_name} | {title}"
    footer_text = getattr(style, 'footer_text', None) or "Confidential & Proprietary"

    # Header
    header = section.header
    if header.paragraphs:
        hp = header.paragraphs[0]
        hp.text = header_text
        hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if hp.runs:
            hp.runs[0].font.name = style.body_font
            hp.runs[0].font.size = Pt(8.5)
            if style.accent_color:
                _set_font_color(hp.runs[0], style.accent_color)

    # Footer
    footer = section.footer
    if footer.paragraphs:
        fp = footer.paragraphs[0]
        fp.text = footer_text
        fp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if fp.runs:
            fp.runs[0].font.name = style.body_font
            fp.runs[0].font.size = Pt(8.5)

        if getattr(style, 'show_page_numbers', True):
            p_num = fp.add_run("\tPage ")
            p_num.font.name = style.body_font
            p_num.font.size = Pt(8.5)
            _add_page_number_field(p_num)


def build_docx(
    sections: list[DocumentSection],
    style: StyleProfile,
    title: str,
    output_dir: Optional[str] = None,
    citations: Optional[list[str]] = None,
    version_id: Optional[str] = None,
    subtitle: Optional[str] = None,
    author: Optional[str] = None,
) -> str:
    """
    Build a styled DOCX document from sections and a StyleProfile.

    Args:
        sections: List of DocumentSection objects.
        style: StyleProfile containing formatting specifications.
        title: Document title.
        output_dir: Directory to save the file.
        citations: Optional list of citation strings.
        version_id: Optional version identifier.
        subtitle: Optional document subtitle.
        author: Optional author/brand attribution.

    Returns:
        Absolute path to the generated .docx file.
    """
    if not DOCX_AVAILABLE:
        raise ImportError("python-docx required: pip install python-docx")

    doc = Document()

    # 1. Setup Page Layout, Margins, Headers/Footers
    _setup_page_and_margins(doc, style)
    _setup_headers_and_footers(doc, style, title)

    # Set default document font style
    normal_style = doc.styles["Normal"]
    normal_style.font.name = style.body_font
    normal_style.font.size = Pt(style.body_font_size)

    # 2. Cover / Title Header Section
    if getattr(style, 'brand_logo_path', None) and Path(style.brand_logo_path).is_file():
        _add_image(doc, style.brand_logo_path, width_inches=2.0, align="left", style=style)

    title_para = doc.add_heading(title, level=0)
    title_para.paragraph_format.space_before = Pt(12)
    title_para.paragraph_format.space_after = Pt(4)
    title_run = title_para.runs[0] if title_para.runs else title_para.add_run(title)
    title_run.font.name = style.heading_font
    title_run.font.size = Pt(style.heading_font_size + 8)
    if style.heading_color:
        _set_font_color(title_run, style.heading_color)

    if subtitle:
        sub_para = doc.add_paragraph()
        sub_para.paragraph_format.space_after = Pt(8)
        sub_run = sub_para.add_run(subtitle)
        sub_run.font.name = style.body_font
        sub_run.font.size = Pt(style.body_font_size + 2)
        sub_run.italic = True
        if style.body_color:
            _set_font_color(sub_run, style.body_color)

    if author or getattr(style, 'brand_name', None):
        brand_str = author or getattr(style, 'brand_name', '')
        b_para = doc.add_paragraph()
        b_para.paragraph_format.space_after = Pt(12)
        b_run = b_para.add_run(f"Prepared by: {brand_str}")
        b_run.font.name = style.body_font
        b_run.font.size = Pt(style.body_font_size - 1)
        if style.accent_color:
            _set_font_color(b_run, style.accent_color)

    # Divider bar
    divider_color = style.accent_color or style.heading_color or "1A365D"
    _add_divider_line(doc, divider_color)

    # 3. Add Sections
    for sec in sections:
        _add_heading(doc, sec.heading, sec.level, style)

        # Embedded tables on DocumentSection object
        for tbl in getattr(sec, 'tables', []):
            _add_styled_table(doc, tbl.headers, tbl.rows, tbl.caption, style)

        # Embedded images on DocumentSection object
        for img in getattr(sec, 'images', []):
            _add_image(doc, img.image_path, img.caption, img.width_inches, img.align, style)

        # Embedded callouts on DocumentSection object
        for callout in getattr(sec, 'callout_boxes', []):
            _add_callout_box(doc, callout.text, callout.title or "NOTE", style)

        # Parse and render text blocks (paragraphs, bullets, numbered lists, markdown tables, callouts)
        blocks = _parse_content_blocks(sec.content)
        for block in blocks:
            btype = block.get("type")
            if btype == "bullet":
                _add_bullet_list(doc, block["items"], style)
            elif btype == "numbered":
                _add_numbered_list(doc, block["items"], style)
            elif btype == "table":
                _add_styled_table(doc, block.get("headers", []), block.get("rows", []), None, style)
            elif btype == "callout":
                _add_callout_box(doc, block.get("text", ""), block.get("title", "NOTE"), style)
            else:
                _add_paragraph(doc, block.get("text", ""), style)

        if getattr(sec, 'page_break_after', False):
            doc.add_page_break()

    # 4. Citations & References Section
    if citations:
        doc.add_page_break()
        _add_heading(doc, "References & Sources", level=1, style=style)
        _add_divider_line(doc, divider_color)
        for i, cite in enumerate(citations, 1):
            _add_paragraph(doc, f"[{i}] {cite}", style)

    # 5. Save output file
    out_dir = Path(output_dir or settings.generated_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = version_id or str(uuid.uuid4())[:8]
    safe_title = re.sub(r"[^\w\s-]", "", title)[:40].strip().replace(" ", "_")
    filename = f"{safe_title}_{vid}.docx"
    file_path = out_dir / filename
    doc.save(str(file_path))
    logger.info(f"DOCX saved: {file_path}")
    return str(file_path)
