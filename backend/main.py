"""
main.py — FastAPI Backend for Multi-Agent AI Chatbot.

Endpoints:
  POST /api/chat          — Send message + optional files to orchestrator
  POST /api/upload        — Upload template files
  GET  /api/download/{id} — Download generated artifact
  GET  /api/versions/{id} — Get version history for artifact
  GET  /api/artifacts     — List all artifacts
  GET  /api/knowledge     — Get RAG knowledge base stats
  DELETE /api/artifacts/{id} — Delete artifact
  GET  /health            — Health check
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'import backend...' works from any working directory
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)


import shutil
import uuid
from typing import Optional

import aiofiles
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pydantic import BaseModel

from backend.config import settings
from backend.agents.orchestrator import run_orchestrator
from backend.versioning.version_manager import get_version_manager
from backend.agents.rag_agent import get_knowledge_stats, list_indexed_sources
from backend.agents.editor import insert_image_to_docx
from backend.tools.docx_parser import parse_docx


# ─────────────────────────────────────────────
# App Setup
# ─────────────────────────────────────────────

app = FastAPI(
    title="Multi-Agent AI Chatbot",
    description="Enterprise-grade multi-agent system for document and PPT generation",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
Path(settings.generated_dir).mkdir(parents=True, exist_ok=True)
Path(settings.versions_dir).mkdir(parents=True, exist_ok=True)

# In-memory session store (replace with Redis for production)
session_store: dict[str, dict] = {}


# ─────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    file_ids: list[str] = []  # Previously uploaded file IDs


class ChatResponse(BaseModel):
    session_id: str
    response: str
    agent_trace: list[dict]
    generated_doc: Optional[dict] = None
    generated_ppt: Optional[dict] = None
    citations: list[str] = []
    doc_artifact_id: Optional[str] = None
    ppt_artifact_id: Optional[str] = None


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    file_type: str
    size_bytes: int
    path: str


# Helper Functions


def _validate_file_extension(filename: str) -> bool:
    ext = Path(filename).suffix.lower().lstrip(".")
    return ext in settings.allowed_ext_list


def _file_size_ok(size: int) -> bool:
    return size <= settings.max_file_size_mb * 1024 * 1024


def _artifact_info(file_path: str | None) -> Optional[dict]:
    """Build artifact download info from file path."""
    if not file_path:
        return None
    p = Path(file_path)
    if not p.exists():
        return None
    return {
        "filename": p.name,
        "size_bytes": p.stat().st_size,
        "file_path": str(p),
        "download_url": f"/api/download/{p.name}",
    }


# Endpoints


@app.get("/")
async def root():
    """Root endpoint with service status and documentation link."""
    return {
        "status": "online",
        "service": "Multi-Agent AI Chatbot for Document & PPT Generation",
        "docs": "/api/docs",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "knowledge_chunks": get_knowledge_stats().get("total_chunks", 0),
    }


@app.post("/api/upload", response_model=list[UploadResponse])
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Upload template files (DOCX, PDF, PPTX, images).
    Returns file IDs to include in subsequent chat requests.
    """
    results = []
    for file in files:
        # Validate
        if not _validate_file_extension(file.filename or ""):
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed: {file.filename}. Allowed: {settings.allowed_extensions}"
            )

        content = await file.read()
        if not _file_size_ok(len(content)):
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file.filename}. Max size: {settings.max_file_size_mb}MB"
            )

        # Save to uploads dir
        file_id = str(uuid.uuid4())
        ext = Path(file.filename).suffix.lower()
        safe_name = f"{file_id}{ext}"
        dest_path = Path(settings.upload_dir) / safe_name

        async with aiofiles.open(str(dest_path), "wb") as f:
            await f.write(content)

        results.append(UploadResponse(
            file_id=file_id,
            filename=file.filename,
            file_type=ext.lstrip("."),
            size_bytes=len(content),
            path=str(dest_path),
        ))
        logger.info(f"Uploaded: {file.filename} → {dest_path}")

    return results


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chat endpoint. Routes user message through multi-agent orchestrator.

    Accepts:
      - message: User's natural language request
      - session_id: For multi-turn conversation continuity
      - file_ids: IDs of previously uploaded files to process
    """
    # Resolve file paths from file_ids
    file_paths: list[str] = []
    for fid in request.file_ids:
        # Match file_id prefix in uploads dir
        matches = list(Path(settings.upload_dir).glob(f"{fid}*"))
        if matches:
            file_paths.append(str(matches[0]))

    # Load prior session state
    prior_state = session_store.get(request.session_id)

    # Add any new uploaded paths to the session
    if prior_state and file_paths:
        existing = prior_state.get("uploaded_files", [])
        file_paths = list({*existing, *file_paths})

    logger.info(
        f"[API] chat | session={request.session_id} | "
        f"files={len(file_paths)} | msg='{request.message[:60]}'"
    )

    try:
        result = run_orchestrator(
            user_message=request.message,
            uploaded_files=file_paths,
            session_id=request.session_id,
            prior_state=prior_state,
        )
    except Exception as e:
        logger.error(f"[API] Orchestrator error: {e}")
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Save updated session state
    session_store[request.session_id] = {
        "messages": result.get("messages", []),
        "uploaded_files": result.get("uploaded_files", []),
        "doc_style_profile": result.get("doc_style_profile"),
        "ppt_style_profile": result.get("ppt_style_profile"),
        "generated_doc_path": result.get("generated_doc_path"),
        "generated_ppt_path": result.get("generated_ppt_path"),
        "doc_artifact_id": result.get("doc_artifact_id"),
        "ppt_artifact_id": result.get("ppt_artifact_id"),
        "citations": result.get("citations", []),
    }

    return ChatResponse(
        session_id=request.session_id,
        response=result.get("final_response", "Task completed."),
        agent_trace=result.get("agent_trace", []),
        generated_doc=_artifact_info(result.get("generated_doc_path")),
        generated_ppt=_artifact_info(result.get("generated_ppt_path")),
        citations=result.get("citations", []),
        doc_artifact_id=result.get("doc_artifact_id"),
        ppt_artifact_id=result.get("ppt_artifact_id"),
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    """Download a generated file (DOCX or PPTX)."""
    # Search in generated and versions dirs
    search_dirs = [settings.generated_dir, settings.versions_dir]
    for d in search_dirs:
        fp = Path(d) / filename
        if fp.exists():
            media_type = (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                if filename.endswith(".docx") else
                "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
            return FileResponse(
                path=str(fp),
                filename=filename,
                media_type=media_type,
            )
    raise HTTPException(status_code=404, detail=f"File not found: {filename}")


@app.get("/api/versions/{artifact_id}")
async def get_versions(artifact_id: str):
    """Get version history for an artifact."""
    vm = get_version_manager()
    versions = vm.get_versions(artifact_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No versions found for artifact: {artifact_id}")
    return {"artifact_id": artifact_id, "versions": versions}


@app.get("/api/artifacts")
async def list_artifacts():
    """List all tracked artifacts."""
    vm = get_version_manager()
    return {"artifacts": vm.list_artifacts()}


@app.delete("/api/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str):
    """Delete all versions of an artifact."""
    vm = get_version_manager()
    vm.delete_artifact(artifact_id)
    return {"status": "deleted", "artifact_id": artifact_id}


@app.get("/api/document/{artifact_id}/sections")
async def get_document_sections(artifact_id: str):
    """Get list of headings/sections in the latest version of a document artifact."""
    vm = get_version_manager()
    versions = vm.get_versions(artifact_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"No versions found for artifact: {artifact_id}")

    latest_file = versions[-1].get("file_path") or versions[-1].get("path")
    if not latest_file or not Path(latest_file).exists():
        raise HTTPException(status_code=404, detail="Document file missing")

    try:
        doc = parse_docx(latest_file)
        sections = [sec["heading"] for sec in doc.sections if sec.get("heading")]
        return {"artifact_id": artifact_id, "sections": sections}
    except Exception as e:
        logger.error(f"Error parsing document sections: {e}")
        return {"artifact_id": artifact_id, "sections": []}


@app.post("/api/document/insert-image")
async def insert_image_into_document(
    artifact_id: str = Form(...),
    image_file: Optional[UploadFile] = File(None),
    existing_image_filename: Optional[str] = Form(None),
    section_heading: Optional[str] = Form(None),
    caption: Optional[str] = Form(None),
    width_inches: float = Form(5.0),
    align: str = Form("center"),
    is_logo: bool = Form(False),
    placement_target: str = Form("section"),
    session_id: Optional[str] = Form(None),
):
    """
    Insert an image or logo into a DOCX document artifact.
    Accepts an uploaded image file OR the filename of an already uploaded image.
    """
    vm = get_version_manager()
    versions = vm.get_versions(artifact_id)
    if not versions:
        raise HTTPException(status_code=404, detail=f"Artifact not found: {artifact_id}")

    latest = versions[-1]
    doc_path = latest.get("file_path") or latest.get("path")
    if not doc_path or not Path(doc_path).exists():
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    # Resolve image path
    image_path: Optional[str] = None
    if image_file and image_file.filename:
        ext = Path(image_file.filename).suffix.lower()
        if ext.lstrip(".") not in ("png", "jpg", "jpeg", "webp", "tiff", "bmp", "gif"):
            raise HTTPException(status_code=400, detail=f"Unsupported image type: {ext}")

        content = await image_file.read()
        if not _file_size_ok(len(content)):
            raise HTTPException(status_code=413, detail="Image file too large")

        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}{ext}"
        dest_path = Path(settings.upload_dir) / safe_name

        async with aiofiles.open(str(dest_path), "wb") as f:
            await f.write(content)

        image_path = str(dest_path)
    elif existing_image_filename:
        candidate = Path(settings.upload_dir) / existing_image_filename
        if candidate.exists():
            image_path = str(candidate)
        else:
            matches = list(Path(settings.upload_dir).glob(f"*{existing_image_filename}*"))
            if matches:
                image_path = str(matches[0])

    if not image_path:
        raise HTTPException(status_code=400, detail="Please upload or select an image file.")

    res = insert_image_to_docx(
        file_path=doc_path,
        artifact_id=artifact_id,
        image_path=image_path,
        section_heading=section_heading,
        caption=caption,
        width_inches=width_inches,
        align=align,
        is_logo=is_logo,
        placement_target=placement_target,
    )

    if res.get("status") == "error":
        raise HTTPException(status_code=500, detail=res.get("message", "Failed to insert image"))

    if session_id and session_id in session_store:
        session_store[session_id]["generated_doc_path"] = res["file_path"]

    artifact_info = _artifact_info(res["file_path"])
    return {
        "status": "success",
        "doc_artifact_id": artifact_id,
        "version": res["version"],
        "generated_doc": artifact_info,
        "message": f"Successfully inserted image into document (Version {res['version']})",
    }



@app.get("/api/knowledge")
async def knowledge_stats():
    """Get enterprise knowledge base statistics."""
    stats = get_knowledge_stats()
    return {
        "total_chunks": stats.get("total_chunks", 0),
        "sources": stats.get("sources", []),
        "source_count": len(stats.get("sources", [])),
    }


@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get current session state (for UI restoration)."""
    state = session_store.get(session_id, {})
    return {
        "session_id": session_id,
        "messages": state.get("messages", []),
        "uploaded_files": [Path(f).name for f in state.get("uploaded_files", [])],
        "has_doc": bool(state.get("generated_doc_path")),
        "has_ppt": bool(state.get("generated_ppt_path")),
        "doc_artifact_id": state.get("doc_artifact_id"),
        "ppt_artifact_id": state.get("ppt_artifact_id"),
    }


@app.delete("/api/session/{session_id}")
async def clear_session(session_id: str):
    """Clear a conversation session."""
    session_store.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level.lower(),
    )
