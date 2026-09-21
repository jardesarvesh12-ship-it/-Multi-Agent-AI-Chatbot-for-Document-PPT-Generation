"""
vector_store.py — ChromaDB vector store interface for enterprise RAG.
Provides add, search and delete operations using local persistent storage.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("chromadb not installed: pip install chromadb")

from backend.config import settings as app_settings


class VectorStore:
    """
    Wrapper around ChromaDB for persistent document storage and retrieval.
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb required: pip install chromadb")

        self.persist_dir = persist_dir or app_settings.chroma_persist_dir
        self.collection_name = collection_name or app_settings.chroma_collection_name

        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            f"ChromaDB initialized: collection='{self.collection_name}' "
            f"at '{self.persist_dir}' "
            f"({self.collection.count()} documents)"
        )

    def add_documents(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: Optional[list[dict]] = None,
        ids: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Add documents with pre-computed embeddings to ChromaDB.

        Args:
            texts: Document text chunks.
            embeddings: Pre-computed embedding vectors.
            metadatas: Optional metadata for each chunk.
            ids: Optional IDs; auto-generated if None.

        Returns:
            List of stored document IDs.
        """
        if not texts:
            return []

        doc_ids = ids or [str(uuid.uuid4()) for _ in texts]
        metas = metadatas or [{} for _ in texts]

        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metas,
            ids=doc_ids,
        )
        logger.info(f"Added {len(texts)} chunks to ChromaDB collection '{self.collection_name}'")
        return doc_ids

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search for similar documents using a query embedding.

        Args:
            query_embedding: Query vector.
            n_results: Number of results to return.
            where: Optional ChromaDB filter dict.

        Returns:
            List of dicts with 'text', 'metadata', 'distance', 'id'.
        """
        count = self.collection.count()
        if count == 0:
            return []

        n_results = min(n_results, count)
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self.collection.query(**kwargs)

        output = []
        for i, doc in enumerate(results["documents"][0]):
            output.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "id": results["ids"][0][i],
            })
        return output

    def delete_by_source(self, source: str):
        """Delete all chunks from a specific source file."""
        try:
            self.collection.delete(where={"source": source})
            logger.info(f"Deleted chunks from source: {source}")
        except Exception as e:
            logger.warning(f"Could not delete chunks for source '{source}': {e}")

    def get_count(self) -> int:
        """Return total number of stored documents."""
        return self.collection.count()

    def list_sources(self) -> list[str]:
        """Return unique source file paths stored in the collection."""
        if self.collection.count() == 0:
            return []
        results = self.collection.get(include=["metadatas"])
        sources = list({m.get("source", "") for m in results["metadatas"] if m.get("source")})
        return sorted(sources)


# Singleton instance
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Return the singleton VectorStore instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
