"""Explicit chain-of-thought reasoning for safety-critical queries.

The router decides when a question needs step-by-step reasoning and supplies the
steps. This module executes them and returns the chain as structured data.

Structure matters here: an earlier version formatted the reasoning into markdown
and prepended it to the answer, which meant the UI could only show it as a wall of
text. Emitting each step as its own event lets the interface render reasoning as it
happens, and keeps the answer itself clean.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from crewai import LLM

from medical_agent.config import Config
from medical_agent.utils.events import EventType, emit

logger = logging.getLogger(__name__)

_STEP_HEADER = re.compile(r"^\*\*Step\s*(\d+)\s*:\s*(.+?)\*\*\s*$", re.IGNORECASE)


@dataclass
class ReasoningStep:
    index: int
    name: str
    reasoning: str = ""
    conclusion: str = ""

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "reasoning": self.reasoning,
            "conclusion": self.conclusion,
        }


@dataclass
class CoTResult:
    steps: list[ReasoningStep] = field(default_factory=list)
    final_answer: str = ""
    confidence: str = "medium"
    quality: str = "adequate"
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "steps": [s.as_dict() for s in self.steps],
            "final_answer": self.final_answer,
            "confidence": self.confidence,
            "quality": self.quality,
            "error": self.error,
        }


PROMPT = """You are a medical AI assistant using explicit step-by-step reasoning.

USER QUERY: "{query}"

REASONING STEPS TO FOLLOW:
{steps}

AVAILABLE RESEARCH DATA:
{findings}

For each step state what you are analysing, show your reasoning, and give a
conclusion. Use exactly this format:

**Step 1: [step name]**
Reasoning: [your reasoning]
Conclusion: [your conclusion]

**Step 2: [step name]**
Reasoning: [your reasoning]
Conclusion: [your conclusion]

After all steps:

**FINAL ANSWER:**
[answer synthesised from the steps above]

**CONFIDENCE LEVEL:** [High/Medium/Low]
**REASONING QUALITY:** [Strong/Adequate/Weak]
"""


class ChainOfThoughtProcessor:
    def __init__(self) -> None:
        self._llm: LLM | None = None

    @property
    def llm(self) -> LLM:
        if self._llm is None:
            self._llm = LLM(
                model=f"groq/{Config.GROQ_MODEL_NAME}",
                api_key=Config.GROQ_API_KEY,
                temperature=0.2,
                max_tokens=2000,
            )
        return self._llm

    def run(
        self,
        query: str,
        reasoning_steps: list[str],
        research_findings: str = "",
    ) -> CoTResult:
        prompt = PROMPT.format(
            query=query,
            steps="\n".join(f"{i}. {s}" for i, s in enumerate(reasoning_steps, 1)),
            findings=research_findings or "No research data provided.",
        )
        try:
            response = self.llm.call([{"role": "user", "content": prompt}])
        except Exception as exc:
            logger.warning("Chain-of-thought reasoning failed: %s", exc)
            return CoTResult(final_answer=research_findings, confidence="low", error=str(exc))

        result = self.parse(response)
        for step in result.steps:
            emit(EventType.COT_STEP, **step.as_dict())
        return result

    @staticmethod
    def parse(response: str) -> CoTResult:
        """Parse the structured reasoning response.

        Tolerant by design: a malformed response should still yield an answer.
        """
        steps: list[ReasoningStep] = []
        current: ReasoningStep | None = None
        buffer: list[str] = []

        def flush() -> None:
            if current is not None:
                current.reasoning = "\n".join(buffer).strip()
                steps.append(current)

        for raw_line in response.splitlines():
            line = raw_line.strip()
            header = _STEP_HEADER.match(line)
            if header:
                flush()
                buffer = []
                current = ReasoningStep(index=int(header.group(1)), name=header.group(2).strip())
            elif line.lower().startswith("reasoning:"):
                buffer.append(line.split(":", 1)[1].strip())
            elif line.lower().startswith("conclusion:") and current is not None:
                current.conclusion = line.split(":", 1)[1].strip()
            elif current is not None and line and not line.startswith("**"):
                buffer.append(line)
        flush()

        final_answer = ""
        if "**FINAL ANSWER:**" in response:
            tail = response.split("**FINAL ANSWER:**", 1)[1]
            final_answer = tail.split("**")[0].strip() if "**" in tail else tail.strip()

        return CoTResult(
            steps=steps,
            final_answer=final_answer,
            confidence=_pick(response, "CONFIDENCE LEVEL", ["high", "low"], "medium"),
            quality=_pick(response, "REASONING QUALITY", ["strong", "weak"], "adequate"),
        )


def _pick(response: str, label: str, options: list[str], default: str) -> str:
    for line in response.splitlines():
        if label in line:
            lowered = line.lower()
            for option in options:
                if option in lowered:
                    return option
    return default


def render_markdown(result: CoTResult) -> str:
    """Plain-text rendering for the non-streaming endpoint."""
    lines = ["## Chain of thought", ""]
    for step in result.steps:
        lines.append(f"**Step {step.index}: {step.name}**")
        if step.reasoning:
            lines.append(f"Reasoning: {step.reasoning}")
        if step.conclusion:
            lines.append(f"Conclusion: {step.conclusion}")
        lines.append("")
    lines += ["---", "", "## Answer", "", result.final_answer or "No answer generated.", ""]
    lines.append(f"Confidence: {result.confidence} | Reasoning quality: {result.quality}")
    return "\n".join(lines)


_processor: ChainOfThoughtProcessor | None = None


def get_cot_processor() -> ChainOfThoughtProcessor:
    global _processor
    if _processor is None:
        _processor = ChainOfThoughtProcessor()
    return _processor


def as_metadata(result: CoTResult) -> dict[str, Any]:
    return result.as_dict()
