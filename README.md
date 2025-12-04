# Medical Agent with GraphRAG

This project implements a multi-agent system for clinical decision support using CrewAI, Graphiti, and Neo4j.

## Prerequisites

1.  **Neo4j**: You need a running Neo4j instance (Desktop or Aura).
2.  **API Keys**:
    *   `GOOGLE_API_KEY`: For Gemini (Graphiti).
    *   `OPENAI_API_KEY`: For CrewAI Agents.

## Setup

1.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

2.  Configure `.env`:
    Create a `.env` file in the root directory with your credentials.

## Running

1.  **Seed the Graph**:
    You can seed the graph by running the seed script directly or via the API.
    ```bash
    python -m medical_agent.graph.seed
    ```

2.  **Start the API**:
    ```bash
    python -m medical_agent.api.server
    ```

3.  **Query**:
    Send a POST request to `http://localhost:8000/ask`:
    ```json
    {
      "query": "Can I prescribe Warfarin and Aspirin together?"
    }
    ```
