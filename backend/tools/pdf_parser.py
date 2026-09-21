"""
pdf_parser.py — PDF parsing using PyMuPDF (fitz).
Extracts text, images, tables, and metadata from PDF files.
Falls back to OCR for scanned/image-only pages.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not installed. Install via: pip install PyMuPDF")

from backend.tools.ocr import image_to_text
from PIL import Image


@dataclass
class PDFPage:
    page_number: int
    text: str
    images: list[dict] = field(default_factory=list)
    is_scanned: bool = False
    width: float = 0.0
    height: float = 0.0


@dataclass
class PDFDocument:
    file_path: str
    total_pages: int
    pages: list[PDFPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    full_text: str = ""

    @property
    def is_scanned(self) -> bool:
        """True if more than half the pages appear to be scanned images."""
        if not self.pages:
            return False
        scanned = sum(1 for p in self.pages if p.is_scanned)
        return scanned > len(self.pages) / 2


def parse_pdf(file_path: str | Path, use_ocr_fallback: bool = True) -> PDFDocument:
    """
    Parse a PDF file and extract all text content.

    Args:
        file_path: Path to the PDF file.
        use_ocr_fallback: If True, apply OCR to image-only pages.

    Returns:
        PDFDocument with all extracted content.
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError("PyMuPDF required: pip install PyMuPDF")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    pages: list[PDFPage] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text").strip()
        images_info = []
        is_scanned = False

        # Detect scanned/image-only page
        if not text and use_ocr_fallback:
            is_scanned = True
            # Render page to image and OCR it
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR accuracy
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            pil_image = Image.open(io.BytesIO(img_bytes))
            text = image_to_text(pil_image)
            logger.info(f"Page {page_num + 1}: OCR applied (scanned/image page)")

        # Extract image references
        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = doc.extract_image(xref)
            images_info.append({
                "index": img_index,
                "width": base_image.get("width", 0),
                "height": base_image.get("height", 0),
                "colorspace": base_image.get("colorspace", ""),
                "ext": base_image.get("ext", ""),
            })

        rect = page.rect
        pages.append(PDFPage(
            page_number=page_num + 1,
            text=text,
            images=images_info,
            is_scanned=is_scanned,
            width=rect.width,
            height=rect.height,
        ))

    metadata = doc.metadata or {}
    full_text = "\n\n".join(p.text for p in pages if p.text)
    doc.close()

    return PDFDocument(
        file_path=str(path),
        total_pages=len(pages),
        pages=pages,
        metadata=metadata,
        full_text=full_text,
    )


def pdf_to_chunks(pdf_doc: PDFDocument, chunk_size: int = 1000, overlap: int = 100) -> list[dict]:
    """
    Split PDF content into overlapping chunks for RAG indexing.

    Args:
        pdf_doc: Parsed PDFDocument.
        chunk_size: Characters per chunk.
        overlap: Overlap between chunks.

    Returns:
        List of chunk dicts with text and metadata.
    """
    chunks = []
    for page in pdf_doc.pages:
        text = page.text
        if not text:
            continue
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk_text = text[start:end]
            chunks.append({
                "text": chunk_text,
                "source": pdf_doc.file_path,
                "page": page.page_number,
                "is_scanned": page.is_scanned,
            })
            start += chunk_size - overlap
    return chunks
