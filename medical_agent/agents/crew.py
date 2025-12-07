import os
from crewai import Agent, Task, Crew, Process, LLM
from medical_agent.config import Config
from medical_agent.tools.medical_tools import web_search_tool, graph_db_tool, cypher_query_tool
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from medical_agent.utils.intelligent_router import QueryAnalysis

# Choose LLM: Groq (cloud, powerful, rate-limited) or Ollama (local, unlimited)
USE_GROQ = True  # Set to False to use local Ollama instead

if USE_GROQ:
    # Groq Cloud API - Powerful but rate-limited (100k tokens/day)
    llm = LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=Config.GROQ_API_KEY,
        temperature=0.1
    )
    print("🌩️  Using Groq Cloud LLM (llama-3.3-70b)")
else:
    # Local Ollama - Unlimited but needs local installation
    # Note: llama3:8b has better reasoning than 3.2:3b
    llm = LLM(
        model="ollama/llama3:8b",  # MUST include "ollama/" prefix for LiteLLM routing
        base_url="http://localhost:11434",
        temperature=0.1
    )
    print("🖥️  Using Local Ollama LLM (llama3:8b)")

# --- Agents ---

def get_clinical_researcher():
    """Research agent - gathers information from graph and web."""
    return Agent(
        role='Clinical Researcher',
        goal='Research medical questions by querying the knowledge graph and web sources.',
        backstory="""You are a medical researcher specializing in drug information.
        
        TOOL SELECTION STRATEGY:
        1. Graph Database Search: Use FIRST for known entities (drugs, conditions, interactions)
        2. Cypher Query Executor: Use for complex multi-hop queries (drug A->B->C interactions, 
           finding all contraindications for a condition)
        3. Web Search: Use ONLY if graph has no data, for latest research or rare drugs
        
        IMPORTANT: Call each tool ONCE per query. Do NOT repeat searches.""",
        verbose=True,
        allow_delegation=True,  # Can delegate to safety validator
        tools=[graph_db_tool, cypher_query_tool, web_search_tool],
        llm=llm,
        max_iter=3  
    )

def get_safety_validator():
    """Safety agent - validates drug safety and interactions."""
    return Agent(
        role='Safety Validator',
        goal='Validate drug safety, check interactions, and identify contraindications.',
        backstory="""You are a clinical pharmacist focused on patient safety.
        
        RESPONSIBILITIES:
        - Validate drug interaction severity (Major, Moderate, Minor)
        - Check contraindications against patient conditions
        - Flag dangerous combinations
        
        TOOL USAGE:
        - Use Cypher Query tool to find all interactions for a drug
        - Cross-reference with conditions to find contraindications""",
        verbose=True,
        allow_delegation=False,
        tools=[cypher_query_tool, graph_db_tool],
        llm=llm,
        max_iter=2  # Reduced from 3 - safety checks should be quick
    )

def get_medical_analyst():
    """Synthesis agent - creates final medical recommendations."""
    return Agent(
        role='Medical Analyst',
        goal='Synthesize research findings into clear, actionable medical guidance.',
        backstory="""You are a medical analyst who creates comprehensive reports.
        
        PROCESS:
        1. Receive findings from Clinical Researcher
        2. Get safety validation from Safety Validator
        3. Synthesize into patient-friendly recommendations with citations
        
        NO TOOLS NEEDED - you work with delegated information only.""",
        verbose=True,
        allow_delegation=False,
        tools=[],  # Synthesis agent doesn't need tools
        llm=llm,
        max_iter=2
    )

# --- Crews ---

