"""
doc_generator.py — Document Generator Agent.
Uses Groq LLM to generate DOCX content based on research, RAG context and style profile.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger

from backend.config import settings
from backend.tools.style_extractor import StyleProfile
from backend.generators.docx_builder import DocumentSection, build_docx
from backend.versioning.version_manager import get_version_manager

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger.warning("groq not installed: pip install groq")


def _get_groq_client() -> "Groq":
    if not GROQ_AVAILABLE:
        raise ImportError("groq required: pip install groq")
    return Groq(api_key=settings.groq_api_key)


def _generate_document_outline(
    topic: str,
    context: str,
    style_profile: StyleProfile,
    client: "Groq",
    section_count: int = 6,
) -> list[dict]:
    """Use LLM to generate a structured document outline."""
    style_desc = style_profile.to_prompt_description()
    prompt = f"""You are an expert document writer. Generate a professional document outline for the topic: "{topic}"

Style requirements: {style_desc}

Available research context (use this to make the outline specific and data-driven):
{context[:4500]}

Generate exactly {section_count} sections. Return ONLY a valid JSON array in this format (no markdown code blocks, no trailing commas):
[
  {{"heading": "Executive Summary", "content_brief": "3-5 sentence description of what this section covers with specific data points from the research context"}}
]

Make the outline comprehensive, professional, and well-structured. Each content_brief should be detailed enough to write 400-600 words."""

    from backend.tools.llm_utils import safe_groq_completion
    raw = safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=2000,
    )

    from backend.tools.json_utils import parse_llm_json
    outline = parse_llm_json(raw, default=[])
    return outline if isinstance(outline, list) else []


def _generate_section_content(
    heading: str,
    brief: str,
    topic: str,
    context: str,
    style_profile: StyleProfile,
    client: "Groq",
) -> str:
    """Use LLM to generate full content for one section."""
    style_desc = style_profile.to_prompt_description()
    bullet_instr = "Use bullet points where appropriate." if style_profile.uses_bullet_points else "Use flowing prose."

    prompt = f"""You are an expert document writer. Write the "{heading}" section for a document about: "{topic}"

Section brief: {brief}

Style: {style_desc}
Formatting: {bullet_instr}

Use this research context extensively — include specific facts, statistics, quotes, and examples:
{context[:4000]}

Write 400-600 words. Be highly specific, professional, and informative. Include:
- Specific data points, numbers, and statistics from the research
- Real-world examples and use cases
- Expert insights and current trends
- Actionable insights relevant to {topic}
Format using bullet points starting with '• ' where appropriate for lists. Use flowing prose for analysis paragraphs."""

    from backend.tools.llm_utils import safe_groq_completion
    return safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=1500,
    )


def generate_document(
    topic: str,
    research_context: str = "",
    rag_context: str = "",
    style_profile: Optional[StyleProfile] = None,
    citations: Optional[list[str]] = None,
    artifact_id: Optional[str] = None,
    section_count: int = 8,
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate a professional DOCX document using LLM + RAG + research context.

    Args:
        topic: Document topic/title.
        research_context: Web research content.
        rag_context: Enterprise RAG context.
        style_profile: StyleProfile from uploaded template.
        citations: List of citation strings.
        artifact_id: Existing artifact ID (for versioning) or None to create new.
        section_count: Number of sections to generate.
        output_dir: Output directory.

    Returns:
        Result dict with 'file_path', 'artifact_id', 'version', 'sections'.
    """
    if not GROQ_AVAILABLE:
        return {"status": "error", "message": "groq package not installed"}

    logger.info(f"[DocGenerator] Generating document: '{topic}'")
    client = _get_groq_client()

    # Use default style if none provided
    if style_profile is None:
        style_profile = StyleProfile()

    # Combine contexts
    combined_context = "\n\n".join(filter(None, [research_context, rag_context]))

    try:
        # 1. Generate outline
        logger.info("[DocGenerator] Generating outline...")
        outline = _generate_document_outline(topic, combined_context, style_profile, client, section_count)

        if not outline:
            # Fallback outline
            outline = [
                {"heading": "Executive Summary", "content_brief": f"Overview of {topic}"},
                {"heading": "Introduction", "content_brief": f"Background and context of {topic}"},
                {"heading": "Key Findings", "content_brief": "Main research findings"},
                {"heading": "Analysis", "content_brief": "Detailed analysis"},
                {"heading": "Recommendations", "content_brief": "Actionable recommendations"},
                {"heading": "Conclusion", "content_brief": "Summary and next steps"},
            ]

        # 2. Generate content for each section
        sections: list[DocumentSection] = []
        logger.info(f"[DocGenerator] Generating {len(outline)} sections...")
        for item in outline:
            heading = item.get("heading", "Section")
            brief = item.get("content_brief", "")
            content = _generate_section_content(
                heading, brief, topic, combined_context, style_profile, client
            )
            sections.append(DocumentSection(heading=heading, content=content, level=1))
            logger.info(f"[DocGenerator] Section done: '{heading}'")

        # 3. Build DOCX
        vm = get_version_manager()
        if not artifact_id:
            artifact_id = vm.create_artifact(topic, "docx")

        file_path = build_docx(
            sections=sections,
            style=style_profile,
            title=topic,
            output_dir=output_dir,
            citations=citations,
            version_id=artifact_id[:8],
        )

        # 4. Save version
        version_record = vm.save_version(
            artifact_id=artifact_id,
            source_file_path=file_path,
            title=topic,
            file_type="docx",
            description=f"Generated document: {topic}",
            metadata={"section_count": len(sections), "has_citations": bool(citations)},
        )

        logger.info(f"[DocGenerator] Document ready: {file_path}")
        return {
            "status": "success",
            "file_path": file_path,
            "artifact_id": artifact_id,
            "version": version_record.version_number,
            "sections": [{"heading": s.heading, "content_preview": s.content[:100]} for s in sections],
            "citations": citations or [],
        }

    except Exception as e:
        logger.error(f"[DocGenerator] Error: {e}")
        return {"status": "error", "message": str(e)}
