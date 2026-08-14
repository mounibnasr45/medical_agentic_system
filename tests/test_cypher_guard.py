"""The read-only guard on generated Cypher.

Cypher is written by an LLM from user-supplied text and then executed against the
database. That makes it untrusted input regardless of what the generating prompt
asked for, so the guard is a security control rather than a validation nicety.
"""

import pytest

from medical_agent.tools.medical_tools import CypherQueryTool

reject = CypherQueryTool.reject_if_unsafe


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (n:Entity) WHERE toLower(n.name) CONTAINS 'aspirin' RETURN DISTINCT n LIMIT 20",
        "MATCH (a:Entity)-[r:RELATES_TO]-(b:Entity) WHERE toLower(r.fact) CONTAINS 'bleeding' "
        "RETURN DISTINCT a.name AS Name, r.fact AS Fact LIMIT 20",
        "MATCH (n:Entity) RETURN DISTINCT n.name AS Name LIMIT 20;",
    ],
)
def test_plain_reads_are_allowed(cypher):
    assert reject(cypher) is None


@pytest.mark.parametrize(
    "cypher",
    [
        "MATCH (n) DETACH DELETE n",
        "MATCH (n:Entity) DELETE n",
        "CREATE (n:Entity {name: 'x'}) RETURN n",
        "MERGE (n:Entity {name: 'x'}) RETURN n",
        "MATCH (n:Entity) SET n.name = 'x' RETURN n",
        "MATCH (n:Entity) REMOVE n.name RETURN n",
        "DROP INDEX entity_name",
        "LOAD CSV FROM 'http://evil.test/x.csv' AS row RETURN row",
        "MATCH (n) FOREACH (x IN [1] | DELETE n)",
        "CALL dbms.security.listUsers()",
        "CALL apoc.periodic.iterate('MATCH (n) RETURN n', 'DELETE n', {})",
        "CALL { MATCH (n) DELETE n } RETURN 1",
    ],
)
def test_mutating_and_administrative_clauses_are_rejected(cypher):
    assert reject(cypher) is not None


def test_statement_chaining_is_rejected():
    """A trailing read must not be able to smuggle in a second statement."""
    assert reject("MATCH (n) RETURN n; MATCH (m) DETACH DELETE m") is not None


def test_empty_input_is_rejected():
    assert reject("") is not None
    assert reject("   ") is not None


def test_rejection_names_the_offending_clause():
    reason = reject("MATCH (n) DETACH DELETE n")
    assert "DETACH" in reason.upper() or "DELETE" in reason.upper()
