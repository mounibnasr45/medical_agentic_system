import os
from crewai import Agent, Task, Crew, Process, LLM
from medical_agent.config import Config
from medical_agent.tools.medical_tools import web_search_tool, graph_db_tool

# Use local Ollama model (no API key, no rate limits)
# Note: llama3:8b has better reasoning than 3.2:3b, reducing redundant tool calls
local_llm = LLM(
    model="ollama/llama3:8b",  # MUST include "ollama/" prefix for LiteLLM routing
    base_url="http://localhost:11434"
)

# --- Agents ---

def get_clinical_agent():
    """Single agent that does research AND synthesis to reduce redundant tool calls."""
    return Agent(
        role='Medical Pharmacist',
        goal='Answer medical questions accurately using the knowledge graph and web search.',
        backstory="""You are an experienced clinical pharmacist. You search the internal 
        medical knowledge graph FIRST. If graph has no data, then you search the web. 
        Once you have the information, you provide a complete answer immediately. 
        Do NOT call the same tool multiple times with the same query.""",
        verbose=True,
        allow_delegation=False,
        tools=[graph_db_tool, web_search_tool],
        llm=local_llm,
        max_iter=5  # Limit to 5 iterations to prevent infinite loops
    )

# --- Crews ---

def create_medical_crew(query: str):
    """Optimized single-agent crew to reduce redundant tool calls."""
    agent = get_clinical_agent()

    task = Task(
        description=f"""Answer the question: '{query}'
        
        Instructions:
        1. Search Graph Database ONCE for relevant information
        2. If graph returns results, use them to answer
        3. If graph is empty, search Web ONCE
        4. Provide final answer immediately - do NOT repeat searches""",
        agent=agent,
        expected_output="Complete answer to the medical question with citations."
    )

    return Crew(
        agents=[agent],
        tasks=[task],
        verbose=True,
        process=Process.sequential
    )

# Removed redundant crews - use create_medical_crew() for all queries


