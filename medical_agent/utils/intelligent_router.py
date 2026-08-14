"""LLM-powered query routing.

One cheap, deterministic LLM call decides how much machinery a query deserves:
whether it is medical at all, which agents to run, how many tool iterations each
gets, and whether the answer needs explicit chain-of-thought reasoning.

Routing with a model rather than keyword matching is the point: "can I take these
two together" and "is this combination safe" need identical handling, and no
keyword list captures that.

The router is the only component that must never hard-fail. If the routing call
errors, `_fallback` returns a conservative configuration that runs the full crew.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass

from crewai import LLM

from medical_agent.config import Config
from medical_agent.utils.events import EventType, emit

logger = logging.getLogger(__name__)

ROUTING_PROMPT = """You are an expert medical AI system architect. Analyse this query \
and determine the optimal agent configuration.

USER QUERY: "{query}"

Respond with ONLY valid JSON, no markdown and no explanation:

{{
  "is_medical": true/false,
  "confidence": 0.0-1.0,
  "intent": "drug_info|interaction|contraindication|side_effects|dosage|general_medical|non_medical",
  "complexity": 1-5,
  "required_agents": ["researcher", "validator", "analyst"],
  "max_iterations": {{"researcher": 1-4, "validator": 1-3, "analyst": 1-2}},
  "reasoning": "Brief explanation of your decisions",
  "suggested_tools": ["graph_db", "cypher", "web_search"],
  "rejection_message": "Message if non-medical, else null",
  "use_chain_of_thought": true/false,
  "cot_reasoning_steps": ["step1", "step2", "step3"] or null
}}

GUIDELINES

is_medical:
- true for drugs, medications, conditions, symptoms, treatments
- false for greetings, random text, off-topic requests

complexity:
1 simple definition, 2 single-drug information, 3 interaction or contraindication
between two entities, 4 multi-drug analysis, 5 comprehensive treatment planning

required_agents:
- complexity 1-2: ["researcher"]
- complexity 3 with interaction or contraindication: ["researcher", "validator"]
- complexity 4-5 or a comprehensive request: ["researcher", "validator", "analyst"]

max_iterations (each iteration should try a DIFFERENT tool):
- researcher: 3 at complexity 1-2, 4 at complexity 3, 5 at complexity 4-5
- validator: 2 at complexity 1-2, 3 above
- analyst: always 1, it synthesises and uses no tools

suggested_tools, in priority order:
- graph_db for entities likely present in the knowledge graph
- cypher for multi-hop questions such as interactions and contraindications
- web_search for recent information or rare drugs

use_chain_of_thought:
- true when complexity >= 3, several drugs or conditions are involved, or the
  decision is safety-critical
- false for a single straightforward lookup
When true, give 3-5 concrete reasoning steps. When false, use null.
"""


@dataclass
class QueryAnalysis:
    """The routing decision for one query."""

    is_medical: bool
    confidence: float
    intent: str
    complexity: int
    required_agents: list[str]
    max_iterations: dict[str, int]
    reasoning: str
    suggested_tools: list[str]
    rejection_message: str | None
    use_chain_of_thought: bool
    cot_reasoning_steps: list[str] | None

    def as_dict(self) -> dict:
        return asdict(self)


def _extract_json(text: str) -> dict:
    """Parse the model's JSON, tolerating code fences and surrounding prose."""
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        braces = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if braces:
            return json.loads(braces.group(0))
        raise


class IntelligentRouter:
    def __init__(self) -> None:
        self._llm: LLM | None = None

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = LLM(
                model=f"groq/{Config.GROQ_MODEL_NAME}",
                api_key=Config.GROQ_API_KEY,
                temperature=0.0,  # routing must be reproducible
                max_tokens=500,
            )
        return self._llm

    def analyze_query(self, query: str) -> QueryAnalysis:
        try:
            raw = self.llm.call([{"role": "user", "content": ROUTING_PROMPT.format(query=query)}])
            analysis = self._parse(_extract_json(raw))
        except Exception as exc:
            logger.warning("Routing failed (%s); using conservative defaults", exc)
            analysis = self._fallback()

        emit(
            EventType.ROUTER_COMPLETED,
            is_medical=analysis.is_medical,
            intent=analysis.intent,
            complexity=analysis.complexity,
            confidence=analysis.confidence,
            required_agents=analysis.required_agents,
            suggested_tools=analysis.suggested_tools,
            use_chain_of_thought=analysis.use_chain_of_thought,
            reasoning=analysis.reasoning,
        )
        return analysis

    @staticmethod
    def _parse(data: dict) -> QueryAnalysis:
        complexity = max(1, min(5, int(data.get("complexity", 3))))
        agents = data.get("required_agents") or ["researcher"]
        iterations = data.get("max_iterations") or {}
        return QueryAnalysis(
            is_medical=bool(data.get("is_medical", True)),
            confidence=float(data.get("confidence", 0.5)),
            intent=str(data.get("intent", "general_medical")),
            complexity=complexity,
            required_agents=[a for a in agents if a in {"researcher", "validator", "analyst"}]
            or ["researcher"],
            max_iterations={
                "researcher": int(iterations.get("researcher", 3)),
                "validator": int(iterations.get("validator", 2)),
                "analyst": int(iterations.get("analyst", 1)),
            },
            reasoning=str(data.get("reasoning", "")),
            suggested_tools=data.get("suggested_tools") or ["graph_db", "web_search"],
            rejection_message=data.get("rejection_message"),
            use_chain_of_thought=bool(data.get("use_chain_of_thought", False)),
            cot_reasoning_steps=data.get("cot_reasoning_steps"),
        )

    @staticmethod
    def _fallback() -> QueryAnalysis:
        """Conservative configuration used when routing itself fails.

        Assumes the query is medical and runs the full crew: a wasted crew run is
        cheaper than wrongly rejecting a legitimate clinical question.
        """
        return QueryAnalysis(
            is_medical=True,
            confidence=0.5,
            intent="general_medical",
            complexity=3,
            required_agents=["researcher", "validator", "analyst"],
            max_iterations={"researcher": 3, "validator": 2, "analyst": 1},
            reasoning="Routing model unavailable; conservative defaults applied.",
            suggested_tools=["graph_db", "cypher", "web_search"],
            rejection_message=None,
            use_chain_of_thought=False,
            cot_reasoning_steps=None,
        )


_router: IntelligentRouter | None = None


def get_router() -> IntelligentRouter:
    global _router
    if _router is None:
        _router = IntelligentRouter()
    return _router
