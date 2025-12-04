import os
import re
import asyncio
import logging
from pathlib import Path
from chonkie import RecursiveChunker
from medical_agent.graph.client import get_graphiti_client
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def ingest_text(text: str, source_name: str = "uploaded_doc"):
    logger.info(f"Ingesting text from {source_name}...")
    
    # Chunk Data
    chunker = RecursiveChunker(chunk_size=300)
    chunks = chunker.chunk(text)
    logger.info(f"Generated {len(chunks)} chunks")

    # Initialize Graphiti
    try:
        graphiti = await get_graphiti_client()
        await graphiti.build_indices_and_constraints()
    except Exception as e:
        logger.error(f"Failed to initialize Graphiti: {e}")
        raise

    group_id = "medical_docs"
    
    for i, chunk in enumerate(chunks):
        content = chunk.text
        max_retries = 10
        for attempt in range(max_retries):
            try:
                await graphiti.add_episode(
                    name=f"{source_name} Chunk {i+1}",
                    episode_body=content,
                    source_description=f"{source_name} chunk {i+1}",
                    group_id=group_id,
                    reference_time=datetime.now(timezone.utc)
                )
                await asyncio.sleep(2) # Politeness delay
                break 
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Rate limit" in error_str:
                    wait_time = 60
                    match_m = re.search(r"try again in (\d+)m(\d+(\.\d+)?)s", error_str)
                    if match_m:
                        wait_time = int(match_m.group(1)) * 60 + float(match_m.group(2)) + 5
                    else:
                        match_s = re.search(r"try again in (\d+(\.\d+)?)s", error_str)
                        if match_s:
                            wait_time = float(match_s.group(1)) + 5
                    
                    logger.warning(f"Rate limit hit. Waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Error adding chunk {i+1}: {e}")
                    break

    await graphiti.close()
    return {"status": "success", "chunks_ingested": len(chunks)}
