"""
web_researcher.py — Web Research Agent using Tavily Search API (free tier).
Performs real-time web search and returns structured research results with citations.
"""
from __future__ import annotations

from typing import Any, Optional
from loguru import logger

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.warning("tavily-python not installed: pip install tavily-python")

from backend.config import settings


def research_topic(
    query: str,
    max_results: int = 5,
    search_depth: str = "advanced",
    include_domains: Optional[list[str]] = None,
    exclude_domains: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Perform real-time web research using Tavily Search API.

    Args:
        query: Research query string.
        max_results: Maximum number of results (1-10).
        search_depth: "basic" or "advanced" (more thorough, costs more credits).
        include_domains: Whitelist of domains to search within.
        exclude_domains: Blacklist of domains to exclude.

    Returns:
        Dict with 'summary', 'results' (list), 'citations' (list), 'status'.
    """
    if not TAVILY_AVAILABLE:
        return {
            "status": "error",
            "message": "tavily-python not installed",
            "summary": "",
            "results": [],
            "citations": [],
        }

    logger.info(f"[WebResearcher] Searching: '{query[:80]}'")

    try:
        client = TavilyClient(api_key=settings.tavily_api_key)

        kwargs: dict[str, Any] = {
            "query": query,
            "max_results": min(max_results, 10),
            "search_depth": search_depth,
            "include_answer": True,
            "include_raw_content": False,
        }
        if include_domains:
            kwargs["include_domains"] = include_domains
        if exclude_domains:
            kwargs["exclude_domains"] = exclude_domains

        response = client.search(**kwargs)

        # Extract answer / summary
        summary = response.get("answer", "")

        # Extract individual results
        results = []
        citations = []
        for r in response.get("results", []):
            url = r.get("url", "")
            title = r.get("title", "")
            content = r.get("content", "")
            score = r.get("score", 0.0)

            results.append({
                "title": title,
                "url": url,
                "content": content[:600],
                "score": score,
            })
            citations.append(f"{title} — {url}")

        logger.info(
            f"[WebResearcher] Done: {len(results)} results | "
            f"summary_len={len(summary)}"
        )

        return {
            "status": "success",
            "query": query,
            "summary": summary,
            "results": results,
            "citations": citations,
        }

    except Exception as e:
        logger.error(f"[WebResearcher] Search failed: {e}")
        return {
            "status": "error",
            "message": str(e),
            "query": query,
            "summary": "",
            "results": [],
            "citations": [],
        }


def multi_topic_research(topics: list[str], results_per_topic: int = 3) -> dict[str, Any]:
    """
    Research multiple topics and aggregate findings.

    Args:
        topics: List of research topics.
        results_per_topic: Results per topic.

    Returns:
        Aggregated research dict.
    """
    all_results = []
    all_citations = []
    summaries = []

    for topic in topics:
        res = research_topic(topic, max_results=results_per_topic)
        if res["status"] == "success":
            summaries.append(f"**{topic}**: {res['summary']}")
            all_results.extend(res["results"])
            all_citations.extend(res["citations"])

    return {
        "status": "success",
        "topics": topics,
        "combined_summary": "\n\n".join(summaries),
        "results": all_results,
        "citations": list(dict.fromkeys(all_citations)),  # deduplicate preserving order
    }
