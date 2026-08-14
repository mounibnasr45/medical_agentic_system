"""The graph's model clients must be declared, never defaulted.

Graphiti falls back to OpenAI for every component it is not given: the LLM, the
embedder and the cross-encoder. Those defaults require OPENAI_API_KEY, which this
deployment does not have. The failure is nasty because it hides on any machine
where that variable happens to be set and appears only in deployment, reported as
"graph unavailable" rather than as a missing dependency.
"""

from medical_agent.config import Config
from medical_agent.graph.client import GraphGateway


def test_cross_encoder_is_gemini_not_openai(monkeypatch):
    """Regression: an unset cross_encoder defaulted to OpenAIRerankerClient and
    took the whole knowledge graph offline in production."""
    monkeypatch.setattr(Config, "GOOGLE_API_KEY", "test-key-not-used")

    encoder = GraphGateway()._build_cross_encoder()

    assert type(encoder).__name__ == "GeminiRerankerClient"


def test_embedder_is_gemini_not_openai(monkeypatch):
    monkeypatch.setattr(Config, "GOOGLE_API_KEY", "test-key-not-used")

    embedder = GraphGateway()._build_embedder()

    assert type(embedder).__name__ == "GeminiEmbedder"


def test_embedder_uses_the_configured_dimension(monkeypatch):
    """Graphiti reads EMBEDDING_DIM from the environment at import time, which is
    too fragile to rely on; it has to be passed explicitly. A mismatch with the
    seeded index makes vector search return nothing, silently."""
    monkeypatch.setattr(Config, "GOOGLE_API_KEY", "test-key-not-used")
    monkeypatch.setattr(Config, "EMBEDDING_DIM", 768)

    embedder = GraphGateway()._build_embedder()

    assert embedder.config.embedding_dim == 768


def test_graph_llm_defaults_to_gemini(monkeypatch):
    monkeypatch.setattr(Config, "GRAPH_LLM_PROVIDER", "gemini")
    monkeypatch.setattr(Config, "GOOGLE_API_KEY", "test-key-not-used")

    assert type(GraphGateway()._build_llm_client()).__name__ == "GeminiClient"


def test_graph_llm_honours_the_groq_override(monkeypatch):
    monkeypatch.setattr(Config, "GRAPH_LLM_PROVIDER", "groq")
    monkeypatch.setattr(Config, "GROQ_API_KEY", "test-key-not-used")

    assert type(GraphGateway()._build_llm_client()).__name__ == "GroqClient"


def test_agent_model_carries_a_provider_prefix(monkeypatch):
    """CrewAI routes on the prefix; without it the model resolves to no provider."""
    monkeypatch.setattr(Config, "AGENT_LLM_PROVIDER", "gemini")
    assert Config.agent_llm_model().startswith("gemini/")

    monkeypatch.setattr(Config, "AGENT_LLM_PROVIDER", "groq")
    assert Config.agent_llm_model().startswith("groq/")
