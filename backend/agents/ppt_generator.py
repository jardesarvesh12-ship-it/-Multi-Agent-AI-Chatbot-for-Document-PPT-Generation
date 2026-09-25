"""
ppt_generator.py — PPT Generator Agent.
Uses Groq LLM to generate PPTX presentations from research, RAG context and style profile.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from loguru import logger

from backend.config import settings
from backend.tools.style_extractor import StyleProfile
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


def _generate_slide_outline(
    topic: str,
    context: str,
    style_profile: StyleProfile,
    client: "Groq",
    slide_count: int = 10,
) -> list[dict]:
    """Use LLM to generate slide-by-slide outline with rich, data-driven content."""
    prompt = f"""You are a professional presentation designer and researcher. Create a detailed {slide_count}-slide presentation for: "{topic}"

Research context (use extensively — include specific data, statistics, and facts):
{context[:4500]}

Return ONLY a valid JSON array matching this exact format (no markdown code blocks, no trailing commas, escape internal quotes):
[
  {{
    "title": "Slide Title",
    "bullet_points": [
      "Specific fact or insight with data: include numbers, percentages, or concrete examples",
      "Another data-driven point with real-world context",
      "Third substantive point citing specific trends or findings",
      "Fourth point with actionable insight or implication"
    ],
    "speaker_notes": "2-3 sentence expanded explanation of the slide's key message for the presenter"
  }}
]

Rules:
- Return ONLY valid JSON array with no extra text or markdown formatting.
- Each bullet point MUST be a complete, informative sentence (10-20 words)
- Include real statistics, percentages, and data points from the research context
- Reference specific companies, products, technologies, or market figures where available
- Speaker notes should add depth not visible on the slide
- Make slides flow logically: intro → market overview → key trends → deep analysis → use cases → challenges → future outlook → recommendations → conclusion
- Generate exactly {slide_count} slides"""

    from backend.tools.llm_utils import safe_groq_completion
    raw = safe_groq_completion(
        client=client,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=3000,
    )

    from backend.tools.json_utils import parse_llm_json
    outline = parse_llm_json(raw, default=[])
    return outline if isinstance(outline, list) else []


def generate_presentation(
    topic: str,
    research_context: str = "",
    rag_context: str = "",
    style_profile: Optional[StyleProfile] = None,
    citations: Optional[list[str]] = None,
    artifact_id: Optional[str] = None,
    slide_count: int = 10,
    output_dir: Optional[str] = None,
) -> dict[str, Any]:
    """
    Generate a professional PPTX presentation using LLM + RAG + research.

    Args:
        topic: Presentation topic/title.
        research_context: Web research content.
        rag_context: Enterprise RAG context.
        style_profile: StyleProfile from uploaded template.
        citations: Citation list.
        artifact_id: Existing artifact ID or None to create new.
        slide_count: Number of slides (excluding title + end slides).
        output_dir: Output directory.

    Returns:
        Result dict with 'file_path', 'artifact_id', 'version', 'slides'.
    """
    if not GROQ_AVAILABLE:
        return {"status": "error", "message": "groq package not installed"}

    logger.info(f"[PPTGenerator] Generating presentation: '{topic}' ({slide_count} slides)")
    client = _get_groq_client()

    if style_profile is None:
        style_profile = StyleProfile()

    combined_context = "\n\n".join(filter(None, [research_context, rag_context]))

    try:
        # 1. Generate slide outline
        logger.info("[PPTGenerator] Generating slide outline...")
        outline = _generate_slide_outline(topic, combined_context, style_profile, client, slide_count)

        if not outline:
            # Fallback outline
            outline = [
                {"title": "Agenda", "bullet_points": ["Introduction", "Key Findings", "Analysis", "Recommendations", "Conclusion"], "speaker_notes": ""},
                {"title": f"Introduction to {topic}", "bullet_points": [f"Overview of {topic}", "Why it matters", "Current landscape"], "speaker_notes": ""},
                {"title": "Key Findings", "bullet_points": ["Finding 1", "Finding 2", "Finding 3", "Impact assessment"], "speaker_notes": ""},
                {"title": "Market Analysis", "bullet_points": ["Market size", "Growth trends", "Key players", "Opportunities"], "speaker_notes": ""},
                {"title": "Technology Landscape", "bullet_points": ["Current tech", "Emerging tech", "Adoption rates", "Barriers"], "speaker_notes": ""},
                {"title": "Use Cases", "bullet_points": ["Use case 1", "Use case 2", "Use case 3", "Industry applications"], "speaker_notes": ""},
                {"title": "Competitive Analysis", "bullet_points": ["Competitor overview", "Strengths", "Weaknesses", "Differentiation"], "speaker_notes": ""},
                {"title": "Recommendations", "bullet_points": ["Recommendation 1", "Recommendation 2", "Recommendation 3", "Priority actions"], "speaker_notes": ""},
                {"title": "Implementation Roadmap", "bullet_points": ["Phase 1: Planning", "Phase 2: Execution", "Phase 3: Optimization", "Timeline"], "speaker_notes": ""},
                {"title": "Conclusion & Next Steps", "bullet_points": ["Key takeaways", "Next steps", "Call to action"], "speaker_notes": ""},
            ]

        # 2. Build SlideContent list
        slides: list[SlideContent] = []
        for item in outline:
            slides.append(SlideContent(
                title=item.get("title", "Slide"),
                content=item.get("content", ""),
                bullet_points=item.get("bullet_points", []),
                speaker_notes=item.get("speaker_notes", ""),
            ))
            logger.info(f"[PPTGenerator] Slide prepared: '{item.get('title', '?')}'")

        # 3. Build PPTX
        vm = get_version_manager()
        if not artifact_id:
            artifact_id = vm.create_artifact(topic, "pptx")

        subtitle = f"Research & Analysis — {topic}"
        file_path = build_pptx(
            slides=slides,
            style=style_profile,
            title=topic,
            subtitle=subtitle,
            output_dir=output_dir,
            citations=citations,
            version_id=artifact_id[:8],
        )

        # 4. Version it
        version_record = vm.save_version(
            artifact_id=artifact_id,
            source_file_path=file_path,
            title=topic,
            file_type="pptx",
            description=f"Generated presentation: {topic} ({len(slides)} slides)",
            metadata={"slide_count": len(slides), "has_citations": bool(citations)},
        )

        logger.info(f"[PPTGenerator] Presentation ready: {file_path}")
        return {
            "status": "success",
            "file_path": file_path,
            "artifact_id": artifact_id,
            "version": version_record.version_number,
            "slides": [{"title": s.title, "bullets": s.bullet_points} for s in slides],
            "citations": citations or [],
        }

    except Exception as e:
        logger.error(f"[PPTGenerator] Error: {e}")
        return {"status": "error", "message": str(e)}
