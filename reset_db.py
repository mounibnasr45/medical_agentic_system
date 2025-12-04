import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
user = os.getenv("NEO4J_USER", "neo4j")
password = os.getenv("NEO4J_PASSWORD")

if not password:
    print("❌ Error: NEO4J_PASSWORD not found in .env file")
    exit(1)

driver = GraphDatabase.driver(uri, auth=(user, password))

def reset_database():
    print("🗑️  Clearing Neo4j database...")
    try:
        with driver.session() as session:
            # 1. Delete all nodes and relationships
            session.run("MATCH (n) DETACH DELETE n")
            print("   ✅ Deleted all nodes and relationships")

            # 2. Drop all indexes (crucial for vector dimension reset)
            indexes = session.run("SHOW INDEXES").data()
            for index in indexes:
                # Skip internal/lookup indexes if necessary, but dropping all user indexes is safer
                if index['type'] != 'LOOKUP': 
                    try:
                        session.run(f"DROP INDEX {index['name']}")
                        print(f"   ✅ Dropped index: {index['name']}")
                    except Exception as e:
                        print(f"   ⚠️  Could not drop index {index['name']}: {e}")

            # 3. Drop all constraints
            constraints = session.run("SHOW CONSTRAINTS").data()
            for constraint in constraints:
                try:
                    session.run(f"DROP CONSTRAINT {constraint['name']}")
                    print(f"   ✅ Dropped constraint: {constraint['name']}")
                except Exception as e:
                    print(f"   ⚠️  Could not drop constraint {constraint['name']}: {e}")

        print("✨ Database reset complete!")
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    reset_database()