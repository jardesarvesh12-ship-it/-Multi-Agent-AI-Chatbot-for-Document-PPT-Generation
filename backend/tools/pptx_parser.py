"""
pptx_parser.py — PPTX parsing using python-pptx.
Extracts slide structure, layouts, themes, fonts, colors and content patterns.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from pptx import Presentation
    from pptx.util import Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False
    logger.warning("python-pptx not installed. Install via: pip install python-pptx")


@dataclass
class SlideShape:
    name: str
    shape_type: str
    text: str
    left: float = 0.0
    top: float = 0.0
    width: float = 0.0
    height: float = 0.0
    font_name: Optional[str] = None
    font_size: Optional[float] = None
    bold: bool = False
    font_color: Optional[str] = None
    alignment: str = "left"
    is_title: bool = False
    is_placeholder: bool = False
    placeholder_type: Optional[str] = None


@dataclass
class SlideInfo:
    slide_number: int
    title: Optional[str]
    layout_name: str
    shapes: list[SlideShape] = field(default_factory=list)
    full_text: str = ""
    background_color: Optional[str] = None
    notes: str = ""


@dataclass
class PPTTheme:
    """Captures the visual theme of a presentation."""
    title_font: str = "Calibri"
    body_font: str = "Calibri"
    title_font_size: float = 36.0
    body_font_size: float = 18.0
    accent_color: Optional[str] = None
    background_color: Optional[str] = None
    title_color: Optional[str] = None
    body_color: Optional[str] = None
    slide_width: float = 10.0   # inches
    slide_height: float = 7.5  # inches


@dataclass
class PPTDocument:
    file_path: str
    total_slides: int
    slides: list[SlideInfo] = field(default_factory=list)
    theme: PPTTheme = field(default_factory=PPTTheme)
    slide_layouts: list[str] = field(default_factory=list)
    full_text: str = ""


def _rgb_to_hex(rgb) -> Optional[str]:
    if rgb is None:
        return None
    try:
        return "#{:02X}{:02X}{:02X}".format(rgb.r, rgb.g, rgb.b)
    except Exception:
        return None


def _emu_to_inches(emu: int) -> float:
    return emu / 914400.0


def _get_placeholder_type(ph_type) -> str:
    type_map = {
        1: "CENTER_TITLE", 2: "BODY", 3: "CENTER_TITLE",
        13: "TITLE", 15: "SUBTITLE", 18: "FOOTER",
    }
    try:
        return type_map.get(ph_type, str(ph_type))
    except Exception:
        return "UNKNOWN"


def parse_pptx(file_path: str | Path) -> PPTDocument:
    """
    Parse a PPTX file and extract all slide content and styling.

    Args:
        file_path: Path to the .pptx file.

    Returns:
        PPTDocument with all slides, shapes, theme and layout data.
    """
    if not PPTX_AVAILABLE:
        raise ImportError("python-pptx required: pip install python-pptx")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PPTX not found: {path}")

    prs = Presentation(str(path))
    slides_info: list[SlideInfo] = []
    layout_names = [layout.name for layout in prs.slide_layouts]

    # Extract theme-level info
    theme = PPTTheme()
    theme.slide_width = _emu_to_inches(prs.slide_width)
    theme.slide_height = _emu_to_inches(prs.slide_height)

    for slide_idx, slide in enumerate(prs.slides):
        layout_name = slide.slide_layout.name if slide.slide_layout else "Blank"
        shapes_info: list[SlideShape] = []
        slide_title = None
        texts: list[str] = []

        for shape in slide.shapes:
            is_title = False
            is_placeholder = shape.is_placeholder
            ph_type_str = None
            text = ""

            if shape.has_text_frame:
                text = shape.text_frame.text.strip()
                texts.append(text)

            # Check if this is a title placeholder
            if is_placeholder:
                try:
                    ph_type = shape.placeholder_format.type
                    ph_type_str = _get_placeholder_type(ph_type)
                    if ph_type_str in ("CENTER_TITLE", "TITLE") and text:
                        slide_title = text
                        is_title = True
                except Exception:
                    pass

            # Extract font info from first run
            font_name = None
            font_size = None
            bold = False
            font_color = None
            alignment = "left"

            if shape.has_text_frame and shape.text_frame.paragraphs:
                first_para = shape.text_frame.paragraphs[0]
                if first_para.runs:
                    run = first_para.runs[0]
                    font_name = run.font.name
                    if run.font.size:
                        font_size = run.font.size.pt
                    bold = bool(run.font.bold)
                    try:
                        font_color = _rgb_to_hex(run.font.color.rgb)
                    except Exception:
                        pass

                try:
                    align_map = {
                        PP_ALIGN.LEFT: "left",
                        PP_ALIGN.CENTER: "center",
                        PP_ALIGN.RIGHT: "right",
                        PP_ALIGN.JUSTIFY: "justify",
                    }
                    alignment = align_map.get(first_para.alignment, "left")
                except Exception:
                    pass

                # Update theme from title shapes
                if is_title and font_name:
                    theme.title_font = font_name
                    if font_size:
                        theme.title_font_size = font_size
                    if font_color:
                        theme.title_color = font_color
                elif font_name and not is_title:
                    theme.body_font = font_name
                    if font_size:
                        theme.body_font_size = font_size

            shapes_info.append(SlideShape(
                name=shape.name,
                shape_type=str(shape.shape_type),
                text=text,
                left=_emu_to_inches(shape.left) if shape.left else 0.0,
                top=_emu_to_inches(shape.top) if shape.top else 0.0,
                width=_emu_to_inches(shape.width) if shape.width else 0.0,
                height=_emu_to_inches(shape.height) if shape.height else 0.0,
                font_name=font_name,
                font_size=font_size,
                bold=bold,
                font_color=font_color,
                alignment=alignment,
                is_title=is_title,
                is_placeholder=is_placeholder,
                placeholder_type=ph_type_str,
            ))

        # Extract notes
        notes_text = ""
        try:
            if slide.has_notes_slide:
                notes_text = slide.notes_slide.notes_text_frame.text.strip()
        except Exception:
            pass

        slides_info.append(SlideInfo(
            slide_number=slide_idx + 1,
            title=slide_title,
            layout_name=layout_name,
            shapes=shapes_info,
            full_text="\n".join(t for t in texts if t),
            notes=notes_text,
        ))

    full_text = "\n\n".join(s.full_text for s in slides_info if s.full_text)

    return PPTDocument(
        file_path=str(path),
        total_slides=len(slides_info),
        slides=slides_info,
        theme=theme,
        slide_layouts=layout_names,
        full_text=full_text,
    )


def pptx_to_chunks(ppt_doc: PPTDocument, chunk_size: int = 600) -> list[dict]:
    """Split PPTX content into chunks for RAG indexing."""
    chunks = []
    for slide in ppt_doc.slides:
        if slide.full_text:
            chunks.append({
                "text": slide.full_text[:chunk_size],
                "source": ppt_doc.file_path,
                "slide": slide.slide_number,
                "title": slide.title or "",
                "type": "pptx",
            })
    return chunks
