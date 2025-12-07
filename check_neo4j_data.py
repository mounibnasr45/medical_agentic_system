"""
Quick script to check what data is actually in Neo4j database
"""

from neo4j import GraphDatabase
from medical_agent.config import Config

def check_database():
    driver = GraphDatabase.driver(
        Config.NEO4J_URI,
        auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    )
    
    with driver.session() as session:
        print("=" * 80)
        print("NEO4J DATABASE CONTENTS")
        print("=" * 80)
        
        # Check node labels
        result = session.run("CALL db.labels()")
        labels = [record["label"] for record in result]
        print(f"\n📊 Node Labels: {labels}")
        
        # Count nodes by label
        for label in labels:
            result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
            count = result.single()["count"]
            print(f"   - {label}: {count} nodes")
        
        # Check relationships
        result = session.run("CALL db.relationshipTypes()")
        rel_types = [record["relationshipType"] for record in result]
        print(f"\n🔗 Relationship Types: {rel_types}")
        
        # Count relationships
        for rel_type in rel_types:
            result = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count")
            count = result.single()["count"]
            print(f"   - {rel_type}: {count} relationships")
        
        # Sample Entity nodes
        print("\n" + "=" * 80)
        print("SAMPLE ENTITY NODES")
        print("=" * 80)
        result = session.run("""
            MATCH (e:Entity)
            RETURN e.name AS name, e.summary AS summary
            LIMIT 10
        """)
        
        for i, record in enumerate(result, 1):
            name = record.get("name", "N/A")
            summary = record.get("summary", "No summary")
            print(f"\n{i}. {name}")
            print(f"   Summary: {summary[:150]}...")
        
        # Check for pain-related drugs
        print("\n" + "=" * 80)
        print("DRUGS WITH PAIN/INFLAMMATION PROPERTIES")
        print("=" * 80)
        result = session.run("""
            MATCH (e:Entity)
            WHERE e.summary CONTAINS 'pain' OR e.summary CONTAINS 'inflammation'
               OR e.summary CONTAINS 'NSAID' OR e.summary CONTAINS 'analgesic'
            RETURN e.name AS name, e.summary AS summary
            LIMIT 20
        """)
        
        records = list(result)
        print(f"\nFound {len(records)} drugs with pain/inflammation properties:")
        for record in records:
            print(f"  - {record['name']}")
        
        # Sample relationships
        print("\n" + "=" * 80)
        print("SAMPLE RELATIONSHIPS")
        print("=" * 80)
        result = session.run("""
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            RETURN a.name AS from, b.name AS to, r.fact AS fact
            LIMIT 10
        """)
        
        for i, record in enumerate(result, 1):
            print(f"\n{i}. {record['from']} → {record['to']}")
            print(f"   Fact: {record.get('fact', 'No fact')[:200]}")
    
    driver.close()
    print("\n" + "=" * 80)
    print("✅ DATABASE CHECK COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    check_database()
