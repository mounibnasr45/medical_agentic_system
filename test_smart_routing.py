"""
Test script for intelligent routing and tool diversity.
"""

from medical_agent.utils.intelligent_router import get_router
from medical_agent.agents.crew import create_medical_crew

def test_query(query: str):
    """Test a query with intelligent routing."""
    print(f"\n{'='*80}")
    print(f"TESTING QUERY: '{query}'")
    print(f"{'='*80}\n")
    
    # Step 1: Analyze with LLM router
    router = get_router()
    analysis = router.analyze_query(query)
    
    print(f"📊 ANALYSIS RESULTS:")
    print(f"   Medical: {analysis.is_medical} (confidence: {analysis.confidence:.2f})")
    print(f"   Intent: {analysis.intent}")
    print(f"   Complexity: {analysis.complexity}/5")
    print(f"   Required Agents: {', '.join(analysis.required_agents)}")
    print(f"   Max Iterations: {analysis.max_iterations}")
    print(f"   Suggested Tools: {', '.join(analysis.suggested_tools)}")
    print(f"   Reasoning: {analysis.reasoning}")
    
    if not analysis.is_medical:
        print(f"\n❌ REJECTED: {analysis.rejection_message}")
        return
    
    # Step 2: Create optimized crew
    print(f"\n🚀 CREATING CREW...")
    crew = create_medical_crew(query, analysis)
    
    # Step 3: Execute
    print(f"\n⚡ EXECUTING...")
    result = crew.kickoff()
    
    print(f"\n✅ RESULT:")
    print(f"{result.raw if hasattr(result, 'raw') else result}")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    # Test cases
    test_cases = [
        "hey",  # Should reject
        "what is gripex",  # Simple query - 1 agent, should try web if graph fails
        "aspirin contraindications",  # Medium query - 2 agents
        "can I take aspirin with warfarin",  # Complex query - 3 agents
    ]
    
    for query in test_cases:
        test_query(query)
        print("\n" + "="*80)
        print("Press Enter to continue to next test...")
        input()
