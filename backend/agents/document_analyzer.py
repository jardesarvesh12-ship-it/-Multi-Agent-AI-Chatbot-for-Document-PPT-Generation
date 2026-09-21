"""
document_analyzer.py — Document Analyzer Agent.
Analyzes uploaded DOCX, PDF and image files, extracting structure, style, and content.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from backend.tools.docx_parser import parse_docx, docx_to_chunks
from backend.tools.pdf_parser import parse_pdf, pdf_to_chunks
from backend.tools.style_extractor import extract_style_from_docx, StyleProfile
from backend.tools.ocr import image_file_to_text
from backend.rag.retriever import get_retriever


SUPPORTED_DOC_EXTENSIONS = {".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def analyze_document(file_path: str, index_for_rag: bool = True) -> dict[str, Any]:
    """
    Analyze a document file and optionally index it for RAG.

    Args:
        file_path: Path to the document file.
        index_for_rag: If True, index extracted chunks into ChromaDB.

    Returns:
        Analysis result dict with structure, style, summary and status.
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext not in SUPPORTED_DOC_EXTENSIONS:
        return {
            "status": "error",
            "message": f"Unsupported document extension: {ext}",
            "file": str(path),
        }

    logger.info(f"[DocumentAnalyzer] Analyzing: {path.name}")

    result: dict[str, Any] = {
        "status": "success",
        "file": str(path),
        "file_name": path.name,
        "file_type": ext.lstrip("."),
        "style_profile": None,
        "sections": [],
        "full_text": "",
        "page_count": 0,
        "chunks_indexed": 0,
        "tables": [],
        "is_scanned": False,
    }

    try:
        if ext == ".docx":
            doc = parse_docx(file_path)
            style = extract_style_from_docx(doc)
            result["style_profile"] = style.to_dict()
            result["sections"] = doc.sections
            result["full_text"] = doc.full_text
            result["page_count"] = len(doc.paragraphs)
            result["tables"] = [
                {"rows": t.rows, "cols": t.cols, "preview": t.data[:2]}
                for t in doc.tables
            ]
            if index_for_rag:
                chunks = docx_to_chunks(doc)
                n = get_retriever().index_chunks(chunks)
                result["chunks_indexed"] = n

        elif ext == ".pdf":
            pdf = parse_pdf(file_path, use_ocr_fallback=True)
            result["full_text"] = pdf.full_text
            result["page_count"] = pdf.total_pages
            result["is_scanned"] = pdf.is_scanned
            result["sections"] = [
                {"heading": f"Page {p.page_number}", "content": p.text[:300]}
                for p in pdf.pages[:10]
            ]
            if index_for_rag:
                chunks = pdf_to_chunks(pdf)
                n = get_retriever().index_chunks(chunks)
                result["chunks_indexed"] = n

        elif ext in {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}:
            text = image_file_to_text(file_path)
            result["full_text"] = text
            result["is_scanned"] = True
            result["sections"] = [{"heading": "Image Content", "content": text[:500]}]
            if index_for_rag and text:
                n = get_retriever().index_chunks([{
                    "text": text,
                    "source": str(path),
                    "type": "image_ocr",
                }])
                result["chunks_indexed"] = n

        logger.info(
            f"[DocumentAnalyzer] Done: {path.name} | "
            f"text_len={len(result['full_text'])} | "
            f"chunks={result['chunks_indexed']}"
        )

    except Exception as e:
        logger.error(f"[DocumentAnalyzer] Error analyzing {path.name}: {e}")
        result["status"] = "error"
        result["message"] = str(e)

    return result
