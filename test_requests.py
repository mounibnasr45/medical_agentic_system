import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_seed():
    print("🌱 Triggering Graph Seeding...")
    try:
        response = requests.post(f"{BASE_URL}/seed")
        if response.status_code == 200:
            print("✅ Seeding Successful:", response.json())
        else:
            print(f"❌ Seeding Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")

def test_ask(query):
    print(f"\n❓ Asking Agent: '{query}'")
    try:
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/ask",
            json={"query": query}
        )
        duration = time.time() - start_time
        
        if response.status_code == 200:
            print(f"✅ Response received in {duration:.2f}s:")
            result = response.json().get("response", {})
            print(result)
        else:
            print(f"❌ Request Failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error connecting to server: {e}")

if __name__ == "__main__":
    # 1. Seed the DB first
    test_seed()
    
    # 2. Test a simple query
    # test_ask("What are the interactions for Warfarin?")
    
    # 3. Test a complex query
    # test_ask("Can I prescribe Warfarin and Aspirin together for a patient with heart disease?")
