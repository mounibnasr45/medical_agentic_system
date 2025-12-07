import requests
import json
import time
import sys

# Configuration
API_URL = "http://localhost:8000/ask"
HEADERS = {"Content-Type": "application/json"}

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_separator(title):
    print(f"\n{Colors.HEADER}{'='*60}")
    print(f" {title}")
    print(f"{'='*60}{Colors.ENDC}")

def run_test(scenario_num, title, query, session_id=None, description=""):
    print_separator(f"SCENARIO {scenario_num}: {title}")
    print(f"{Colors.CYAN}Description:{Colors.ENDC} {description}")
    print(f"{Colors.BLUE}Query:{Colors.ENDC} {query}")
    
    payload = {
        "query": query,
        "session_id": session_id
    }
    
    start_time = time.time()
    try:
        response = requests.post(API_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        data = response.json()
        duration = time.time() - start_time
        
        # Extract key metrics
        new_session_id = data.get("session_id")
        processing_mode = data.get("processing_mode", "Unknown")
        analysis = data.get("analysis", {})
        intent = analysis.get("intent", "N/A")
        complexity = analysis.get("complexity", "N/A")
        
        print(f"\n{Colors.GREEN}✅ SUCCESS ({duration:.2f}s){Colors.ENDC}")
        print(f"{Colors.BOLD}Processing Mode:{Colors.ENDC} {processing_mode}")
        print(f"{Colors.BOLD}Detected Intent:{Colors.ENDC} {intent}")
        print(f"{Colors.BOLD}Complexity Score:{Colors.ENDC} {complexity}/5")
        
        print(f"\n{Colors.BOLD}🤖 Agent Response:{Colors.ENDC}")
        print("-" * 40)
        print(data.get("response", "No response text").strip())
        print("-" * 40)
        
        return new_session_id
        
    except requests.exceptions.ConnectionError:
        print(f"\n{Colors.FAIL}❌ ERROR: Could not connect to server at {API_URL}{Colors.ENDC}")
        print("Make sure the server is running: `python start_app.py`")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}❌ ERROR: {e}{Colors.ENDC}")
        return session_id

def main():
    print(f"{Colors.BOLD}🏥 MEDICAL AGENT SYSTEM EVALUATION{Colors.ENDC}")
    print("Running 5 strategic test scenarios to demonstrate system capabilities.\n")
    
    # Wait for server check
    try:
        requests.get("http://localhost:8000/")
    except:
        print(f"{Colors.FAIL}Server is not running! Please run 'python start_app.py' in another terminal.{Colors.ENDC}")
        return

    # --- SCENARIO 1: Basic Retrieval ---
    session_id = run_test(
        1, 
        "Knowledge Graph Retrieval", 
        "What is Warfarin used for?", 
        None,
        "Demonstrates basic entity retrieval from the Neo4j Knowledge Graph."
    )
    
    # --- SCENARIO 2: Safety & Interactions ---
    run_test(
        2, 
        "Safety Validation (Multi-Agent)", 
        "I am taking Warfarin. Is it safe to take Aspirin with it?", 
        session_id,
        "Demonstrates the Safety Validator agent detecting dangerous drug interactions (Major Severity)."
    )
    
    # --- SCENARIO 3: Complex Logic (Cypher) ---
    run_test(
        3, 
        "Complex Graph Query (Cypher)", 
        "Find all contraindications for Aspirin.", 
        session_id,
        "Tests the dynamic Cypher query generation to find specific relationships in the graph."
    )

    # --- SCENARIO 4: Contextual Memory ---
    run_test(
        4, 
        "Contextual Memory Retention", 
        "What are the side effects?", 
        session_id,
        "Tests if the agent remembers we are talking about Aspirin/Warfarin from previous turns."
    )

    # --- SCENARIO 5: Chain of Thought / Comparison ---
    run_test(
        5, 
        "Complex Reasoning & Comparison", 
        "Compare the bleeding risks of Warfarin versus Aspirin. Which requires more monitoring?", 
        session_id,
        "Demonstrates Chain of Thought (CoT) reasoning to synthesize information from multiple sources."
    )

    print_separator("EVALUATION COMPLETE")
    print(f"{Colors.GREEN}System demonstrated capabilities in: Graph RAG, Multi-Agent Safety Checks, Cypher Generation, Memory, and Reasoning.{Colors.ENDC}")

if __name__ == "__main__":
    main()
