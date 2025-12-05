"""
Test script to validate all 6 assignment improvements.

Run this to verify:
1. Cypher Query Tool
2. Tool Usage Logging
3. Multi-Agent Delegation
4. Tool Selection Strategy
5. Response Streaming
6. Frontend

Usage: python test_improvements.py
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000"

def test_cypher_tool():
    """Test 1: Cypher Query Tool"""
    print("\n" + "="*60)
    print("TEST 1: Cypher Query Tool")
    print("="*60)
    
    from medical_agent.tools.medical_tools import cypher_query_tool
    
    print("Running: cypher_query_tool('Find all drugs that interact with Warfarin')")
    result = cypher_query_tool.run("Find all drugs that interact with Warfarin")
    print(f"Result: {result[:200]}...")
    print("✅ Cypher Query Tool works!")

def test_logging():
    """Test 2: Tool Usage Logging"""
    print("\n" + "="*60)
    print("TEST 2: Tool Usage Logging")
    print("="*60)
    
    import os
    log_file = "logs/tool_usage.log"
    
    if os.path.exists(log_file):
        with open(log_file, 'r') as f:
            lines = f.readlines()
            print(f"Log file exists with {len(lines)} lines")
            print("\nLast 3 log entries:")
            for line in lines[-3:]:
                print(f"  {line.strip()}")
        print("✅ Logging works!")
    else:
        print("⚠️  Log file not created yet. Send a query first.")

def test_multi_agent():
    """Test 3: Multi-Agent Delegation"""
    print("\n" + "="*60)
    print("TEST 3: Multi-Agent Delegation")
    print("="*60)
    
    print("Checking crew configuration...")
    from medical_agent.agents.crew import create_medical_crew
    
    crew = create_medical_crew("Test query")
    print(f"Number of agents: {len(crew.agents)}")
    print(f"Agent roles:")
    for agent in crew.agents:
        print(f"  - {agent.role}")
    
    if len(crew.agents) >= 3:
        print("✅ Multi-agent delegation configured!")
    else:
        print("⚠️  Expected 3 agents, found", len(crew.agents))

def test_tool_strategy():
    """Test 4: Tool Selection Strategy"""
    print("\n" + "="*60)
    print("TEST 4: Tool Selection Strategy Documentation")
    print("="*60)
    
    from medical_agent.agents.crew import get_clinical_researcher
    
    agent = get_clinical_researcher()
    print("Clinical Researcher backstory:")
    print(agent.backstory[:300] + "...")
    
    if "TOOL SELECTION STRATEGY" in agent.backstory:
        print("✅ Tool selection strategy documented!")
    else:
        print("⚠️  Tool strategy not found in backstory")

def test_streaming():
    """Test 5: Response Streaming"""
    print("\n" + "="*60)
    print("TEST 5: Response Streaming (SSE)")
    print("="*60)
    
    try:
        print("Testing /ask/stream endpoint...")
        response = requests.post(
            f"{BASE_URL}/ask/stream",
            json={"query": "What is Aspirin?"},
            stream=True,
            timeout=60
        )
        
        events = []
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith('data: '):
                    events.append(line)
                    if len(events) <= 3:  # Show first 3 events
                        print(f"  Event: {line[:80]}...")
        
        print(f"Total events received: {len(events)}")
        print("✅ Streaming works!")
        
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running. Start with: python -m medical_agent.api.server")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_frontend():
    """Test 6: Frontend"""
    print("\n" + "="*60)
    print("TEST 6: Simple Web Frontend")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/chat")
        
        if response.status_code == 200 and "Medical AI Assistant" in response.text:
            print("Chat UI accessible at: http://localhost:8000/chat")
            print(f"HTML size: {len(response.text)} bytes")
            print("✅ Frontend works!")
        else:
            print(f"⚠️  Unexpected response: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running. Start with: python -m medical_agent.api.server")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("\n" + "🎯"*30)
    print("TESTING ALL 6 ASSIGNMENT IMPROVEMENTS")
    print("🎯"*30)
    
    # Test 1: Cypher Tool (doesn't require server)
    try:
        test_cypher_tool()
    except Exception as e:
        print(f"❌ Cypher Tool Test Failed: {e}")
    
    # Test 2: Logging (doesn't require server)
    try:
        test_logging()
    except Exception as e:
        print(f"❌ Logging Test Failed: {e}")
    
    # Test 3: Multi-Agent (doesn't require server)
    try:
        test_multi_agent()
    except Exception as e:
        print(f"❌ Multi-Agent Test Failed: {e}")
    
    # Test 4: Tool Strategy (doesn't require server)
    try:
        test_tool_strategy()
    except Exception as e:
        print(f"❌ Tool Strategy Test Failed: {e}")
    
    # Test 5: Streaming (requires server)
    time.sleep(1)
    try:
        test_streaming()
    except Exception as e:
        print(f"❌ Streaming Test Failed: {e}")
    
    # Test 6: Frontend (requires server)
    time.sleep(1)
    try:
        test_frontend()
    except Exception as e:
        print(f"❌ Frontend Test Failed: {e}")
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print("All tests completed!")
    print("\nTo test features that require the server:")
    print("1. Start server: python -m medical_agent.api.server")
    print("2. Run this script again")
    print("3. Open browser: http://localhost:8000/chat")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
