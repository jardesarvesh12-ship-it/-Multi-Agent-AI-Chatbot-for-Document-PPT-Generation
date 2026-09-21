"""
embedder.py — Local sentence-transformer embeddings for RAG.
Uses all-MiniLM-L6-v2 by default (384-dim, very fast, no API cost).
"""
from __future__ import annotations

from typing import Optional
from loguru import logger

_model_cache: dict = {}


def get_embedding_model(model_name: str = "all-MiniLM-L6-v2"):
    """
    Load (or return cached) SentenceTransformer model.
    Lazily imported to keep server startup fast.

    Args:
        model_name: HuggingFace model identifier.

    Returns:
        Loaded SentenceTransformer model.
    """
    global _model_cache

    if model_name not in _model_cache:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError("sentence-transformers required: pip install sentence-transformers")

        logger.info(f"Loading embedding model: {model_name}")
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info(f"Embedding model loaded: {model_name}")

    return _model_cache[model_name]


def embed_texts(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> list[list[float]]:
    """
    Embed a list of text strings.

    Args:
        texts: List of text strings to embed.
        model_name: Model identifier.

    Returns:
        List of embedding vectors (each is a list of floats).
    """
    model = get_embedding_model(model_name)
    embeddings = model.encode(texts, show_progress_bar=False, convert_to_list=True)
    return embeddings


def embed_query(query: str, model_name: str = "all-MiniLM-L6-v2") -> list[float]:
    """
    Embed a single query string.

    Args:
        query: Query text.
        model_name: Model identifier.

    Returns:
        Embedding vector.
    """
    model = get_embedding_model(model_name)
    return model.encode(query, convert_to_list=True)
