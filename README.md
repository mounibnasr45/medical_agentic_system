# 🏥 Intelligent Medical Agent System

> **Advanced Multi-Agent AI System for Clinical Decision Support**  
> Built with CrewAI, GraphRAG, Neo4j, and LangChain Memory

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-green)](https://fastapi.tiangolo.com/)
[![Neo4j](https://img.shields.io/badge/Neo4j-5.x-blue)](https://neo4j.com/)
[![CrewAI](https://img.shields.io/badge/CrewAI-Latest-orange)](https://www.crewai.com/)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [Setup Instructions](#setup-instructions)
- [Usage Guide](#usage-guide)
- [API Documentation](#api-documentation)
- [System Components](#system-components)
- [Performance Optimizations](#performance-optimizations)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Deployment](#deployment)
- [Future Enhancements](#future-enhancements)

---

## 🎯 Overview

This project demonstrates an enterprise-grade **AI-powered medical assistant** that combines multiple advanced technologies to provide intelligent clinical decision support. The system uses **multi-agent orchestration**, **GraphRAG (Graph Retrieval-Augmented Generation)**, and **LangChain memory** to deliver context-aware, accurate medical information.

### Business Value

- **Intelligent Query Routing**: LLM-powered router analyzes queries and dynamically allocates agents
- **Knowledge Graph Integration**: Neo4j + Graphiti for semantic medical knowledge
- **Conversational Memory**: Multi-session support with context persistence
- **Real-time Streaming**: Server-Sent Events for live agent reasoning
- **Production-Ready**: Caching, error handling, and performance optimization

### Use Cases

1. **Drug Interaction Checking**: Identify contraindications between medications
2. **Clinical Decision Support**: Provide evidence-based treatment recommendations
3. **Patient Query Assistance**: Answer medication and condition questions
4. **Medical Knowledge Search**: Hybrid vector + graph search across medical data

---

## ✨ Key Features

### 🤖 Multi-Agent System (CrewAI)

- **3 Specialized Agents**:
  - **Clinical Researcher**: Graph database + web search
  - **Safety Validator**: Cross-checks contraindications
  - **Clinical Analyst**: Synthesizes final recommendations
  
- **Dynamic Agent Selection**: 1-3 agents based on query complexity
- **Tool Diversity Enforcement**: Prevents redundant tool calls
- **Hierarchical Task Delegation**: Structured decision-making

### 🧠 Intelligent Query Router (LLM-Powered)

- **Groq Llama-3.3-70B** for query analysis
- **JSON-structured output** with Pydantic validation
- **Automatic complexity scoring** (1-5 scale)
- **Non-medical query rejection** with explanations
- **Adaptive iteration limits** based on complexity

```python
# Example routing decision
Query: "Can I take Aspirin with Warfarin?"
Analysis:
  - Intent: drug_interaction
  - Complexity: 3/5
  - Agents: researcher, validator, analyst
  - Max Iterations: 4
  - Tools Priority: [graph_db, web_search, cypher_query]
```

### 🕸️ GraphRAG Knowledge System

- **Neo4j Graph Database**: Stores medical entities and relationships
- **Graphiti Integration**: Hybrid vector + graph search
- **Semantic Search**: all-MiniLM-L6-v2 embeddings
- **Fact Extraction**: Automatic entity and relationship extraction
- **Cypher Query Tool**: Complex graph traversals

### 💬 Conversation Memory (LangChain)

- **Session-based memory**: Isolated conversations per user
- **In-memory storage**: Fast access, no disk I/O
- **Context injection**: Previous messages inform current query
- **Auto-summarization**: Long conversations compressed
- **Memory statistics**: Track conversation metrics

```python
# Multi-turn conversation example
User: "Tell me about Aspirin"
AI: "Aspirin is an NSAID used for pain relief..."

User: "What are its interactions?" 
AI: "Aspirin interacts with Warfarin, increasing bleeding risk..."
     ↑ AI remembers "Aspirin" from context
```

### ⚡ Performance Optimizations

- **Response Caching**: MD5-hashed query results (1-hour TTL)
- **Tool-level Caching**: Graph DB and web search results cached
- **Session-aware Caching**: Cache per session + query
- **Streaming Responses**: Server-Sent Events (SSE) for real-time output
- **Lazy Loading**: Neo4j driver and embeddings loaded on demand

### 🛠️ Custom Tools (3)

1. **Graph Database Search**: Hybrid vector + graph retrieval
2. **Web Search**: DuckDuckGo fallback for missing data
3. **Cypher Query Executor**: Complex graph pattern matching

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Server                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │  POST /ask (with session_id, query)                │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  MemoryManager (LangChain)                          │    │
│  │  - Get/Create session                               │    │
│  │  - Load conversation history                        │    │
│  │  - Inject context into query                        │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  Intelligent Router (Groq Llama-3.3-70B)            │    │
│  │  - Analyze query complexity                         │    │
│  │  - Classify intent (drug_info, interaction, etc)   │    │
│  │  - Determine agent count (1-3)                      │    │
│  │  - Set iteration limits (3-5)                       │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  Medical Crew (CrewAI)                              │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Agent 1: Clinical Researcher                 │  │    │
│  │  │  Tools: Graph DB, Web Search, Cypher          │  │    │
│  │  │  Max Iterations: 3-5 (adaptive)               │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Agent 2: Safety Validator (optional)         │  │    │
│  │  │  Validates contraindications                  │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  │  ┌──────────────────────────────────────────────┐  │    │
│  │  │  Agent 3: Clinical Analyst (optional)         │  │    │
│  │  │  Synthesizes final recommendation             │  │    │
│  │  └──────────────────────────────────────────────┘  │    │
│  └──────────────────┬─────────────────────────────────┘    │
│                     │                                        │
│  ┌──────────────────▼─────────────────────────────────┐    │
│  │  Tools Layer                                        │    │
│  │  ┌────────────┐  ┌────────────┐  ┌─────────────┐  │    │
│  │  │ Graph DB   │  │ Web Search │  │ Cypher      │  │    │
│  │  │ (Graphiti) │  │ (DuckDuck) │  │ (Neo4j)     │  │    │
│  │  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘  │    │
│  └────────┼───────────────┼─────────────────┼─────────┘    │
│           │               │                 │               │
└───────────┼───────────────┼─────────────────┼───────────────┘
            │               │                 │
    ┌───────▼────────┐     │         ┌───────▼────────┐
    │  Neo4j         │     │         │  Neo4j         │
    │  + Graphiti    │     │         │  Direct        │
    │  (Hybrid)      │     │         │  Cypher        │
    └────────────────┘     │         └────────────────┘
                   ┌───────▼────────┐
                   │  DuckDuckGo    │
                   │  Web Search    │
                   └────────────────┘
```

### Data Flow

1. **User Query** → FastAPI `/ask` endpoint
2. **Memory Retrieval** → Load session history, inject context
3. **Intelligent Routing** → LLM analyzes query → Returns configuration
4. **Crew Execution** → 1-3 agents collaborate with tools
5. **Response Generation** → Final answer synthesized
6. **Memory Update** → Save user query + AI response
7. **Caching** → Store result for future identical queries

---

## 🛠️ Technology Stack

### Core Frameworks

| Technology | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.8+ | Programming language |
| **FastAPI** | 0.100+ | REST API server with async support |
| **CrewAI** | Latest | Multi-agent orchestration framework |
| **LangChain** | 0.3.0+ | Memory management & LLM chains |
| **Neo4j** | 5.x | Graph database for medical knowledge |
| **Graphiti** | Latest | Hybrid vector + graph search |

### AI/ML Components

| Component | Model/Service | Use Case |
|-----------|---------------|----------|
| **Query Router** | Groq Llama-3.3-70B | Intent classification & routing |
| **Agent LLM** | Groq Llama-3.3-70B | Agent reasoning & responses |
| **Embeddings** | all-MiniLM-L6-v2 | Semantic vector search |
| **Summarization** | Groq Llama-3.3-70B | Conversation summaries |

### Infrastructure

- **DuckDuckGo Search API**: Web fallback when graph data insufficient
- **Uvicorn**: ASGI server for FastAPI
- **Pydantic**: Data validation and JSON schema
- **Python Logging**: Structured logging system

---

## 📦 Setup Instructions

### Prerequisites

1. **Neo4j Database** (Desktop or Aura)
   - Download: https://neo4j.com/download/
   - Create database named `medical_graph`
   - Note connection details (URI, username, password)

2. **API Keys**
   - **Groq API Key**: https://console.groq.com/
   - **Google API Key** (optional): For Gemini embeddings

### Installation

```bash
# 1. Clone repository
git clone https://github.com/mounibnasr45/medical_agentic_system.git
cd medical_agentic_system

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your credentials
```

### Environment Configuration

Create `.env` file in project root:

```env
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# AI API Keys
GROQ_API_KEY=gsk_your_groq_api_key_here
GOOGLE_API_KEY=your_google_api_key_here  # Optional

# Application Settings
LOG_LEVEL=INFO
CACHE_TTL=3600
```

### Database Seeding

```bash
# Seed Neo4j with initial medical data
python ingest_drugs.py

# Or use the Python module
python -m medical_agent.graph.seed
```

**Sample Data Loaded**:
- Aspirin, Warfarin, Ibuprofen drug profiles
- Drug interactions and contraindications
- Side effects and usage guidelines

---

## 🚀 Usage Guide

### 1️⃣ Start the Application

The easiest way to launch the full system (Server + UI) is:

```bash
python start_app.py
```

This script will:
1. Check if your Neo4j database is running
2. Start the FastAPI backend server
3. Automatically open the Chat UI in your default browser

### 2️⃣ Access the Interfaces

- **Web Chat UI**: [http://localhost:8000/chat](http://localhost:8000/chat)
- **API Documentation (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Root**: [http://localhost:8000](http://localhost:8000)

### 3️⃣ Alternative Launch Method

If you prefer to run the server manually without the helper script:

```bash
python -m medical_agent.api.server
```

### API Endpoints

#### 1. **Ask Agent** (Unified Intelligent Endpoint)

```bash
POST /ask
Content-Type: application/json

{
  "query": "Can I take Aspirin with Warfarin?",
  "session_id": "optional_session_id",  # Auto-generated if not provided
  "use_mcp": null,     # Optional: Force MCP mode (true) or Crew mode (false). Auto-detect if null.
  "stream": false      # Optional: Enable streaming (not yet implemented)
}
```

**Features**:
- **Auto-detection**: Automatically selects MCP or Crew mode based on query complexity
- **Multi-Context Processing (MCP)**: Parallel tool execution for complex queries (complexity ≥3)
- **Chain of Thought (CoT)**: Step-by-step reasoning for complex medical questions
- **Memory Integration**: Uses session context from previous conversations
- **Smart Caching**: Normalized cache keys for semantic duplicate detection

**Response (Crew Mode)**:
```json
{
  "response": "Taking Aspirin with Warfarin significantly increases bleeding risk...",
  "session_id": "a3f2e1c4b5d6",
  "from_cache": false,
  "processing_mode": "CREW",
  "memory_stats": {
    "total_messages": 2,
    "user_messages": 1,
    "ai_messages": 1
  },
  "analysis": {
    "intent": "drug_interaction",
    "complexity": 3,
    "use_cot": true,
    "agents_used": ["researcher", "validator", "analyst"]
  }
}
```

**Response (MCP Mode)**:
```json
{
  "response": "## Research Results\n\nAspirin and Warfarin interaction...",
  "session_id": "a3f2e1c4b5d6",
  "from_cache": false,
  "processing_mode": "MCP",
  "latency_ms": 1250,
  "sources_used": ["graph_db", "cypher", "web"],
  "confidence": 0.87,
  "analysis": {
    "intent": "drug_interaction",
    "complexity": 4,
    "use_cot": true
  }
}
```

**Processing Mode Selection Logic**:
- **MCP Mode (Parallel)**: complexity ≥3 AND intent="interaction" AND multiple tools needed
- **Crew Mode (Sequential)**: All other queries
- **Manual Override**: Set `use_mcp=true` to force MCP mode

#### 2. **Create New Session**

```bash
POST /sessions/new
```

**Response**:
```json
{
  "session_id": "b7c8d9e0f1a2",
  "message": "New session created"
}
```

#### 3. **Get Conversation History**

```bash
GET /sessions/{session_id}/history?limit=20
```

**Response**:
```json
{
  "session_id": "a3f2e1c4b5d6",
  "history": [
    {"role": "user", "content": "What is Aspirin?"},
    {"role": "assistant", "content": "Aspirin is an NSAID..."}
  ],
  "stats": {
    "total_messages": 10,
    "user_messages": 5,
    "ai_messages": 5
  }
}
```


## 📊 System Components

### 1. Intelligent Router (`intelligent_router.py`)

**Purpose**: Analyzes queries and determines optimal agent configuration

**Key Capabilities**:
- LLM-powered intent classification (7 categories)
- Complexity scoring (1-5 scale)
- Dynamic agent selection (1-3 agents)
- Adaptive iteration limits (3-5 iterations)
- Non-medical query rejection

**Sample Output**:
```python
QueryAnalysis(
    intent="drug_interaction",
    complexity=3,
    required_agents=["researcher", "validator", "analyst"],
    max_iterations={"researcher": 4, "validator": 2, "analyst": 2},
    suggested_tools=["graph_db", "web_search"],
    is_medical=True,
    confidence=0.95,
    reasoning="Complex drug interaction requires multi-agent validation"
)
```

### 2. Memory Manager (`memory_manager.py`)

**Purpose**: Manages conversation context across sessions

**Features**:
- In-memory session storage (no disk I/O)
- LangChain ConversationBufferMemory integration
- Context injection into queries
- Automatic conversation summarization (10+ messages)
- Memory statistics tracking

**Architecture**:
```python
MemoryManager (Singleton)
    ├── Session 1: MedicalConversationMemory
    │   ├── ConversationBufferMemory
    │   ├── Groq LLM (for summarization)
    │   └── Session ID: "a3f2e1c4b5d6"
    ├── Session 2: MedicalConversationMemory
    └── Session N: ...
```

### 3. Medical Crew (`crew.py`)

**Purpose**: Orchestrates multi-agent collaboration

**Agents**:

| Agent | Role | Tools | Max Iterations |
|-------|------|-------|----------------|
| **Clinical Researcher** | Research medical info | Graph DB, Web, Cypher | 3-5 (adaptive) |
| **Safety Validator** | Validate safety | Graph DB, Cypher | 2 |
| **Clinical Analyst** | Synthesize findings | All tools | 2 |

**Task Flow**:
1. Research Task → Researcher gathers data
2. Validation Task → Validator checks contraindications
3. Analysis Task → Analyst provides final recommendation

### 4. Custom Tools

#### Graph Database Tool
```python
class GraphDBTool(BaseTool):
    """Hybrid vector + graph search using Graphiti"""
    
    def _run(self, query: str) -> str:
        # 1. Generate embedding for query
        # 2. Search Neo4j graph (vector + traversal)
        # 3. Return top 5 facts with caching
```

#### Web Search Tool
```python
class WebSearchTool(BaseTool):
    """DuckDuckGo fallback search"""
    
    def _run(self, query: str) -> str:
        # 1. Check cache first
        # 2. Search DuckDuckGo (max 3 results)
        # 3. Cache and return formatted results
```

#### Cypher Query Tool
```python
class CypherQueryTool(BaseTool):
    """Execute custom Neo4j Cypher queries"""
    
    def _run(self, query: str) -> str:
        # 1. Convert natural language to Cypher
        # 2. Execute on Neo4j
        # 3. Format and return results
```

---

## ⚡ Performance Optimizations

### 1. Multi-Level Caching

```python
# Response Cache (Complete Queries)
RESPONSE_CACHE = {}  # MD5 key → response string
TTL = 3600 seconds

# Tool-Level Cache (Graph DB & Web Search)
_TOOL_CACHE = {}  # (tool_name, query) → (result, timestamp)
TTL = 3600 seconds

# Session-Aware Cache
cache_key = md5(f"{session_id}:{query}")
```

### 2. Lazy Loading

- **Neo4j Driver**: Initialized only when first tool is called
- **Graphiti Client**: Created on-demand with async context manager
- **Embeddings Model**: Loaded once on first graph search

### 3. Streaming Output

```python
# Server-Sent Events for real-time agent thoughts
async def event_generator():
    yield f"data: {json.dumps({'type': 'thinking', 'message': '...'})}\n\n"
    # ... agent execution
    yield f"data: {json.dumps({'type': 'result', 'message': '...'})}\n\n"
```

### 4. Tool Diversity Enforcement

```markdown
**CRITICAL TOOL USAGE RULES:**
1. Try DIFFERENT tools in each iteration
2. If Graph DB returns incomplete info → switch to Web Search
3. If Graph DB returns "No info" → skip to Web Search
4. Only repeat a tool if it gave useful info
```

---

## 📁 Project Structure

```
medical_agentic_system/
├── medical_agent/
│   ├── agents/
│   │   └── crew.py                 # CrewAI agent definitions
│   ├── api/
│   │   └── server.py               # FastAPI endpoints
│   ├── graph/
│   │   ├── client.py               # Graphiti client wrapper
│   │   ├── local_embedder.py       # Custom embedding provider
│   │   └── seed.py                 # Database seeding script
│   ├── tools/
│   │   └── medical_tools.py        # Custom CrewAI tools (3)
│   ├── utils/
│   │   ├── intelligent_router.py   # LLM-powered query router
│   │   ├── memory_manager.py       # LangChain memory system
│   │   └── ingestion.py            # Document ingestion
│   └── config.py                   # Environment configuration
├── static/
│   └── chat.html                   # Web UI for chatbot
├── data/
│   └── (runtime data storage)
├── tests/
│   ├── test_smart_routing.py       # Router tests
│   └── test_memory_system.py       # Memory tests
├── ingest_drugs.py                 # Initial data seeding
├── start_app.py                    # Server startup script
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── README.md                       # This file
```

---

## 🧪 Testing

### Test Scripts

```bash
# 1. Test intelligent routing
python evaluate_system.py
```

### Sample Test Cases

#### Simple Query (1 Agent)
```
Query: "What is Aspirin?"
Expected: 1 agent, 3 iterations, uses Graph DB + Web
```

#### Drug Interaction (2 Agents)
```
Query: "Can I take Aspirin with Warfarin?"
Expected: 2 agents (researcher + validator), 4 iterations
```

#### Complex Analysis (3 Agents)
```
Query: "What are all contraindications for patients with bleeding disorders?"
Expected: 3 agents, 5 iterations, uses all tools
```

#### Non-Medical Query (Rejection)
```
Query: "What's the weather today?"
Expected: Instant rejection with explanation
```

## 🐳 Docker Deployment

You can containerize the application using Docker for easy deployment.

### 1. Build the Docker Image

```bash
docker build -t medical-agent .
```

### 2. Run the Container

Make sure your `.env` file is configured, then run:

```bash
docker run -p 8000:8000 --env-file .env medical-agent
```

The API will be available at `http://localhost:8000` and the Chat UI at `http://localhost:8000/chat`.

---

## 🔮 Future Enhancements

### Planned Features

1. **User Authentication**
   - JWT-based auth
   - Role-based access control (RBAC)
   - API key management

2. **Advanced Memory**
   - Semantic memory search across all sessions
   - Long-term user preferences
   - RAG over conversation history

3. **Enhanced Knowledge Graph**
   - Automatic medical literature ingestion
   - PubMed integration
   - Drug database sync (FDA, DrugBank)

4. **Multi-Modal Support**
   - Image analysis (medical scans)
   - PDF document processing
   - Voice query support

5. **Analytics Dashboard**
   - Query analytics
   - Agent performance metrics
   - User engagement tracking

6. **Fine-Tuning**
   - Custom medical LLM fine-tuning
   - Domain-specific embeddings
   - Tool usage optimization
## 👨‍💻 Developer

**Mounib Nasr**  
AI Engineer Candidate  
[GitHub](https://github.com/mounibnasr45) 

