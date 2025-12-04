import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000"

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def wait_for_rate_limit(seconds=60):
    print(f"\n⏳ Waiting {seconds} seconds to respect Rate Limits...")
    for i in range(seconds, 0, -1):
        print(f"{i}...", end="\r")
        time.sleep(1)
    print("Go! 🚀")

def test_graph_info():
    print_header("Checking Graph Status")
    try:
        response = requests.get(f"{BASE_URL}/graph-info")
        if response.status_code == 200:
            print("✅ Graph Connection: OK")
            print(f"📊 Stats: {json.dumps(response.json(), indent=2)}")
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error connecting to API: {e}")
        sys.exit(1)

def test_clinical_query():
    print_header("Step 1: Testing Clinical Query Agent (/ask)")
    query = "What are the contraindications for Aspirin?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

def test_formulation_validation():
    print_header("Step 2: Testing Drug Interaction Query (/ask)")
    query = "What are the interactions between Aspirin and Warfarin?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

def test_alternatives():
    print_header("Step 3: Testing Alternative Finder (/ask)")
    query = "What are alternatives to Aspirin for pain relief?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        response = requests.post(f"{BASE_URL}/ask", json=payload)
        if response.status_code == 200:
            result = response.json()
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("🚀 Starting Agent Test Suite (With Rate Limit Delays)...")
    
    # 1. Check if server is up and graph status
    # test_graph_info()
    
    # 2. Run the agent use cases with delays
    test_clinical_query()
    
    test_formulation_validation()
    
    test_alternatives()
    
    print("\n✅ Test Suite Completed.")
