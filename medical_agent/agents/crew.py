"""Multi-agent crew, configured per query by the router.

Three roles, each added only when the routing decision calls for it:

  Clinical Researcher  gathers evidence from the graph, generated Cypher and the web
  Safety Validator     checks interactions and contraindications, grades severity
  Medical Analyst      synthesises the findings into an answer, uses no tools

A simple lookup runs one agent; a multi-drug safety question runs all three. The
alternative - always running all three - triples cost and latency for questions
that do not need it.

The LLM is built lazily. Constructing it at import time meant the module could not
be imported without a live API key, which broke tests and CI.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from crewai import LLM, Agent, Crew, Process, Task

from medical_agent.config import Config
from medical_agent.tools.medical_tools import (
    cypher_query_tool,
    graph_db_tool,
    web_search_tool,
)
from medical_agent.utils.events import EventType, emit

if TYPE_CHECKING:
    from medical_agent.utils.intelligent_router import QueryAnalysis

logger = logging.getLogger(__name__)

_llm: LLM | None = None

TOOL_LABELS = {
    "graph_db": "Graph Database Search",
    "cypher": "Cypher Query Executor",
    "web_search": "Web Search",
    "web": "Web Search",
}


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM(
            model=Config.agent_llm_model(),
            api_key=Config.agent_llm_api_key(),
            temperature=0.1,
        )
    return _llm


def get_clinical_researcher() -> Agent:
    return Agent(
        role="Clinical Researcher",
        goal="Research medical questions using the knowledge graph and web sources.",
        backstory="""You are a medical researcher specialising in drug information.

        Tool selection strategy:
        1. Graph Database Search first, for known drugs, conditions and interactions.
        2. Cypher Query Executor for multi-hop questions, such as every drug that
           interacts with a given drug, or all contraindications for a condition.
        3. Web Search when the graph has no data, or for recent or rare drugs.

        If a tool reports that the knowledge graph is unavailable, move straight to
        Web Search and say in your findings that graph verification was not possible.

        Call each tool once per query. Do not repeat identical searches.""",
        verbose=False,
        allow_delegation=True,
        tools=[graph_db_tool, cypher_query_tool, web_search_tool],
        llm=get_llm(),
        max_iter=3,
    )


def get_safety_validator() -> Agent:
    return Agent(
        role="Safety Validator",
        goal="Validate drug safety, check interactions and identify contraindications.",
        backstory="""You are a clinical pharmacist focused on patient safety.

        You grade interaction severity as Major, Moderate or Minor, check
        contraindications against stated patient conditions, and flag dangerous
        combinations explicitly. State clearly when evidence is insufficient rather
        than implying safety.""",
        verbose=False,
        allow_delegation=False,
        tools=[cypher_query_tool, graph_db_tool],
        llm=get_llm(),
        max_iter=2,
    )


def get_medical_analyst() -> Agent:
    return Agent(
        role="Medical Analyst",
        goal="Synthesise research findings into clear, actionable guidance.",
        backstory="""You turn research and safety findings into a clear answer.

        You cite which source supports each claim, keep warnings prominent, and
        write for a non-specialist without losing clinical accuracy. You use no
        tools; you work from what the other agents found.""",
        verbose=False,
        allow_delegation=False,
        tools=[],
        llm=get_llm(),
        max_iter=1,
    )


def _tool_priority(analysis: QueryAnalysis) -> str:
    return (
        ", ".join(TOOL_LABELS.get(t, t) for t in analysis.suggested_tools)
        or "Graph Database Search"
    )


def _cot_block(analysis: QueryAnalysis) -> str:
    if not (analysis.use_chain_of_thought and analysis.cot_reasoning_steps):
        return ""
    steps = "\n".join(f"   {i}. {s}" for i, s in enumerate(analysis.cot_reasoning_steps, 1))
    return f"""

This query requires explicit step-by-step reasoning. Work through these steps:
{steps}

