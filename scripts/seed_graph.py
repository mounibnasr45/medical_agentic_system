"""Seed the knowledge graph from data/drugs.json.

Run once against an empty database, and again whenever the embedding model or
dimension changes: vectors from different models are not comparable, so the index
must be rebuilt rather than appended to.

    python -m scripts.seed_graph            # add episodes
    python -m scripts.seed_graph --reset    # wipe the graph first

Each drug becomes one episode. Graphiti extracts entities and relationships from
the text, which is why the episode body is written as prose rather than passed as
structured fields.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from medical_agent.config import Config  # noqa: E402
from medical_agent.graph.client import get_gateway  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("seed")

DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "drugs.json"
GROUP_ID = "medical_docs"
# Groq's free tier is rate limited; pace the episode calls.
DELAY_BETWEEN_EPISODES = 3.0


def build_episode(drug: dict) -> str:
    """Render one drug as prose for entity extraction."""
    parts = [f"{drug['name']}: {drug.get('description', '').strip()}"]

    for interaction in drug.get("interactions", []):
        parts.append(
            f"{drug['name']} interacts with {interaction['drug']}. "
            f"Severity: {interaction.get('severity', 'Unknown')}. "
            f"Effect: {interaction.get('effect', 'Not specified')}."
        )

    contraindications = drug.get("contraindications", [])
    if contraindications:
        parts.append(f"{drug['name']} is contraindicated in: {', '.join(contraindications)}.")
        for item in contraindications:
            parts.append(f"{drug['name']} should not be used in patients with {item}.")

    return "\n".join(parts)


def _mask(value: str | None) -> str:
    """Show enough of a secret to spot a wrong or malformed value, not enough to leak it."""
    if not value:
        return "<empty>"
    if len(value) <= 4:
        return f"<{len(value)} chars>"
    return f"{value[:2]}...{value[-2:]} ({len(value)} chars)"


async def check_connection() -> bool:
    """Verify credentials before doing anything destructive.

    Connection problems are the overwhelmingly common failure here, and the
    driver's own traceback buries the cause forty frames deep.
    """
    from neo4j import AsyncGraphDatabase
    from neo4j.exceptions import AuthError, ConfigurationError, ServiceUnavailable

    logger.info("Connecting to %s as %s", Config.NEO4J_URI, Config.NEO4J_USER)
    driver = AsyncGraphDatabase.driver(
        Config.NEO4J_URI, auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )
    try:
        await driver.verify_connectivity()
        logger.info("Connection verified")
        return True
    except AuthError:
        logger.error("Authentication rejected by Neo4j.")
        logger.error("  user:     %s", Config.NEO4J_USER)
        logger.error("  password: %s", _mask(Config.NEO4J_PASSWORD))
        logger.error("Check that:")
        logger.error("  - the password matches THIS instance (each Aura instance has its own)")
        logger.error("  - the value has no surrounding quotes, spaces or trailing characters")
        logger.error("  - an unquoted '#' in .env is not truncating it as a comment")
        logger.error("  - the user is 'neo4j' unless you created another")
        return False
    except (ServiceUnavailable, ConfigurationError) as exc:
        logger.error("Could not reach the database: %s", exc)
        logger.error("Check the URI scheme (Aura needs neo4j+s://) and that the")
        logger.error("instance is Running rather than paused in the Aura console.")
        return False
    finally:
        await driver.close()


async def reset_graph() -> None:
    """Delete all nodes. Destructive and irreversible."""
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(
        Config.NEO4J_URI, auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )
    try:
        await driver.execute_query("MATCH (n) DETACH DELETE n", database_=Config.NEO4J_DATABASE)
        logger.info("Graph cleared (database: %s)", Config.NEO4J_DATABASE)
    finally:
        await driver.close()


async def seed(reset: bool) -> int:
    if not Config.graph_configured():
        logger.error(
            "Graph is not configured. Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD and GOOGLE_API_KEY."
        )
        return 1

    drugs = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    logger.info("Loaded %d drugs from %s", len(drugs), DATA_PATH.name)

    if not await check_connection():
        return 1

    if reset:
        await reset_graph()

    client = await get_gateway().get_client()
    if client is None:
        logger.error("Could not connect to the graph: %s", get_gateway().last_error)
        return 1

    await client.build_indices_and_constraints()
    logger.info("Indices and constraints ready (embedding_dim=%d)", Config.EMBEDDING_DIM)

    failures = 0
    for index, drug in enumerate(drugs, 1):
        name = drug.get("name", f"drug-{index}")
        logger.info("[%d/%d] %s", index, len(drugs), name)
        try:
            await client.add_episode(
                name=f"Drug: {name}",
                episode_body=build_episode(drug),
                source_description="data/drugs.json",
                group_id=GROUP_ID,
                reference_time=datetime.now(UTC),
            )
        except Exception as exc:
            failures += 1
            logger.error("  failed: %s", exc)
        await asyncio.sleep(DELAY_BETWEEN_EPISODES)

    await get_gateway().close()

    if failures:
        logger.warning("Finished with %d failed episode(s)", failures)
        return 1
    logger.info("Seeding complete: %d episodes", len(drugs))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the medical knowledge graph.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete every node before seeding. Irreversible.",
    )
    args = parser.parse_args()
    return asyncio.run(seed(args.reset))


if __name__ == "__main__":
    raise SystemExit(main())
