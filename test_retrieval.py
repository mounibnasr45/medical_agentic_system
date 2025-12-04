import asyncio
import logging
import os
import json

# Force Transformers to use PyTorch and ignore TensorFlow to avoid conflicts/hangs
os.environ["USE_TORCH"] = "1"
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

from medical_agent.graph.client import get_graphiti_client
from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_retrieval():
    client = None
    try:
        logger.info("Initializing Graphiti client...")
        client = await get_graphiti_client()
        
        query = "What are the side effects of Warfarin?"
        logger.info(f"Searching for: '{query}'")
        
        # Perform Hybrid Search
        results = await client.search_(
            query, 
            group_ids=["medical_docs"], 
            config=COMBINED_HYBRID_SEARCH_RRF
        )
        
        logger.info("Search completed.")
        
        # Process Nodes
        nodes = results.nodes if results.nodes else []
        logger.info(f"Found {len(nodes)} nodes.")
        for i, node in enumerate(nodes):
            print(f"\n--- Node {i+1} ---")
            if hasattr(node, 'name'):
                print(f"Name: {node.name}")
            if hasattr(node, 'body'):
                print(f"Body: {node.body[:200]}...")
        
        # Process Edges
        edges = results.edges if results.edges else []
        logger.info(f"Found {len(edges)} edges.")
        for i, edge in enumerate(edges):
            print(f"\n--- Edge {i+1} ---")
            if hasattr(edge, 'fact'):
                print(f"Fact: {edge.fact}")

        # Process Episodes
        episodes = results.episodes if results.episodes else []
        logger.info(f"Found {len(episodes)} episodes.")
        for i, ep in enumerate(episodes):
            print(f"\n--- Episode {i+1} ---")
            if hasattr(ep, 'name'):
                print(f"Name: {ep.name}")
            if hasattr(ep, 'description'):
                print(f"Description: {ep.description[:200]}...")

    except Exception as e:
        logger.error(f"An error occurred during retrieval: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(test_retrieval())
