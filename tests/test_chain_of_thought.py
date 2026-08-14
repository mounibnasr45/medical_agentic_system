"""Parsing of the model's step-by-step reasoning response.

The parser has to be forgiving: a malformed response should still yield an
answer rather than an exception or, worse, a silently truncated one.
"""

from medical_agent.utils.chain_of_thought import ChainOfThoughtProcessor

parse = ChainOfThoughtProcessor.parse

RESPONSE = """**Step 1: Identify the drugs**
Reasoning: The query names Aspirin and Warfarin.
Conclusion: Two anticoagulant-affecting drugs are involved.

**Step 2: Check the interaction**
Reasoning: The graph records a major interaction.
Conclusion: Concurrent use raises bleeding risk.

**FINAL ANSWER:**
The contraindications for Aspirin are:
*   **Bleeding disorders**
*   **Stomach ulcers**

Consult a clinician before combining these.

**CONFIDENCE LEVEL:** High
**REASONING QUALITY:** Strong
"""


def test_extracts_every_step():
    result = parse(RESPONSE)

    assert [s.index for s in result.steps] == [1, 2]
    assert result.steps[0].name == "Identify the drugs"
    assert result.steps[0].conclusion == "Two anticoagulant-affecting drugs are involved."


def test_answer_survives_bold_markup():
    """Regression: the answer was cut at the first '**', so a bulleted list of
    bold contraindications truncated it to a few characters."""
    answer = parse(RESPONSE).final_answer

    assert "Bleeding disorders" in answer
    assert "Stomach ulcers" in answer
    assert "Consult a clinician" in answer


def test_answer_stops_before_the_trailing_labels():
    answer = parse(RESPONSE).final_answer

    assert "CONFIDENCE LEVEL" not in answer
    assert "REASONING QUALITY" not in answer


def test_reads_confidence_and_quality():
    result = parse(RESPONSE)

    assert result.confidence == "high"
    assert result.quality == "strong"


def test_defaults_when_labels_are_absent():
    result = parse("**FINAL ANSWER:**\nJust an answer.")

    assert result.final_answer == "Just an answer."
    assert result.confidence == "medium"
    assert result.quality == "adequate"


def test_unparseable_response_yields_no_answer_rather_than_raising():
    result = parse("The model ignored the format entirely.")

    assert result.steps == []
    assert result.final_answer == ""
