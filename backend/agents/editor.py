"""
editor.py — Conversational Editor Agent.
Modifies existing DOCX/PPTX artifacts based on natural-language instructions,
preserving formatting and structure.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from loguru import logger

from backend.config import settings
from backend.tools.docx_parser import parse_docx
from backend.tools.pptx_parser import parse_pptx
from backend.tools.style_extractor import StyleProfile, extract_style_from_docx, extract_style_from_pptx
from backend.generators.docx_builder import DocumentSection, build_docx, ImageData
from backend.generators.pptx_builder import SlideContent, build_pptx
from backend.versioning.version_manager import get_version_manager

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


def _get_groq_client() -> "Groq":
    if not GROQ_AVAILABLE:
        raise ImportError("groq required: pip install groq")
    return Groq(api_key=settings.groq_api_key)


def _parse_edit_intent(instruction: str, client: "Groq") -> dict:
    """Parse user edit instruction into structured intent."""
    prompt = f"""You are a document editing assistant. Analyze this editing instruction and return a JSON object:

Instruction: "{instruction}"

Return ONLY JSON:
{{
  "action": "add_section" | "remove_section" | "modify_section" | "rewrite" | "make_concise" | "add_bullet" | "update_tone" | "other",
  "target": "section name or 'all' or 'introduction' etc.",
  "details": "brief description of what to do",
  "new_section_heading": "if adding a section, its heading (else null)"
}}"""

    from backend.tools.llm_utils import safe_groq_completion
    raw = safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )
    from backend.tools.json_utils import parse_llm_json
    intent = parse_llm_json(raw, default={"action": "other", "target": "all", "details": instruction})
    return intent if isinstance(intent, dict) else {"action": "other", "target": "all", "details": instruction}


def _generate_new_section(heading: str, instruction: str, doc_context: str, style: StyleProfile,
                           client: "Groq") -> str:
    """Generate content for a new section."""
    prompt = f"""Write a professional "{heading}" section for a document.
Instruction: {instruction}
Style: {style.to_prompt_description()}
Existing document context:
{doc_context[:1500]}

Write 150-250 words. Use bullet points where appropriate (start with '• ')."""

    from backend.tools.llm_utils import safe_groq_completion
    return safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=500,
    )


def _make_content_concise(content: str, client: "Groq") -> str:
    """Make content more concise using LLM."""
    prompt = f"""Make this content more concise. Preserve key points. Remove redundancy:

{content[:2000]}

Return only the revised content."""

    from backend.tools.llm_utils import safe_groq_completion
    return safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=600,
    )


def edit_docx(
    file_path: str,
    instruction: str,
    artifact_id: str,
    extra_context: str = "",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Apply a natural-language edit instruction to an existing DOCX file.

    Args:
        file_path: Path to existing DOCX.
        instruction: Natural language edit instruction.
        artifact_id: Artifact ID for versioning.
        extra_context: Additional research or context.
        output_dir: Output directory.

    Returns:
        Result dict with new file_path, version, changes made.
    """
    logger.info(f"[Editor] Editing DOCX: '{instruction[:60]}'")
    client = _get_groq_client()

    try:
        # Parse existing document
        doc = parse_docx(file_path)
        style = extract_style_from_docx(doc)
        intent = _parse_edit_intent(instruction, client)
        logger.info(f"[Editor] Intent: {intent}")

        # Build sections from existing doc
        sections: list[DocumentSection] = []
        for sec in doc.sections:
            sections.append(DocumentSection(
                heading=sec["heading"],
                content=sec["content"],
                level=1,
            ))

        action = intent.get("action", "other")
        changes_made = []

        if action == "add_section":
            new_heading = intent.get("new_section_heading") or "New Section"
            new_content = _generate_new_section(
                new_heading, instruction, doc.full_text, style, client
            )
            sections.append(DocumentSection(heading=new_heading, content=new_content, level=1))
            changes_made.append(f"Added new section: '{new_heading}'")

        elif action == "make_concise":
            for i, sec in enumerate(sections):
                sections[i] = DocumentSection(
                    heading=sec.heading,
                    content=_make_content_concise(sec.content, client),
                    level=sec.level,
                )
            changes_made.append("Made all sections more concise.")

        elif action == "remove_section":
            target = intent.get("target", "").lower()
            before = len(sections)
            sections = [s for s in sections if target not in s.heading.lower()]
            changes_made.append(f"Removed {before - len(sections)} section(s) matching '{target}'")

        elif action in ("modify_section", "update_tone"):
            target = intent.get("target", "").lower()
            for i, sec in enumerate(sections):
                if target == "all" or target in sec.heading.lower():
                    new_content = _generate_new_section(
                        sec.heading, instruction + " " + extra_context, doc.full_text, style, client
                    )
                    sections[i] = DocumentSection(heading=sec.heading, content=new_content, level=sec.level)
            changes_made.append(f"Modified section(s) matching '{target}'")

        else:
            # Generic rewrite
            new_content = _generate_new_section(
                "Updated Content", instruction + " " + extra_context, doc.full_text, style, client
            )
            sections.append(DocumentSection(heading="Updates", content=new_content, level=1))
            changes_made.append("Added updates section.")

        # Build new DOCX
        new_file_path = build_docx(
            sections=sections,
            style=style,
            title=Path(file_path).stem,
            output_dir=output_dir,
            version_id=artifact_id[:8],
        )

        # Version it
        vm = get_version_manager()
        version_record = vm.save_version(
            artifact_id=artifact_id,
            source_file_path=new_file_path,
            title=Path(file_path).stem,
            file_type="docx",
            description=f"Edit: {instruction[:80]}",
            metadata={"changes": changes_made},
        )

        return {
            "status": "success",
            "file_path": new_file_path,
            "artifact_id": artifact_id,
            "version": version_record.version_number,
            "changes_made": changes_made,
            "instruction": instruction,
        }

    except Exception as e:
        logger.error(f"[Editor] DOCX edit error: {e}")
        return {"status": "error", "message": str(e)}


