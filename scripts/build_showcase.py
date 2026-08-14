"""Pre-compute answers for the showcase queries.

The deployed demo caps visitors at a few queries per day. Showcase answers are
computed here, ahead of time, and served from disk so a visitor can explore the
system's capabilities without spending their allowance.

Run locally with a seeded graph and live API keys:

    python -m scripts.build_showcase

Writes data/showcase.json, which is committed so the deployment ships with it.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medical_agent import pipeline  # noqa: E402
from medical_agent.config import Config  # noqa: E402
from medical_agent.utils import showcase  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("showcase")


async def build() -> int:
    if not Config.GROQ_API_KEY:
        logger.error("GROQ_API_KEY is required to compute showcase answers.")
        return 1

    answers: dict[str, dict] = {}
    for item in showcase.SHOWCASE_QUERIES:
        query = item["query"]
        logger.info("Computing: %s", query)
        try:
            result = await pipeline.run_query(query=query, session_id=None)
        except Exception as exc:
            logger.error("  failed: %s", exc)
            continue

        answers[showcase.normalise(query)] = {
            "id": item["id"],
            "query": query,
            "demonstrates": item["demonstrates"],
            "response": result.response,
            "processing_mode": result.processing_mode,
            "analysis": result.analysis,
            "sources_used": result.sources_used,
            "confidence": result.confidence,
            "cot": result.cot,
            "graph_available": result.graph_available,
            "latency_ms": result.latency_ms,
        }
        logger.info("  done in %dms (%s)", result.latency_ms, result.processing_mode)

    if not answers:
        logger.error("No answers computed; leaving the existing file untouched.")
        return 1

    showcase.save(answers)
    logger.info("Wrote %d answers to %s", len(answers), showcase.SHOWCASE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(build()))
