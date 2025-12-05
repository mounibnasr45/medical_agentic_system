"""
Quick start script for Medical AI Assistant

This script:
1. Checks if Neo4j is running
2. Starts the FastAPI server
3. Opens the chat UI in browser

Usage: python start_app.py
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

def check_neo4j():
    """Check if Neo4j is accessible."""
    try:
        from neo4j import GraphDatabase
        from medical_agent.config import Config
        
        driver = GraphDatabase.driver(
            Config.NEO4J_URI,
            auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
        )
        driver.verify_connectivity()
        driver.close()
        print("✅ Neo4j is running")
        return True
    except Exception as e:
        print(f"❌ Neo4j not accessible: {e}")
        print("\n🔧 To start Neo4j:")
        print("   1. Open Neo4j Desktop")
        print("   2. Start your database")
        print("   3. Run this script again\n")
        return False

def start_server():
    """Start the FastAPI server."""
    print("🚀 Starting Medical AI Assistant...")
    print("📡 Server will run on: http://localhost:8000")
    print("💬 Chat UI will open at: http://localhost:8000/chat")
    print("\nPress CTRL+C to stop the server\n")
    
    # Wait a bit before opening browser
    time.sleep(2)
    webbrowser.open("http://localhost:8000/chat")
    
    # Start server
    import uvicorn
    from medical_agent.api.server import app
    
    uvicorn.run(app, host="0.0.0.0", port=8000)

def main():
    print("="*60)
    print("🏥 Medical AI Assistant - Quick Start")
    print("="*60)
    
    # Check Neo4j
    if not check_neo4j():
        sys.exit(1)
    
    # Start server
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
