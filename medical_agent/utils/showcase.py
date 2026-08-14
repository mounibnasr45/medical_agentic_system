"""Pre-computed showcase answers.

The public demo caps each visitor at a handful of queries per day. Spending those
on "what is aspirin" would waste them, so a curated set of questions ships with
answers already computed by `scripts/build_showcase.py`.

Showcase answers are served from disk: instant, free, and exempt from the quota.
Visitors spend their allowance only on questions of their own.

If the file is missing or empty the queries still work; they just run live and
count against the quota like anything else.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SHOWCASE_PATH = Path(__file__).resolve().parents[2] / "data" / "showcase.json"

# The questions offered as one-click examples in the UI. Chosen to exercise a
# different path each: single lookup, safety validation, multi-hop Cypher,
# parallel retrieval, and the non-medical rejection path.
SHOWCASE_QUERIES: list[dict[str, str]] = [
    {
        "id": "warfarin-basics",
        "query": "What is Warfarin used for?",
        "demonstrates": "Single-agent graph lookup",
    },
    {
        "id": "aspirin-warfarin",
        "query": "Can I take Aspirin with Warfarin?",
        "demonstrates": "Multi-agent safety validation, major interaction",
    },
    {
        "id": "aspirin-contraindications",
        "query": "Find all contraindications for Aspirin.",
        "demonstrates": "Generated Cypher, multi-hop traversal",
    },
    {
        "id": "blood-thinner-painkiller",
        "query": "What is the safest painkiller for someone on blood thinners?",
        "demonstrates": "Parallel retrieval with chain-of-thought reasoning",
    },
    {
        "id": "non-medical",
        "query": "Write me a poem about the sea.",
        "demonstrates": "Out-of-scope rejection by the router",
    },
]


def _load() -> dict[str, Any]:
    if not SHOWCASE_PATH.exists():
        return {}
    try:
        return json.loads(SHOWCASE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read showcase file: %s", exc)
        return {}


_CACHE: dict[str, Any] | None = None


def _entries() -> dict[str, Any]:
    global _CACHE
    if _CACHE is None:
        _CACHE = _load()
        if _CACHE:
            logger.info("Loaded %d showcase answers", len(_CACHE))
    return _CACHE


def normalise(query: str) -> str:
    return " ".join(query.lower().split()).rstrip("?.! ")


def lookup(query: str) -> dict[str, Any] | None:
    """Return a pre-computed answer for this query, if there is one."""
    return _entries().get(normalise(query))


def catalogue() -> list[dict[str, Any]]:
    """Showcase queries plus whether each is pre-computed, for the UI."""
    available = _entries()
    return [
        {**item, "precomputed": normalise(item["query"]) in available} for item in SHOWCASE_QUERIES
    ]


def save(answers: dict[str, Any]) -> None:
    """Write the showcase file. Used by scripts/build_showcase.py."""
    SHOWCASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SHOWCASE_PATH.write_text(json.dumps(answers, indent=2), encoding="utf-8")
    global _CACHE
    _CACHE = None
