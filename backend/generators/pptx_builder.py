"""
pptx_builder.py — Professional PPTX builder using python-pptx.
Applies PPT StyleProfile from template to generate themed presentations.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False
    logger.warning("python-pptx not installed: pip install python-pptx")

from backend.tools.style_extractor import StyleProfile
from backend.config import settings


@dataclass
class SlideContent:
    title: str
    content: str           # Main body text
    bullet_points: list[str] = field(default_factory=list)
    speaker_notes: str = ""
    layout_name: str = "Title and Content"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)


def _apply_text_style(run, font_name: str, font_size: float, bold: bool = False,
                       color_hex: Optional[str] = None):
    """Apply consistent font styling to a run."""
    run.font.name = font_name
    run.font.size = Pt(font_size)
    run.font.bold = bold
    if color_hex:
        try:
            r, g, b = _hex_to_rgb(color_hex)
            run.font.color.rgb = RGBColor(r, g, b)
        except Exception:
            pass


def _add_title_slide(prs: "Presentation", title: str, subtitle: str, style: StyleProfile):
    """Add a title slide (first slide) to the presentation."""
    # Use layout index 0 (Title Slide) or find it
    layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)

    for placeholder in slide.placeholders:
        ph_type = placeholder.placeholder_format.type
        if ph_type == 1 or ph_type == 13:  # Title
            placeholder.text = title
            if placeholder.text_frame.paragraphs[0].runs:
                run = placeholder.text_frame.paragraphs[0].runs[0]
                _apply_text_style(run, style.title_font, style.title_font_size,
                                   bold=True, color_hex=style.heading_color)
        elif ph_type == 2 or ph_type == 15:  # Subtitle/Body
            placeholder.text = subtitle
            if placeholder.text_frame.paragraphs[0].runs:
                run = placeholder.text_frame.paragraphs[0].runs[0]
                _apply_text_style(run, style.body_font, style.body_font_size,
                                   color_hex=style.body_color)
    return slide


def _add_content_slide(
    prs: "Presentation",
    slide_content: SlideContent,
    style: StyleProfile,
    layout_index: int = 1,
):
    """Add a content slide with title and body."""
    # Pick layout
    try:
        layout = prs.slide_layouts[layout_index]
    except IndexError:
        layout = prs.slide_layouts[1]

    slide = prs.slides.add_slide(layout)

    # Build idx → placeholder map (idx 0=title, idx 1=body/content)
    ph_map = {ph.placeholder_format.idx: ph for ph in slide.placeholders}

    # --- Title (idx 0) ---
    title_ph = ph_map.get(0)
    if title_ph:
        title_ph.text = slide_content.title
        if title_ph.text_frame.paragraphs[0].runs:
            _apply_text_style(
                title_ph.text_frame.paragraphs[0].runs[0],
                style.title_font, min(style.title_font_size, 28),
                bold=True, color_hex=style.heading_color,
            )

    # --- Body (idx 1) ---
    body_ph = ph_map.get(1)
    if body_ph:
        tf = body_ph.text_frame
        tf.clear()
        tf.word_wrap = True

        def _clean(text: str) -> str:
            """Strip markdown bold/italic markers."""
            import re
            text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
            text = re.sub(r'\*(.*?)\*', r'\1', text)
            return text.strip("•- \t")

        points = slide_content.bullet_points
        if not points and slide_content.content:
            points = [slide_content.content[:600]]

        for i, point in enumerate(points):
            clean_point = _clean(point)
            if not clean_point:
                continue
            para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            para.text = clean_point
            para.level = 0
            if para.runs:
                _apply_text_style(
                    para.runs[0], style.body_font, style.body_font_size,
                    color_hex=style.body_color,
                )

    # Add speaker notes
    if slide_content.speaker_notes:
        try:
            notes_slide = slide.notes_slide
            notes_slide.notes_text_frame.text = slide_content.speaker_notes
        except Exception:
            pass

    return slide


def _add_section_header_slide(prs: "Presentation", title: str, style: StyleProfile):
    """Add a section divider slide."""
    try:
        layout = prs.slide_layouts[2]  # Section Header layout
    except IndexError:
        layout = prs.slide_layouts[0]
    slide = prs.slides.add_slide(layout)
    for placeholder in slide.placeholders:
        ph_type = placeholder.placeholder_format.type
        if ph_type in (1, 13, 3):
            placeholder.text = title
            if placeholder.text_frame.paragraphs[0].runs:
                run = placeholder.text_frame.paragraphs[0].runs[0]
                _apply_text_style(run, style.title_font, style.title_font_size,
                                   bold=True, color_hex=style.heading_color)
    return slide


def build_pptx(
    slides: list[SlideContent],
    style: StyleProfile,
    title: str,
    subtitle: str = "",
    output_dir: Optional[str] = None,
    citations: Optional[list[str]] = None,
    version_id: Optional[str] = None,
) -> str:
    """
    Build a styled PPTX presentation from slide content and a StyleProfile.

    Args:
        slides: List of SlideContent objects (excluding title slide).
        style: StyleProfile from template analysis.
        title: Presentation title.
        subtitle: Subtitle for the title slide.
        output_dir: Directory to save the file.
        citations: Optional list of citations for final slide.
        version_id: Optional version identifier.

    Returns:
        Absolute path to the generated .pptx file.
    """
    if not PPTX_AVAILABLE:
        raise ImportError("python-pptx required: pip install python-pptx")

    prs = Presentation()
    prs.slide_width = Inches(style.slide_width)
    prs.slide_height = Inches(style.slide_height)

    # 1. Title slide
    _add_title_slide(prs, title, subtitle or f"Generated Presentation — {title}", style)

    # 2. Content slides
    for i, slide_content in enumerate(slides):
        layout_idx = 1  # default "Title and Content"
        _add_content_slide(prs, slide_content, style, layout_index=layout_idx)

    # 3. Citations slide
    if citations:
        cite_content = SlideContent(
            title="References & Sources",
            content="",
            bullet_points=[f"[{i+1}] {c}" for i, c in enumerate(citations[:10])],
            speaker_notes="Sources used for generating this presentation.",
        )
        _add_content_slide(prs, cite_content, style, layout_index=1)

    # 4. Thank You / End slide
    end_slide_content = SlideContent(
        title="Thank You",
        content="Questions & Discussion",
        bullet_points=[],
    )
    _add_title_slide(prs, "Thank You", "Questions & Discussion", style)

    # Save
    out_dir = Path(output_dir or settings.generated_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vid = version_id or str(uuid.uuid4())[:8]
    safe_title = re.sub(r"[^\w\s-]", "", title)[:40].strip().replace(" ", "_")
    filename = f"{safe_title}_{vid}.pptx"
    file_path = out_dir / filename
    prs.save(str(file_path))
    logger.info(f"PPTX saved: {file_path}")
    return str(file_path)
