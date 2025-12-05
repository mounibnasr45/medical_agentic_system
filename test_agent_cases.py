import requests
import time
import json
import sys

BASE_URL = "http://localhost:8000"

def print_header(title):
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")

def test_clinical_query():
    print_header("Test 1: Contraindications Query")
    query = "What is Aspirin and what is gripex if you don't have information in databse then search in web?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload, timeout=120)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success (took {elapsed:.1f}s)")
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except requests.exceptions.Timeout:
        print("❌ Request timeout (>120s)")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_drug_interaction():
    print_header("Test 2: Drug Interaction Query")
    query = "What are the interactions between Aspirin and Warfarin?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload, timeout=120)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success (took {elapsed:.1f}s)")
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except requests.exceptions.Timeout:
        print("❌ Request timeout (>120s)")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_alternatives():
    print_header("Test 3: Drug Alternatives Query")
    query = "What are alternatives to Aspirin for pain relief?"
    print(f"❓ Query: {query}")
    
    payload = {"query": query}
    try:
        start_time = time.time()
        response = requests.post(f"{BASE_URL}/ask", json=payload, timeout=120)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Success (took {elapsed:.1f}s)")
            print("\n🤖 Agent Response:")
            print(result.get("response", "No response field"))
        else:
            print(f"❌ Failed: {response.status_code}")
            print(response.text)
    except requests.exceptions.Timeout:
        print("❌ Request timeout (>120s)")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_server_health():
    print_header("Server Health Check")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            print(f"📊 Response: {json.dumps(response.json(), indent=2)}")
            return True
        else:
            print(f"❌ Server returned: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print(f"💡 Make sure server is running: python -m medical_agent.api.server")
        return False

if __name__ == "__main__":
    print("🚀 Medical Agent Test Suite")
    print("=" * 60)
    print("📋 Testing simplified single-agent architecture")
    print("🔧 All queries use /ask endpoint")
    print("=" * 60)
    
    # Check if server is accessible
    if not test_server_health():
        sys.exit(1)
    
    # Run all test cases
    test_clinical_query()
    # test_drug_interaction()
    # test_alternatives()
    
    print("\n" + "=" * 60)
    print("✅ Test Suite Completed")
    print("=" * 60)
