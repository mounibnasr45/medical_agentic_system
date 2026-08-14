"""Central configuration, read once from the environment at import time."""

import os

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip())
    except ValueError:
        return default


def _csv(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    # --- Neo4j ---
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    # Aura's credentials file calls these NEO4J_USERNAME/NEO4J_DATABASE, so accept
    # both spellings rather than making the file's values silently not apply.
    NEO4J_USER = os.getenv("NEO4J_USER") or os.getenv("NEO4J_USERNAME") or "neo4j"
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    # Graphiti defaults this to "neo4j"; some Aura instances name the database
    # after the instance id, and querying the wrong one fails silently.
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE") or "neo4j"

    # --- API keys ---
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

    # --- Models ---
    GROQ_MODEL_NAME = os.getenv("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

    # Graph ingestion runs a different workload from the agents: Graphiti's entity
    # extraction prompts reach ~19k tokens, which exceeds Groq's free 12k
    # tokens-per-minute ceiling in a single request and can never succeed there.
    # Gemini handles ingestion; Groq stays for the agents, where prompts are small
    # and its latency is the advantage.
    GRAPH_LLM_PROVIDER = os.getenv("GRAPH_LLM_PROVIDER", "gemini").strip().lower()
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash")

    # Provider for the agents, router, reasoning and merge steps.
    #
    # Gemini by default for two reasons. CrewAI 1.x marks cache breakpoints on
    # agent messages and strips them only for providers it supports natively;
    # Groq is not one, so its messages arrive via LiteLLM carrying an unsupported
    # 'cache_breakpoint' property and every crew run fails. Groq's free tier also
    # caps at 12k tokens per minute, which a three-agent crew exhausts quickly.
    AGENT_LLM_PROVIDER = os.getenv("AGENT_LLM_PROVIDER", "gemini").strip().lower()

    @classmethod
    def agent_llm_model(cls) -> str:
        """Model identifier for CrewAI, provider prefix included."""
        if cls.AGENT_LLM_PROVIDER == "groq":
            return f"groq/{cls.GROQ_MODEL_NAME}"
        return f"gemini/{cls.GEMINI_MODEL_NAME}"

    @classmethod
    def agent_llm_api_key(cls) -> str | None:
        return cls.GROQ_API_KEY if cls.AGENT_LLM_PROVIDER == "groq" else cls.GOOGLE_API_KEY

    # Must match the dimension of the Neo4j vector index. Changing it needs a re-seed.
    EMBEDDING_DIM = _int("EMBEDDING_DIM", 768)

    # --- Deployment ---
    PORT = _int("PORT", 8000)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    # Exact origins allowed to call the API. Empty means local dev only.
    _EXPLICIT_ORIGINS = _csv("ALLOWED_ORIGINS")
    LOCAL_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ALLOWED_ORIGINS = _EXPLICIT_ORIGINS or LOCAL_DEV_ORIGINS

    # Per-IP queries per UTC day, protecting LLM spend on a public demo.
    DAILY_QUERY_LIMIT = _int("DAILY_QUERY_LIMIT", 5)

    # When false, the graph layer is skipped entirely and agents run on web + LLM.
    GRAPH_ENABLED = _bool("GRAPH_ENABLED", True)

    @classmethod
    def graph_configured(cls) -> bool:
        """True when the graph has everything it needs to connect."""
        return bool(
            cls.GRAPH_ENABLED
            and cls.NEO4J_URI
            and cls.NEO4J_USER
            and cls.NEO4J_PASSWORD
            and cls.GOOGLE_API_KEY
        )

    @classmethod
    def missing_required(cls) -> list[str]:
        """Names of settings the app cannot start usefully without."""
        missing = []
        if not cls.agent_llm_api_key():
            missing.append("GROQ_API_KEY" if cls.AGENT_LLM_PROVIDER == "groq" else "GOOGLE_API_KEY")
        return missing
