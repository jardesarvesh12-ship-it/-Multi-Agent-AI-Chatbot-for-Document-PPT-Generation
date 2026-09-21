"""
retriever.py — High-level RAG retrieval combining embedding + ChromaDB search.
Indexes documents and retrieves relevant context for generation agents.
"""
from __future__ import annotations

from pathlib import Path
from loguru import logger

from backend.config import settings
from backend.rag.embedder import embed_texts, embed_query
from backend.rag.vector_store import get_vector_store


class RAGRetriever:
    """
    High-level retriever that handles:
    - Indexing new documents (DOCX, PDF, PPTX chunks)
    - Retrieving relevant context for a query
    - Citing source files for transparency
    """

    def __init__(self, embedding_model: str | None = None):
        self.embedding_model = embedding_model or settings.embedding_model
        self.vector_store = get_vector_store()

    def index_chunks(self, chunks: list[dict]) -> int:
        """
        Embed and index text chunks into ChromaDB.

        Args:
            chunks: List of dicts with at least 'text' and 'source' keys.

        Returns:
            Number of chunks indexed.
        """
        if not chunks:
            return 0

        texts = [c["text"] for c in chunks]
        logger.info(f"Embedding {len(texts)} chunks...")
        embeddings = embed_texts(texts, self.embedding_model)

        # Remove existing chunks from same sources to avoid duplicates
        sources = list({c.get("source", "") for c in chunks if c.get("source")})
        for source in sources:
            self.vector_store.delete_by_source(source)

        metadatas = []
        for c in chunks:
            meta = {k: str(v) for k, v in c.items() if k != "text"}
            metadatas.append(meta)

        self.vector_store.add_documents(
            texts=texts,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.info(f"Indexed {len(chunks)} chunks successfully.")
        return len(chunks)

    def retrieve(
        self,
        query: str,
        n_results: int = 5,
        source_filter: str | None = None,
    ) -> list[dict]:
        """
        Retrieve relevant chunks for a query.

        Args:
            query: User query or generation context.
            n_results: Number of top results.
            source_filter: Optional filter to specific source file.

        Returns:
            List of result dicts with text, metadata, distance.
        """
        logger.info(f"RAG retrieving: '{query[:80]}...' (top {n_results})")
        query_vec = embed_query(query, self.embedding_model)

        where = {"source": source_filter} if source_filter else None
        results = self.vector_store.search(
            query_embedding=query_vec,
            n_results=n_results,
            where=where,
        )
        logger.info(f"RAG found {len(results)} relevant chunks")
        return results

    def retrieve_formatted(self, query: str, n_results: int = 5) -> tuple[str, list[str]]:
        """
        Retrieve context and return formatted string + citation list.

        Args:
            query: Query string.
            n_results: Top-k results.

        Returns:
            Tuple of (context_text, citations_list)
        """
        results = self.retrieve(query, n_results)
        if not results:
            return "", []

        context_parts = []
        citations = []
        seen_sources = set()

        for i, r in enumerate(results):
            context_parts.append(f"[Source {i+1}]: {r['text']}")
            src = r["metadata"].get("source", "Unknown")
            if src not in seen_sources:
                seen_sources.add(src)
                page = r["metadata"].get("page", "")
                slide = r["metadata"].get("slide", "")
                loc = f" (page {page})" if page else (f" (slide {slide})" if slide else "")
                citations.append(f"{Path(src).name}{loc}")

        return "\n\n".join(context_parts), citations

    @property
    def total_documents(self) -> int:
        return self.vector_store.get_count()

    def list_sources(self) -> list[str]:
        return self.vector_store.list_sources()


# Singleton
_retriever: RAGRetriever | None = None


def get_retriever() -> RAGRetriever:
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
    return _retriever