For each step, state what you are analysing, your reasoning, and your conclusion.
"""


def _on_task_complete(output: Any) -> None:
    """Emit a trace event as each task finishes.

    Wrapped defensively: CrewAI's callback payload shape is not part of its stable
    API, and a trace failure must never fail the run it is describing.
    """
    try:
        agent = getattr(output, "agent", None) or "agent"
        description = str(getattr(output, "description", ""))[:120]
        emit(
            EventType.STAGE_COMPLETED,
            stage=str(agent),
            ok=True,
            summary=description,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Task callback trace failed: %s", exc)


def create_medical_crew(query: str, analysis: QueryAnalysis | None = None) -> Crew:
    """Build a crew sized to the routing decision."""
    if analysis is None:
        from medical_agent.utils.intelligent_router import get_router

        analysis = get_router().analyze_query(query)

    priority = _tool_priority(analysis)
    cot = _cot_block(analysis)

    researcher = get_clinical_researcher()
    researcher.max_iter = analysis.max_iterations.get("researcher", 3)

    research_task = Task(
        description=f"""Research this question: '{query}'

        Query intent: {analysis.intent}
        Complexity: {analysis.complexity}/5
        Recommended tool priority: {priority}{cot}

        Tool usage rules:
        1. Try a DIFFERENT tool on each iteration; do not repeat one that worked.
        2. If the graph returns partial information, switch to Web Search next.
        3. If the graph reports no data or is unavailable, go to Web Search.
        4. Use at most {analysis.max_iterations.get("researcher", 3)} iterations.

        Return your findings with each source cited.
        """,
        agent=researcher,
        expected_output="Research findings with the data source for each claim.",
    )

    agents, tasks = [researcher], [research_task]

    if "validator" in analysis.required_agents:
        validator = get_safety_validator()
        validator.max_iter = analysis.max_iterations.get("validator", 2)
        agents.append(validator)
        tasks.append(
            Task(
                description=f"""Validate safety for: '{query}'

                Intent: {analysis.intent}. Complexity: {analysis.complexity}/5.

                1. Check drug interactions, using Cypher for multi-hop relationships.
                2. Grade severity as Major, Moderate or Minor.
                3. Flag every Major or Moderate risk explicitly.
                4. Use at most {analysis.max_iterations.get("validator", 2)} iterations.
                """,
                agent=validator,
                expected_output="Safety validation report with graded risk levels.",
                context=[research_task],
            )
        )

    if "analyst" in analysis.required_agents:
        analyst = get_medical_analyst()
        analyst.max_iter = analysis.max_iterations.get("analyst", 1)
        agents.append(analyst)
        has_validator = "validator" in analysis.required_agents
        tasks.append(
            Task(
                description=f"""Write the final answer for: '{query}'

                1. Review the research findings.
                2. {"Incorporate the safety validation." if has_validator else "No safety validation was required."}
                3. Write for a non-specialist, citing sources.
                4. Keep any warnings prominent.
                """,
                agent=analyst,
                expected_output="Final guidance with citations and warnings.",
                context=list(tasks),
            )
        )

    logger.info(
        "Crew configured: %d agents (%s), %d tasks, cot=%s",
        len(agents),
        ", ".join(a.role for a in agents),
        len(tasks),
        analysis.use_chain_of_thought,
    )
    emit(
        EventType.STAGE_STARTED,
        stage="crew",
        agents=[a.role for a in agents],
        tasks=len(tasks),
    )

    try:
        return Crew(
            agents=agents,
            tasks=tasks,
            verbose=False,
            process=Process.sequential,
            task_callback=_on_task_complete,
        )
    except TypeError:
        # Older or newer CrewAI without task_callback: lose the per-task trace,
        # keep the run.
        logger.debug("CrewAI does not accept task_callback; continuing without it")
        return Crew(agents=agents, tasks=tasks, verbose=False, process=Process.sequential)
