import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver(uri, auth=(user, password))

def check_state():
    with driver.session() as session:
        print("--- Indexes ---")
        indexes = session.run("SHOW INDEXES").data()
        for idx in indexes:
            print(f"Name: {idx['name']}, Type: {idx['type']}, Entity: {idx['entityType']}, Properties: {idx['properties']}")
            # Check for vector options if available (provider specific)
            if idx['type'] == 'VECTOR':
                 # Try to get more details if possible, though SHOW INDEXES output varies by version
                 print(f"   -> Vector Index Details: {idx}")

        print("\n--- Node Sample ---")
        # Check one Entity node to see the embedding property length
        result = session.run("MATCH (n:Entity) RETURN n.name, size(n.name_embedding) as emb_size LIMIT 1").single()
        if result:
            print(f"Node: {result['n.name']}, Embedding Size: {result['emb_size']}")
        else:
            print("No Entity nodes found.")

if __name__ == "__main__":
    check_state()
    driver.close()
