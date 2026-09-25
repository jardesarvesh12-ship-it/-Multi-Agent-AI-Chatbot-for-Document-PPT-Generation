"""
test_docx_components.py — Verification script for DOCX generator components.
Run: python scripts/test_docx_components.py
"""
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.tools.style_extractor import StyleProfile
from backend.generators.docx_builder import (
    DocumentSection, TableData, CalloutBoxData, build_docx
)

def test_generation():
    style = StyleProfile(
        heading_font="Calibri",
        body_font="Calibri",
        heading_font_size=16.0,
        body_font_size=11.0,
        heading_color="#1A365D",
        body_color="#2D3748",
        accent_color="#2B6CB0",
        background_color="#F0F4F8",
        brand_name="Acme Enterprise Solutions",
        header_text="Acme Solutions | Technical Whitepaper",
        footer_text="Confidential - Internal Use Only",
        show_page_numbers=True,
        page_orientation="portrait",
        paper_size="letter",
    )

    sections = [
        DocumentSection(
            heading="Executive Summary",
            content="This document demonstrates **editable DOCX document component generation** with full support for:\n• Structure & Layout\n• Typography & Colors\n• Tables & Callouts\n• Headers & Footers",
            level=1,
            callout_boxes=[
                CalloutBoxData(
                    text="This feature is production-ready for automated multi-agent document generation.",
                    title="IMPORTANT NOTE",
                )
            ]
        ),
        DocumentSection(
            heading="Market Analysis & Metrics",
            content="Here is a table showing key performance indicators:",
            level=1,
            tables=[
                TableData(
                    headers=["Metric", "Target", "Achieved", "Status"],
                    rows=[
                        ["Document Quality", "95%", "99%", "Passed"],
                        ["Style Compliance", "100%", "100%", "Passed"],
                        ["Generation Speed", "< 5s", "1.2s", "Optimal"],
                    ],
                    caption="System Performance Metrics"
                )
            ]
        ),
        DocumentSection(
            heading="Markdown Component Parsing Test",
            content="Below is a inline Markdown table generated inside text:\n\n| Feature | Supported | Description |\n| --- | --- | --- |\n| Headers/Footers | Yes | Running brand headers and page field |\n| Zebra Tables | Yes | Alternating shaded table rows |\n| Callouts | Yes | Highlight boxes with accent borders |\n\n> [!TIP] Markdown callout blocks are also parsed dynamically!",
            level=1,
        )
    ]

    out_path = build_docx(
        sections=sections,
        style=style,
        title="Comprehensive DOCX Component Report",
        subtitle="Full Specification & Implementation Test",
        author="Acme AI Systems",
        citations=["https://python-docx.readthedocs.io", "AI Document Generation Architecture v2.0"]
    )

    print(f"Successfully generated DOCX file: {out_path}")
    assert Path(out_path).exists(), "File should exist"
    print("Verification passed!")

if __name__ == "__main__":
    test_generation()
