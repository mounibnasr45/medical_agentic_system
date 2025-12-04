import asyncio
import json
import os
from datetime import datetime
from medical_agent.graph.client import get_graphiti_client
from graphiti_core.nodes import EpisodeType

async def seed_graph():
    graphiti = await get_graphiti_client()
    
    # Ensure indices are built
    await graphiti.build_indices_and_constraints()

    data_path = os.path.join(os.path.dirname(__file__), '../../data/drugs.json')
    
    with open(data_path, 'r') as f:
        drugs = json.load(f)

    print(f"Seeding {len(drugs)} drugs...")

    for drug in drugs:
        # Construct a narrative text for the drug to be ingested as an episode
        text = f"Drug Name: {drug['name']}.\n"
        text += f"Description: {drug['description']}\n"
        
        if drug['interactions']:
            text += "Interactions:\n"
            for interaction in drug['interactions']:
                text += f"- {drug['name']} interacts with {interaction['drug']}. Severity: {interaction['severity']}. Effect: {interaction['effect']}.\n"
        
        if drug['contraindications']:
            text += "Contraindications:\n"
            for contra in drug['contraindications']:
                text += f"- {drug['name']} is contraindicated in {contra}.\n"

        print(f"Ingesting {drug['name']}...")
        await graphiti.add_episode(
            name=f"Drug Info: {drug['name']}",
            episode_body=text,
            source=EpisodeType.text,
            source_description=f"Seed data for {drug['name']}",
            reference_time=datetime.now()
        )

    print("Seeding complete.")
    await graphiti.close()

if __name__ == "__main__":
    asyncio.run(seed_graph())
