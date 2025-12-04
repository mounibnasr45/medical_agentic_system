import os
import re
# Force Transformers to use PyTorch and ignore TensorFlow to avoid conflicts/hangs
os.environ["USE_TORCH"] = "1"
os.environ["USE_TF"] = "0"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"

import asyncio
import logging
from pathlib import Path
from chonkie import RecursiveChunker
from medical_agent.graph.client import get_graphiti_client
from medical_agent.config import Config
from datetime import datetime, timezone

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ingest():
    # 1. Read Data
    file_path = Path("data/drugs.txt")
    if not file_path.exists():
        # Try absolute path if relative fails
        file_path = Path(__file__).parent / "data" / "drugs.txt"
        if not file_path.exists():
             logger.error(f"File not found: {file_path}")
             return

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    logger.info(f"Read {len(text)} characters from {file_path}")

    # 2. Chunk Data using Chonkie
    logger.info("Chunking text with Chonkie...")
    # RecursiveChunker in this version does not support chunk_overlap
    # Reducing chunk_size to 300 to avoid hitting TPM limits
    chunker = RecursiveChunker(
        chunk_size=300
    )
    chunks = chunker.chunk(text)
    
    logger.info(f"Generated {len(chunks)} chunks")

    # 3. Initialize Graphiti
    try:
        logger.info("Initializing Graphiti client...")
        graphiti = await get_graphiti_client()
        # Ensure indices are built
        await graphiti.build_indices_and_constraints()
    except Exception as e:
        logger.error(f"Failed to initialize Graphiti: {e}")
        return

    # 4. Ingest Chunks
    group_id = "medical_docs"
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Ingesting chunk {i+1}/{len(chunks)}...")
        
        content = chunk.text
        
        max_retries = 10
        for attempt in range(max_retries):
            try:
                await graphiti.add_episode(
                    name=f"Drug Info Chunk {i+1}",
                    episode_body=content,
                    source_description=f"drugs.txt chunk {i+1}",
                    group_id=group_id,
                    reference_time=datetime.now(timezone.utc)
                )
                logger.info(f"Successfully added chunk {i+1}")
                
                # Standard delay between successful chunks to be nice to the API
                await asyncio.sleep(5)
                break # Success, exit retry loop
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Rate limit" in error_str:
                    # Try to extract wait time
                    wait_time = 60 # Default wait
                    
                    # Regex for "try again in 3m42.04s"
                    match_m = re.search(r"try again in (\d+)m(\d+(\.\d+)?)s", error_str)
                    if match_m:
                        wait_time = int(match_m.group(1)) * 60 + float(match_m.group(2)) + 5
                    else:
                        # Regex for "try again in 2.5s"
                        match_s = re.search(r"try again in (\d+(\.\d+)?)s", error_str)
                        if match_s:
                            wait_time = float(match_s.group(1)) + 5
                    
                    logger.warning(f"Rate limit hit. Waiting {wait_time:.2f}s before retry {attempt+1}/{max_retries}...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Error adding chunk {i+1}: {e}")
                    break # Non-retryable error

    await graphiti.close()
    logger.info("Ingestion complete.")

if __name__ == "__main__":
    asyncio.run(ingest())
