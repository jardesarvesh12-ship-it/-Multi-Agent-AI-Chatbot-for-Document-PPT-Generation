"""
ppt_analyzer.py — PPT Analyzer Agent.
Analyzes uploaded PPTX files to extract slide structure, layouts, theme and style.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from backend.tools.pptx_parser import parse_pptx, pptx_to_chunks
from backend.tools.style_extractor import extract_style_from_pptx, StyleProfile
from backend.rag.retriever import get_retriever


def analyze_pptx(file_path: str, index_for_rag: bool = True) -> dict[str, Any]:
    """
    Analyze a PPTX file and optionally index it for RAG.

    Args:
        file_path: Path to the .pptx file.
        index_for_rag: If True, index slide content into ChromaDB.

    Returns:
        Analysis result dict with slides, theme, style and status.
    """
    path = Path(file_path)
    if path.suffix.lower() not in {".pptx", ".ppt"}:
        return {
            "status": "error",
            "message": f"Not a PPTX file: {path.suffix}",
            "file": str(path),
        }

    logger.info(f"[PPTAnalyzer] Analyzing: {path.name}")

    result: dict[str, Any] = {
        "status": "success",
        "file": str(path),
        "file_name": path.name,
        "file_type": "pptx",
        "total_slides": 0,
        "slide_layouts": [],
        "theme": {},
        "style_profile": None,
        "slides_summary": [],
        "full_text": "",
        "chunks_indexed": 0,
    }

    try:
        ppt = parse_pptx(file_path)
        style = extract_style_from_pptx(ppt)

        result["total_slides"] = ppt.total_slides
        result["slide_layouts"] = ppt.slide_layouts
        result["theme"] = {
            "title_font": ppt.theme.title_font,
            "body_font": ppt.theme.body_font,
            "title_font_size": ppt.theme.title_font_size,
            "body_font_size": ppt.theme.body_font_size,
            "title_color": ppt.theme.title_color,
            "accent_color": ppt.theme.accent_color,
            "slide_width": ppt.theme.slide_width,
            "slide_height": ppt.theme.slide_height,
        }
        result["style_profile"] = style.to_dict()
        result["full_text"] = ppt.full_text
        result["slides_summary"] = [
            {
                "slide_number": s.slide_number,
                "title": s.title,
                "layout": s.layout_name,
                "text_preview": s.full_text[:200],
            }
            for s in ppt.slides
        ]

        if index_for_rag:
            chunks = pptx_to_chunks(ppt)
            n = get_retriever().index_chunks(chunks)
            result["chunks_indexed"] = n

        logger.info(
            f"[PPTAnalyzer] Done: {path.name} | "
            f"slides={ppt.total_slides} | "
            f"chunks={result['chunks_indexed']}"
        )

    except Exception as e:
        logger.error(f"[PPTAnalyzer] Error: {e}")
        result["status"] = "error"
        result["message"] = str(e)

    return result