def insert_image_to_docx(
    file_path: str,
    artifact_id: str,
    image_path: str,
    section_heading: Optional[str] = None,
    caption: Optional[str] = None,
    width_inches: float = 5.0,
    align: str = "center",
    is_logo: bool = False,
    placement_target: str = "section",  # "section", "header_logo", "top_cover"
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Insert an image or company logo/symbol into a DOCX document.
    """
    logger.info(f"[Editor] Inserting image/logo '{image_path}' into DOCX '{file_path}' (target: {placement_target})")
    try:
        doc = parse_docx(file_path)
        style = extract_style_from_docx(doc)

        # If header_logo or top_cover, attach to style profile as brand logo
        if placement_target in ("header_logo", "top_cover") or (is_logo and not section_heading):
            style.brand_logo_path = image_path

        sections: list[DocumentSection] = []
        target_found = False

        img_obj = ImageData(
            image_path=image_path,
            caption=caption,
            width_inches=float(width_inches),
            align=align.lower() if align in ("left", "center", "right") else "center",
        )

        for sec_dict in doc.sections:
            heading = sec_dict["heading"]
            content = sec_dict["content"]
            img_list = []

            # Check matching section if placement is section or specific heading provided
            if placement_target == "section" or (section_heading and section_heading.strip()):
                if (section_heading and section_heading.strip().lower() in heading.lower()) or (not section_heading and not target_found and placement_target == "section"):
                    target_found = True
                    img_list.append(img_obj)

            sections.append(DocumentSection(
                heading=heading,
                content=content,
                level=1,
                images=img_list,
            ))

        if placement_target == "section" and (not sections or not target_found):
            if sections:
                sections[0].images.append(img_obj)
            else:
                sections.append(DocumentSection(
                    heading="Overview",
                    content="",
                    level=1,
                    images=[img_obj],
                ))

        # Rebuild DOCX
        new_file_path = build_docx(
            sections=sections,
            style=style,
            title=Path(file_path).stem,
            output_dir=output_dir,
            version_id=artifact_id[:8],
        )

        # Version it
        vm = get_version_manager()
        version_record = vm.save_version(
            artifact_id=artifact_id,
            source_file_path=new_file_path,
            title=Path(file_path).stem,
            file_type="docx",
            description=f"Inserted {'logo' if is_logo else 'image'}: {Path(image_path).name}" + (f" ({caption})" if caption else ""),
            metadata={"inserted_image": image_path, "caption": caption, "section": section_heading, "is_logo": is_logo, "target": placement_target},
        )

        return {
            "status": "success",
            "file_path": new_file_path,
            "artifact_id": artifact_id,
            "version": version_record.version_number,
            "filename": Path(new_file_path).name,
            "changes_made": [f"Inserted {'logo' if is_logo else 'image'} '{Path(image_path).name}' into document"],
        }
    except Exception as e:
        logger.error(f"[Editor] Image insert error: {e}")
        return {"status": "error", "message": str(e)}



def edit_pptx(
    file_path: str,
    instruction: str,
    artifact_id: str,
    extra_context: str = "",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Apply a natural-language edit instruction to an existing PPTX file.

    Args:
        file_path: Path to existing PPTX.
        instruction: Natural language edit instruction.
        artifact_id: Artifact ID for versioning.
        extra_context: Additional context.
        output_dir: Output directory.

    Returns:
        Result dict with new file_path, version, changes made.
    """
    logger.info(f"[Editor] Editing PPTX: '{instruction[:60]}'")
    client = _get_groq_client()

    try:
        ppt = parse_pptx(file_path)
        style = extract_style_from_pptx(ppt)
        intent = _parse_edit_intent(instruction, client)

        # Build slides list
        slides: list[SlideContent] = []
        for slide in ppt.slides:
            if slide.slide_number == 1:
                continue  # Skip title slide, it stays
            text_parts = [s.text for s in slide.shapes if s.text and not s.is_title]
            bullet_points = [t.strip() for t in text_parts if t.strip()]
            slides.append(SlideContent(
                title=slide.title or f"Slide {slide.slide_number}",
                content=slide.full_text,
                bullet_points=bullet_points,
                speaker_notes=slide.notes,
            ))

        action = intent.get("action", "other")
        changes_made = []

        if action == "make_concise":
            for i, slide in enumerate(slides):
                slides[i] = SlideContent(
                    title=slide.title,
                    content=slide.content,
                    bullet_points=slide.bullet_points[:3],  # Keep top 3 bullets
                    speaker_notes=slide.speaker_notes,
                )
            changes_made.append("Reduced bullet points for conciseness.")

        elif action == "add_section":
            new_heading = intent.get("new_section_heading") or "New Section"
            new_content = _generate_new_section(new_heading, instruction, ppt.full_text, style, client)
            bullets = [line.strip("• ") for line in new_content.split("\n") if line.strip().startswith("•")][:5]
            if not bullets:
                bullets = [line.strip() for line in new_content.split("\n") if line.strip()][:4]
            slides.append(SlideContent(title=new_heading, content=new_content, bullet_points=bullets))
            changes_made.append(f"Added slide: '{new_heading}'")

        elif action == "remove_section":
            target = intent.get("target", "").lower()
            before = len(slides)
            slides = [s for s in slides if target not in s.title.lower()]
            changes_made.append(f"Removed {before - len(slides)} slide(s) matching '{target}'")

        else:
            # Generic: update all slides tone
            changes_made.append("Applied general updates to presentation.")

        # Rebuild PPTX
        title_slide = ppt.slides[0] if ppt.slides else None
        prs_title = title_slide.title if title_slide else Path(file_path).stem

        new_file_path = build_pptx(
            slides=slides,
            style=style,
            title=prs_title,
            output_dir=output_dir,
            version_id=artifact_id[:8],
        )

        vm = get_version_manager()
        version_record = vm.save_version(
            artifact_id=artifact_id,
            source_file_path=new_file_path,
            title=prs_title,
            file_type="pptx",
            description=f"Edit: {instruction[:80]}",
            metadata={"changes": changes_made},
        )

        return {
            "status": "success",
            "file_path": new_file_path,
            "artifact_id": artifact_id,
            "version": version_record.version_number,
            "changes_made": changes_made,
            "instruction": instruction,
        }

    except Exception as e:
        logger.error(f"[Editor] PPTX edit error: {e}")
        return {"status": "error", "message": str(e)}


def edit_artifact(
    file_path: str,
    instruction: str,
    artifact_id: str,
    extra_context: str = "",
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """Auto-route edit to DOCX or PPTX editor based on file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == ".docx":
        return edit_docx(file_path, instruction, artifact_id, extra_context, output_dir)
    elif ext in (".pptx", ".ppt"):
        return edit_pptx(file_path, instruction, artifact_id, extra_context, output_dir)
    else:
        return {"status": "error", "message": f"Cannot edit file type: {ext}"}
