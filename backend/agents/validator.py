"""
validator.py — Content Validator Agent.
Validates generated DOCX/PPTX files for completeness, quality and consistency.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from backend.tools.docx_parser import parse_docx
from backend.tools.pptx_parser import parse_pptx


def validate_docx(file_path: str, expected_sections: int = 3) -> dict[str, Any]:
    """
    Validate a generated DOCX file.

    Args:
        file_path: Path to the DOCX file.
        expected_sections: Minimum expected section count.

    Returns:
        Validation result with score, issues and suggestions.
    """
    logger.info(f"[Validator] Validating DOCX: {Path(file_path).name}")
    issues = []
    suggestions = []
    score = 100

    try:
        doc = parse_docx(file_path)
        text = doc.full_text

        # Check 1: Non-empty content
        if len(text) < 200:
            issues.append("Document content is too short (< 200 characters).")
            score -= 20
            suggestions.append("Ask the generator to produce more detailed content.")

        # Check 2: Has headings / sections
        headings = [p for p in doc.paragraphs if p.level > 0]
        if len(headings) < expected_sections:
            issues.append(f"Only {len(headings)} headings found; expected at least {expected_sections}.")
            score -= 15
            suggestions.append("Regenerate with more sections.")

        # Check 3: No placeholder text
        placeholder_markers = ["[PLACEHOLDER]", "INSERT HERE", "TODO", "Lorem ipsum"]
        for marker in placeholder_markers:
            if marker.lower() in text.lower():
                issues.append(f"Placeholder text found: '{marker}'")
                score -= 10
                suggestions.append(f"Replace placeholder '{marker}' with real content.")

        # Check 4: Has references section (if citations expected)
        has_refs = any("reference" in p.text.lower() or "source" in p.text.lower()
                       for p in doc.paragraphs)
        if not has_refs:
            suggestions.append("Consider adding a References/Sources section.")

        # Check 5: Word count
        word_count = len(text.split())
        if word_count < 150:
            issues.append(f"Low word count: {word_count} words.")
            score -= 10

    except Exception as e:
        logger.error(f"[Validator] DOCX validation error: {e}")
        issues.append(f"Validation error: {e}")
        score -= 30

    score = max(0, score)
    status = "pass" if score >= 70 else "warn" if score >= 50 else "fail"

    return {
        "status": status,
        "score": score,
        "file": file_path,
        "file_type": "docx",
        "issues": issues,
        "suggestions": suggestions,
        "passed": status in ("pass", "warn"),
    }


def validate_pptx(file_path: str, expected_slides: int = 5) -> dict[str, Any]:
    """
    Validate a generated PPTX file.

    Args:
        file_path: Path to the PPTX file.
        expected_slides: Minimum expected slide count.

    Returns:
        Validation result with score, issues and suggestions.
    """
    logger.info(f"[Validator] Validating PPTX: {Path(file_path).name}")
    issues = []
    suggestions = []
    score = 100

    try:
        ppt = parse_pptx(file_path)

        # Check 1: Slide count
        if ppt.total_slides < expected_slides:
            issues.append(f"Only {ppt.total_slides} slides; expected at least {expected_slides}.")
            score -= 20
            suggestions.append("Add more slides for comprehensive coverage.")

        # Check 2: Each slide has a title
        untitled = [s for s in ppt.slides if not s.title]
        if untitled:
            issues.append(f"{len(untitled)} slides missing titles.")
            score -= 10
            suggestions.append("Ensure every slide has a clear title.")

        # Check 3: Content in slides
        empty_slides = [s for s in ppt.slides if not s.full_text.strip()]
        if empty_slides:
            issues.append(f"{len(empty_slides)} slides have no content.")
            score -= 15
            suggestions.append("Add content to empty slides.")

        # Check 4: Placeholder text
        placeholder_markers = ["[PLACEHOLDER]", "Click to edit", "INSERT TEXT", "Lorem ipsum"]
        full_text = ppt.full_text.lower()
        for marker in placeholder_markers:
            if marker.lower() in full_text:
                issues.append(f"Default placeholder found: '{marker}'")
                score -= 5

        # Check 5: Word count
        word_count = len(ppt.full_text.split())
        if word_count < 100:
            issues.append(f"Low total content: {word_count} words across all slides.")
            score -= 10

    except Exception as e:
        logger.error(f"[Validator] PPTX validation error: {e}")
        issues.append(f"Validation error: {e}")
        score -= 30

    score = max(0, score)
    status = "pass" if score >= 70 else "warn" if score >= 50 else "fail"

    return {
        "status": status,
        "score": score,
        "file": file_path,
        "file_type": "pptx",
        "issues": issues,
        "suggestions": suggestions,
        "passed": status in ("pass", "warn"),
    }


def validate_artifact(file_path: str) -> dict[str, Any]:
    """Auto-detect file type and validate accordingly."""
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return validate_docx(file_path)
    elif ext in (".pptx", ".ppt"):
        return validate_pptx(file_path)
    else:
        return {"status": "error", "message": f"Cannot validate file type: {ext}"}
