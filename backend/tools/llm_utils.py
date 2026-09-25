"""
llm_utils.py — Centralized LLM completion wrapper with automatic rate-limit retry,
exponential backoff, model fallback, and prompt budgeting.
"""
from __future__ import annotations

import re
import time
from typing import Any, List, Optional
from loguru import logger

from backend.config import settings

try:
    from groq import Groq, RateLimitError
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False


FALLBACK_MODELS = [
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "allam-2-7b",
]


def safe_groq_completion(
    client: "Groq",
    messages: List[dict],
    model: Optional[str] = None,
    temperature: float = 0.3,
    max_tokens: int = 2000,
    max_retries: int = 4,
) -> str:
    """
    Execute a Groq chat completion with automatic retry on rate limits (429)
    and automatic model fallback if rate limits persist.

    Args:
        client: Instantiated Groq client.
        messages: List of chat messages.
        model: Target model name (defaults to settings.groq_model).
        temperature: Sampling temperature.
        max_tokens: Max tokens to generate.
        max_retries: Retries per model before trying next candidate.

    Returns:
        Generated text string.
    """
    if not GROQ_AVAILABLE:
        raise ImportError("groq is not installed")

    primary_model = model or settings.groq_model
    candidate_models = [primary_model] + [m for m in FALLBACK_MODELS if m != primary_model]

    for current_model in candidate_models:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content.strip()

            except Exception as e:
                err_msg = str(e)
                is_rate_limit = (
                    "429" in err_msg
                    or "rate_limit_exceeded" in err_msg
                    or "Rate limit" in err_msg
                    or isinstance(e, RateLimitError)
                )

                if is_rate_limit:
                    wait_time = 2.5
                    match = re.search(r"try again in (\d+(?:\.\d+)?)s", err_msg, re.IGNORECASE)
                    if match:
                        try:
                            wait_time = float(match.group(1)) + 0.5
                        except ValueError:
                            pass
                    else:
                        wait_time = min(2.0 ** attempt + 0.5, 10.0)

                    logger.warning(
                        f"[LLM Utils] Rate limit hit for model '{current_model}' (Attempt {attempt}/{max_retries}). "
                        f"Sleeping {wait_time:.2f}s before retry..."
                    )
                    time.sleep(wait_time)

                    if attempt == max_retries:
                        logger.warning(
                            f"[LLM Utils] Max retries reached for '{current_model}'. Falling back to next model..."
                        )
                        break
                else:
                    logger.error(f"[LLM Utils] LLM API call failed on '{current_model}': {err_msg}")
                    raise e

    raise RuntimeError(f"All LLM models failed after rate limit retries: {candidate_models}")
