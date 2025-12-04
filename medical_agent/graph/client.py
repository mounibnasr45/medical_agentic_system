import os
import sys
import logging
from medical_agent.config import Config
from graphiti_core import Graphiti
from medical_agent.graph.groq_client import GroqClient
from medical_agent.graph.local_embedder import LocalEmbedder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_CACHED_EMBEDDER = None

async def get_graphiti_client() -> Graphiti:
    """
    Initializes and returns the Graphiti client.
    """
    global _CACHED_EMBEDDER
    try:
        # Load from Config
        neo4j_uri = Config.NEO4J_URI
        neo4j_user = Config.NEO4J_USER
        neo4j_password = Config.NEO4J_PASSWORD
        
        groq_api_key = Config.GROQ_API_KEY

        if not all([groq_api_key, neo4j_uri, neo4j_user, neo4j_password]):
            logger.error("Missing environment variables for Graphiti connection.")
            raise ValueError("Missing environment variables")

        # Use Groq for LLM
        llm_client = GroqClient(
            api_key=groq_api_key,
            model=Config.GROQ_MODEL_NAME
        )

        # Use Local Open-Source Embeddings (no API key needed)
        # Cache the embedder to avoid reloading the model on every call (which causes hangs/slowness)
        if _CACHED_EMBEDDER is None:
            logger.info("Loading LocalEmbedder model (this happens once)...")
            _CACHED_EMBEDDER = LocalEmbedder(
                model_name="all-MiniLM-L6-v2"  # Fast, lightweight, runs locally
            )
        
        embedder = _CACHED_EMBEDDER

        # Initialize Graphiti without cross_encoder (optional component)
        graphiti = Graphiti(
            neo4j_uri,
            neo4j_user,
            neo4j_password,
            llm_client=llm_client,
            embedder=embedder
        )
        
        return graphiti

    except Exception as e:
        logger.error(f"Error setting up Graphiti: {e}")
        raise
