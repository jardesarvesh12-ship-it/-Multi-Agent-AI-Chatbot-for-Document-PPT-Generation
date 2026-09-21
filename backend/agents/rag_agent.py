"""
rag_agent.py — Enterprise RAG Agent.
Retrieves relevant enterprise knowledge from indexed documents using ChromaDB.
"""
from __future__ import annotations

from typing import Any
from loguru import logger

from backend.rag.retriever import get_retriever


def retrieve_knowledge(
    query: str,
    n_results: int = 5,
    source_filter: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve relevant knowledge from the enterprise vector store.

    Args:
        query: Search query.
        n_results: Number of chunks to retrieve.
        source_filter: Optional source file path to restrict search.

    Returns:
        Dict with 'context', 'citations', 'chunks', 'status'.
    """
    logger.info(f"[RAGAgent] Retrieving knowledge for: '{query[:80]}'")

    retriever = get_retriever()

    if retriever.total_documents == 0:
        logger.warning("[RAGAgent] Vector store is empty — no documents indexed yet.")
        return {
            "status": "empty",
            "message": "No documents have been indexed yet. Please upload and analyze documents first.",
            "context": "",
            "citations": [],
            "chunks": [],
        }

    try:
        context, citations = retriever.retrieve_formatted(query, n_results)
        raw_chunks = retriever.retrieve(query, n_results, source_filter)

        logger.info(
            f"[RAGAgent] Retrieved {len(raw_chunks)} chunks | "
            f"citations={len(citations)}"
        )

        return {
            "status": "success",
            "query": query,
            "context": context,
            "citations": citations,
            "chunks": raw_chunks,
            "total_indexed_docs": retriever.total_documents,
        }

    except Exception as e:
        logger.error(f"[RAGAgent] Error: {e}")
        return {
            "status": "error",
            "message": str(e),
            "context": "",
            "citations": [],
            "chunks": [],
        }


def list_indexed_sources() -> list[str]:
    """Return all source file paths currently in the vector store."""
    return get_retriever().list_sources()


def get_knowledge_stats() -> dict:
    """Return statistics about the knowledge base."""
    retriever = get_retriever()
    return {
        "total_chunks": retriever.total_documents,
        "sources": retriever.list_sources(),
    }
