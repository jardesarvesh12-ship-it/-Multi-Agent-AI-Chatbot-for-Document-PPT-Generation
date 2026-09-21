"""
ocr.py — OCR processing using Tesseract for scanned documents and images.
Supports PNG, JPG, JPEG, TIFF and image pages extracted from PDFs.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image
from loguru import logger

try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed — OCR disabled. Install via: pip install pytesseract")

# Common Tesseract install paths on Windows
_WIN_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _configure_tesseract():
    """Try to auto-detect Tesseract binary on Windows."""
    if not TESSERACT_AVAILABLE:
        return
    import platform
    if platform.system() == "Windows":
        for path in _WIN_TESSERACT_PATHS:
            if Path(path).exists():
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Tesseract found at: {path}")
                return
        logger.warning(
            "Tesseract not found at default Windows paths. "
            "Download from: https://github.com/UB-Mannheim/tesseract/wiki"
        )


_configure_tesseract()


def image_to_text(image: Image.Image, lang: str = "eng") -> str:
    """
    Extract text from a PIL Image using Tesseract OCR.

    Args:
        image: PIL Image object.
        lang: Language code (default 'eng').

    Returns:
        Extracted text string.
    """
    if not TESSERACT_AVAILABLE:
        return "[OCR unavailable — pytesseract not installed]"
    try:
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip()
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return f"[OCR error: {e}]"


def image_file_to_text(file_path: str | Path, lang: str = "eng") -> str:
    """
    Extract text from an image file.

    Args:
        file_path: Path to the image file.
        lang: Language code.

    Returns:
        Extracted text string.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {path}")

    image = Image.open(path)
    return image_to_text(image, lang=lang)


def image_bytes_to_text(data: bytes, lang: str = "eng") -> str:
    """
    Extract text from image bytes.

    Args:
        data: Raw image bytes.
        lang: Language code.

    Returns:
        Extracted text string.
    """
    image = Image.open(io.BytesIO(data))
    return image_to_text(image, lang=lang)


def get_image_info(image: Image.Image) -> dict:
    """Return basic metadata about an image."""
    return {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "format": getattr(image, "format", "unknown"),
    }