def create_medical_crew(query: str, analysis: 'QueryAnalysis' = None, apply_cot: bool = True):
    """
    Intelligent multi-agent crew with LLM-powered dynamic configuration.
    
    Uses QueryAnalysis from intelligent router to:
    - Select only required agents (not always all 3)
    - Set adaptive iteration limits based on complexity
    - Optimize tool usage based on query intent
    - Apply Chain of Thought reasoning for complex queries
    
    Args:
        query: User's medical query
        analysis: QueryAnalysis from router (auto-generated if None)
        apply_cot: Whether to apply CoT reasoning (default: True)
    
    Returns:
        Crew instance configured for the query
    """
    
    # Fallback if no analysis provided (backward compatibility)
    if analysis is None:
        from medical_agent.utils.intelligent_router import get_router
        router = get_router()
        analysis = router.analyze_query(query)
    
    # Get agents based on analysis
    researcher = get_clinical_researcher()
    
    # Override max_iter based on intelligent analysis
    researcher.max_iter = analysis.max_iterations.get('researcher', 3)
    
    # Build tool priority list from analysis
    tool_priority = ', '.join([
        'Graph Database Search' if t == 'graph_db' else
        'Cypher Query Executor' if t == 'cypher' else
        'Web Search' for t in analysis.suggested_tools
    ])
    
    # Prepare Chain of Thought instructions if applicable
    cot_instructions = ""
    if apply_cot and analysis.use_chain_of_thought and analysis.cot_reasoning_steps:
        steps_formatted = "\n".join([f"   {i+1}. {step}" for i, step in enumerate(analysis.cot_reasoning_steps)])
        cot_instructions = f"""
        
**🧠 CHAIN OF THOUGHT REASONING REQUIRED:**
This query requires step-by-step logical reasoning. Follow these steps:
{steps_formatted}

For each step, explicitly state:
- What you're analyzing
- Your reasoning process
- Your conclusion for that step

Then synthesize all steps into a final answer.
"""
    
    # Task 1: Research (always executed, but optimized)
    research_task = Task(
        description=f"""Research the question: '{query}'
        
        QUERY INTENT: {analysis.intent}
        COMPLEXITY: {analysis.complexity}/5
        RECOMMENDED TOOL PRIORITY: {tool_priority}{cot_instructions}
        
        **CRITICAL TOOL USAGE RULES:**
        1. Try DIFFERENT tools in each iteration (don't repeat the same tool)
        2. If Graph Database returns incomplete/partial info, immediately switch to Web Search
        3. If Graph Database returns "No info", skip to Web Search in next iteration
        4. Only repeat a tool if it gave useful info and you need MORE from that same source
        5. Maximum {analysis.max_iterations['researcher']} iterations total
        
        EXECUTION STRATEGY:
        - Iteration 1: Try {tool_priority.split(', ')[0]}
        - If incomplete: Iteration 2: Try {tool_priority.split(', ')[1] if len(tool_priority.split(', ')) > 1 else 'Web Search'}
        - If still incomplete: Iteration 3: Try remaining tools or refine query
        
        OPTIMIZATION: This query has complexity {analysis.complexity}/5. 
        {'Focus on precise answers but try 2 different sources if first is incomplete.' if analysis.complexity <= 2 else 'Use multiple sources for comprehensive answer.'}
        
        Return findings with sources cited.
        """,
        agent=researcher,
        expected_output="Research findings with data sources."
    )
    
    tasks = [research_task]
    agents = [researcher]
    
    # Conditionally add agents based on LLM analysis (not hardcoded keywords)
    if 'validator' in analysis.required_agents:
        validator = get_safety_validator()
        validator.max_iter = analysis.max_iterations.get('validator', 2)
        agents.append(validator)
        
        safety_task = Task(
            description=f"""Validate safety for: '{query}'
            
            QUERY INTENT: {analysis.intent}
            COMPLEXITY: {analysis.complexity}/5
            
            1. Use Cypher Query tool for drug interactions
            2. Check contraindication severity levels
            3. Flag any Major or Moderate risks
            4. Maximum {analysis.max_iterations['validator']} iterations
            
            OPTIMIZATION: {'Quick binary safety check.' if analysis.complexity <= 2 else 'Thorough safety analysis required.'}
            """,
            agent=validator,
            expected_output="Safety validation report with risk levels.",
            context=[research_task]
        )
        tasks.append(safety_task)
    
    # Add analyst for complex queries (LLM decides, not keywords)
    if 'analyst' in analysis.required_agents:
        analyst = get_medical_analyst()
        analyst.max_iter = analysis.max_iterations.get('analyst', 1)
        agents.append(analyst)
        
        synthesis_task = Task(
            description=f"""Create final answer for: '{query}'
            
            QUERY COMPLEXITY: {analysis.complexity}/5
            
            1. Review research findings
            {'2. Incorporate safety validation' if 'validator' in analysis.required_agents else '2. Skip safety (not applicable)'}
            3. Write patient-friendly response with citations
            4. Include warnings if applicable
            
            OPTIMIZATION: {'Concise summary sufficient.' if analysis.complexity <= 3 else 'Comprehensive synthesis required.'}
            """,
            agent=analyst,
            expected_output="Complete medical guidance with citations and warnings.",
            context=tasks
        )
        tasks.append(synthesis_task)
    
    print(f"\n🎯 Crew Configuration (AI-optimized):")
    print(f"   Agents: {len(agents)} ({', '.join([a.role for a in agents])})")
    print(f"   Tasks: {len(tasks)}")
    print(f"   Max iterations: {analysis.max_iterations}")
    if apply_cot and analysis.use_chain_of_thought:
        print(f"   🧠 Chain of Thought: ENABLED ({len(analysis.cot_reasoning_steps)} steps)")
    print()
    
    return Crew(
        agents=agents,
        tasks=tasks,
        verbose=True,
        process=Process.sequential
    )

# Removed redundant crews - use create_medical_crew() for all queries


