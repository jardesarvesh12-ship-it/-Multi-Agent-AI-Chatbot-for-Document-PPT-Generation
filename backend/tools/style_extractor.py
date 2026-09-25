"""
style_extractor.py — Unified style extraction from DOCX and PPTX files.
Produces a StyleProfile that can be used to guide generation agents.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from loguru import logger


@dataclass
class StyleProfile:
    """
    Unified representation of document/presentation visual style.
    Used by generators to replicate tone, structure and formatting.
    """
    # Fonts
    heading_font: str = "Calibri"
    body_font: str = "Calibri"
    heading_font_size: float = 16.0
    body_font_size: float = 11.0

    # Colors
    heading_color: Optional[str] = None
    body_color: Optional[str] = None
    accent_color: Optional[str] = None
    background_color: Optional[str] = None

    # Layout & Margins
    margins: dict = field(default_factory=lambda: {
        "top": 1.0, "bottom": 1.0, "left": 1.0, "right": 1.0
    })
    line_spacing: float = 1.15
    space_after_para: float = 6.0       # pt after paragraphs
    space_before_heading: float = 12.0  # pt before headings
    page_orientation: str = "portrait"  # portrait / landscape
    paper_size: str = "letter"          # letter / a4

    # Branding & Header/Footer
    brand_name: Optional[str] = None
    brand_logo_path: Optional[str] = None
    header_text: Optional[str] = None
    footer_text: Optional[str] = None
    show_page_numbers: bool = True

    # Content style signals
    tone: str = "professional"          # professional / casual / academic / technical
    formality: str = "formal"           # formal / semi-formal / informal
    avg_sentence_length: int = 20       # words per sentence
    uses_bullet_points: bool = True
    uses_numbered_lists: bool = True
    uses_tables: bool = False
    section_count: int = 0
    heading_style: str = "bold"         # bold / underline / color

    # PPTX-specific
    slide_width: float = 10.0
    slide_height: float = 7.5
    layout_names: list[str] = field(default_factory=list)
    title_font: str = "Calibri"
    title_font_size: float = 36.0

    # Source info
    source_file: str = ""
    file_type: str = ""  # docx / pptx / pdf

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    def to_prompt_description(self) -> str:
        """Generate a human-readable style description for LLM prompts."""
        return (
            f"Document style: {self.tone} tone, {self.formality} formality. "
            f"Fonts: heading={self.heading_font} {self.heading_font_size}pt, "
            f"body={self.body_font} {self.body_font_size}pt. "
            f"Colors: heading={self.heading_color or 'default'}, "
            f"body={self.body_color or 'default'}, accent={self.accent_color or 'default'}. "
            f"Uses bullet points: {self.uses_bullet_points}. "
            f"Average sentence length: {self.avg_sentence_length} words. "
            f"Sections: {self.section_count}."
        )


def _analyze_tone(text: str) -> tuple[str, str]:
    """Simple heuristic tone/formality detection."""
    text_lower = text.lower()
    word_count = len(text.split())
    if word_count == 0:
        return "professional", "formal"

    formal_words = {"therefore", "furthermore", "consequently", "however", "moreover",
                    "pursuant", "herein", "aforementioned", "shall", "hereby"}
    casual_words = {"we", "you", "let's", "hey", "great", "awesome", "simple", "easy"}
    technical_words = {"algorithm", "architecture", "infrastructure", "framework",
                       "implementation", "optimization", "deployment", "pipeline"}

    formal_count = sum(1 for w in formal_words if w in text_lower)
    casual_count = sum(1 for w in casual_words if w in text_lower)
    technical_count = sum(1 for w in technical_words if w in text_lower)

    if technical_count > 3:
        tone = "technical"
    elif formal_count > casual_count:
        tone = "professional"
    elif casual_count > formal_count:
        tone = "casual"
    else:
        tone = "professional"

    formality = "formal" if formal_count >= 2 else "semi-formal"
    return tone, formality


def _avg_sentence_len(text: str) -> int:
    """Estimate average sentence length in words."""
    sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    if not sentences:
        return 15
    lengths = [len(s.split()) for s in sentences]
    return int(sum(lengths) / len(lengths))


def extract_style_from_docx(docx_doc) -> StyleProfile:
    """
    Extract a StyleProfile from a parsed DocxDocument.

    Args:
        docx_doc: DocxDocument instance from docx_parser.

    Returns:
        StyleProfile instance.
    """
    style = docx_doc.style
    text = docx_doc.full_text

    tone, formality = _analyze_tone(text)

    uses_bullets = any(
        p.text.strip().startswith(("•", "-", "*", "–", "›"))
        for p in docx_doc.paragraphs
    )
    uses_numbered = any(
        p.text.strip()[:2].rstrip(".").isdigit()
        for p in docx_doc.paragraphs
        if p.text.strip()
    )

    return StyleProfile(
        heading_font=style.heading_font,
        body_font=style.body_font,
        heading_font_size=14.0,
        body_font_size=style.default_font_size,
        heading_color=style.heading_color,
        body_color=style.body_color,
        margins=style.margins if style.margins else {"top": 1.0, "bottom": 1.0, "left": 1.25, "right": 1.25},
        tone=tone,
        formality=formality,
        avg_sentence_length=_avg_sentence_len(text),
        uses_bullet_points=uses_bullets,
        uses_numbered_lists=uses_numbered,
        uses_tables=len(docx_doc.tables) > 0,
        section_count=len(docx_doc.sections),
        source_file=docx_doc.file_path,
        file_type="docx",
    )


def extract_style_from_pptx(ppt_doc) -> StyleProfile:
    """
    Extract a StyleProfile from a parsed PPTDocument.

    Args:
        ppt_doc: PPTDocument instance from pptx_parser.

    Returns:
        StyleProfile instance.
    """
    theme = ppt_doc.theme
    text = ppt_doc.full_text
    tone, formality = _analyze_tone(text)

    return StyleProfile(
        heading_font=theme.title_font,
        body_font=theme.body_font,
        heading_font_size=theme.title_font_size,
        body_font_size=theme.body_font_size,
        heading_color=theme.title_color,
        accent_color=theme.accent_color,
        background_color=theme.background_color,
        slide_width=theme.slide_width,
        slide_height=theme.slide_height,
        layout_names=ppt_doc.slide_layouts,
        title_font=theme.title_font,
        title_font_size=theme.title_font_size,
        tone=tone,
        formality=formality,
        section_count=ppt_doc.total_slides,
        source_file=ppt_doc.file_path,
        file_type="pptx",
    )
