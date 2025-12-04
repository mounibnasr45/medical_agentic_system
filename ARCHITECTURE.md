# 🏗️ System Architecture - Medical Graph RAG Agent

## **Current Architecture (v2.0 - Simplified)**

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER REQUEST                                 │
│  "What are the contraindications for Aspirin?"                      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     FastAPI Server :8000                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ POST /ask         → General medical queries                  │  │
│  │ GET  /graph-info  → Health check                             │  │
│  │ POST /seed        → Initialize graph with sample data        │  │
│  │ POST /add-document → Upload custom medical documents         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   CrewAI Orchestration                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Single Agent: "Medical Pharmacist"                           │  │
│  │  - Role: Answer medical queries                              │  │
│  │  - Tools: Graph Search + Web Search                          │  │
│  │  - Max Iterations: 5 (prevents loops)                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  Task Flow:                                                         │
│  1. Check Graph Database (local knowledge)                         │
│  2. If empty, search Web (DuckDuckGo)                              │
│  3. Synthesize answer                                              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      Tool Layer (Cached)                            │
│  ┌────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  Graph Database Tool   │  │     Web Search Tool             │  │
│  │  - Graphiti + Neo4j    │  │     - DuckDuckGo API            │  │
│  │  - Entity/Edge search  │  │     - Top 3 results             │  │
│  │  - 1hr cache TTL       │  │     - 1hr cache TTL             │  │
│  └────────────────────────┘  └─────────────────────────────────┘  │
│                                                                     │
│  Cache Strategy:                                                    │
│  - Key: hash(tool_name + normalized_query)                         │
│  - TTL: 1 hour                                                      │
│  - Storage: In-memory dict (should be Redis for prod)              │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                       LLM Providers                                 │
│  ┌────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  Agent LLM (CrewAI)    │  │  Graph LLM (Graphiti)           │  │
│  │  Ollama llama3.2:3b    │  │  Groq llama-3.3-70b             │  │
│  │  - Local inference     │  │  - API-based                    │  │
│  │  - Unlimited requests  │  │  - 100k tokens/day limit        │  │
│  │  - Weak reasoning      │  │  - Strong reasoning             │  │
│  │  localhost:11434       │  │  Rate limit risk ⚠️             │  │
│  └────────────────────────┘  └─────────────────────────────────┘  │
│                                                                     │
│  Embeddings: all-MiniLM-L6-v2 (sentence-transformers, local)       │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   Data Storage Layer                                │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Neo4j Graph Database (localhost:7687)                        │  │
│  │                                                               │  │
│  │  Nodes:                                                       │  │
│  │  ├─ Drug (e.g., "Aspirin", "Warfarin")                       │  │
│  │  ├─ Condition (e.g., "Bleeding disorders")                   │  │
│  │  └─ Effect (e.g., "Reye's syndrome")                         │  │
│  │                                                               │  │
│  │  Edges (Relationships):                                       │  │
│  │  ├─ CONTRAINDICATED_IN (Drug → Condition)                    │  │
│  │  ├─ INTERACTS_WITH (Drug ↔ Drug)                             │  │
│  │  ├─ ALSO_KNOWN_AS (Drug → Alias)                             │  │
│  │  └─ CAUSES (Drug → Effect)                                   │  │
│  │                                                               │  │
│  │  Sample Data (from seed.py):                                 │  │
│  │  - Aspirin contraindications                                 │  │
│  │  - Aspirin + Warfarin interaction                            │  │
│  │  - Metformin side effects                                    │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## **Request Flow Example**

### **Query:** "What are the contraindications for Aspirin?"

```
1. User → FastAPI /ask endpoint
   POST {"query": "What are the contraindications for Aspirin?"}

2. FastAPI → CrewAI Crew
   create_medical_crew(query)

3. CrewAI → Medical Pharmacist Agent
   Task: "Answer question using Graph first, then Web if needed"

4. Agent → Graph Database Tool
   Tool Call: graph_db_tool.run("Aspirin contraindications")

5. Graph Tool → Cache Check
   Key: hash("GraphDB:aspirin contraindications")
   Result: MISS (first query)

6. Graph Tool → Neo4j
   Cypher: Vector similarity search + keyword matching
   Results: 
   - "Aspirin is contraindicated in Bleeding disorders"
   - "Aspirin is contraindicated in Stomach ulcers"
   - "Aspirin is contraindicated in children (Reye's syndrome)"

7. Graph Tool → Cache Store
   Store results with 1hr TTL

8. Graph Tool → Agent
   Return formatted facts

9. Agent → LLM (Ollama)
   Prompt: "Based on these facts: [facts], answer: [query]"
   LLM Response: "Aspirin contraindications include..."

10. Agent → CrewAI
    Task Complete

11. CrewAI → FastAPI
    Return formatted response

12. FastAPI → User
    {"response": "The contraindications for Aspirin include..."}
```

**Total Time:** ~8-10 seconds (without redundant calls)

---

## **Data Flow Diagram**

```
        [User Query]
             ↓
    ┌────────────────┐
    │  FastAPI       │
    └────────────────┘
             ↓
    ┌────────────────┐
    │  CrewAI Crew   │
    └────────────────┘
             ↓
    ┌──────────────────────────────┐
    │  Medical Pharmacist Agent    │
    │  (Ollama llama3.2:3b)        │
    └──────────────────────────────┘
         ↓              ↓
    ┌─────────┐   ┌──────────┐
    │ Graph   │   │   Web    │
    │ Search  │   │  Search  │
    └─────────┘   └──────────┘
         ↓              ↓
    ┌─────────┐   ┌──────────┐
    │ Cache   │   │  Cache   │
    │ Check   │   │  Check   │
    └─────────┘   └──────────┘
         ↓              ↓
    ┌─────────┐   ┌──────────┐
    │ Neo4j   │   │ DuckDuck │
    │ + Groq  │   │   Go     │
    └─────────┘   └──────────┘
         ↓              ↓
    [Structured     [Web Results]
     Graph Data]
         ↓              ↓
    ┌──────────────────────────────┐
    │     Agent Synthesis          │
    │   (Combines both sources)    │
    └──────────────────────────────┘
                 ↓
            [Final Answer]
```

---

## **Technology Stack**

### **Backend**
- **API Framework:** FastAPI 0.104+
- **Agent Framework:** CrewAI 0.80+
- **Async Runtime:** asyncio, uvloop

### **AI/ML**
- **Agent LLM:** Ollama llama3.2:3b (local)
- **Graph LLM:** Groq llama-3.3-70b (API) ⚠️ Rate limited
- **Embeddings:** sentence-transformers/all-MiniLM-L6-v2
- **Graph RAG:** Graphiti

### **Data Storage**
- **Graph DB:** Neo4j 5.x (bolt://localhost:7687)
- **Cache:** In-memory dict (should upgrade to Redis)

### **Tools**
- **Web Search:** DuckDuckGo Search API
- **Schema Validation:** Pydantic v2

---

## **File Structure**

```
genai_agent_project/
├── medical_agent/
│   ├── __init__.py
│   ├── config.py              # Environment variables, settings
│   ├── agents/
│   │   └── crew.py            # Agent + Crew definitions
│   ├── api/
│   │   └── server.py          # FastAPI endpoints
│   ├── graph/
│   │   ├── client.py          # Graphiti client factory
│   │   ├── groq_client.py     # Groq LLM wrapper
│   │   ├── local_embedder.py  # Sentence-transformer embedder
│   │   └── seed.py            # Sample data ingestion
│   ├── tools/
│   │   └── medical_tools.py   # Graph + Web search tools
│   └── utils/
│       └── ingestion.py       # Document processing
├── data/
│   └── sample_drugs.txt       # Medical knowledge base
├── test_agent_cases.py        # Integration tests
├── test_retrieval.py          # Graph query tests
├── IMPROVEMENTS.md            # This roadmap
└── README.md                  # Setup instructions
```

---

## **Key Design Decisions**

### **1. Why Single Agent?**
**Before:** 3 agents (Researcher, Safety, Analyst)  
**After:** 1 agent (Medical Pharmacist)

**Reasons:**
- Reduces token consumption (3 LLM calls → 1)
- Eliminates inter-agent delegation overhead
- Clearer reasoning chain
- Faster responses

**Trade-off:** Less specialized reasoning, but acceptable for current use case

---

### **2. Why Hybrid LLM?**
**Agents:** Ollama (local, weak)  
**Graph:** Groq (API, strong)

**Reasons:**
- Groq llama-3.3-70b excels at knowledge graph operations
- Ollama llama3.2:3b sufficient for simple agent tasks
- Cost optimization (graph ops are infrequent)

**Trade-off:** Still vulnerable to Groq rate limits

---

### **3. Why DuckDuckGo over Google?**
**Reasons:**
- No API key required
- Free unlimited searches
- Privacy-focused

**Trade-off:** Lower quality results vs Google Custom Search

---

### **4. Why In-Memory Cache?**
**Reasons:**
- Simple to implement
- Low latency (microseconds)
- Sufficient for single-instance deployment

**Trade-off:** Not suitable for multi-instance (use Redis for production)

---

## **Scalability Considerations**

### **Current Limitations**
| Component | Max Capacity | Bottleneck |
|-----------|--------------|------------|
| FastAPI | ~1000 req/s | Single-threaded crew.kickoff() |
| Ollama | ~5 req/s | GPU/CPU inference speed |
| Neo4j | ~10k queries/s | Graph complexity |
| Cache | Unlimited | Memory (GB) |

### **Scaling Strategies**

**Horizontal Scaling:**
```
┌──────────┐   ┌──────────┐   ┌──────────┐
│ API      │   │ API      │   │ API      │
│ Instance │   │ Instance │   │ Instance │
└──────────┘   └──────────┘   └──────────┘
     ↓              ↓              ↓
┌─────────────────────────────────────────┐
│        Load Balancer (nginx)            │
└─────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────┐
│    Shared Neo4j + Redis Cluster         │
└─────────────────────────────────────────┘
```

**Vertical Scaling:**
- Upgrade to 8B/70B Ollama model (requires GPU)
- Increase Neo4j memory allocation
- Use Redis for distributed caching

---

## **Security Model**

### **Current State: ⚠️ INSECURE**
- No authentication
- No input validation
- No rate limiting
- Groq API key in plaintext .env

### **Recommended Production Security**

```python
# 1. API Key Authentication
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    if request.url.path.startswith("/ask"):
        api_key = request.headers.get("X-API-Key")
        if not secrets.compare_digest(api_key, os.getenv("API_KEY")):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

# 2. Rate Limiting
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)

@app.post("/ask")
@limiter.limit("10/minute")
async def ask_agent(...):
    ...

# 3. Input Sanitization
class QueryRequest(BaseModel):
    query: str = Field(..., max_length=500, regex=r'^[a-zA-Z0-9\s\?\.]+$')
```

---

## **Monitoring & Observability**

### **What to Monitor**

1. **API Metrics**
   - Request latency (p50, p95, p99)
   - Error rate (4xx, 5xx)
   - Throughput (req/s)

2. **Agent Metrics**
   - Tool call frequency
   - Tool call success rate
   - Average iterations per query

3. **System Metrics**
   - Ollama GPU/CPU usage
   - Neo4j memory/disk usage
   - Cache hit rate

### **Recommended Stack**
- **Metrics:** Prometheus + Grafana
- **Logging:** Structured logging (JSON) → Loki
- **Tracing:** OpenTelemetry → Jaeger
- **Alerts:** AlertManager → PagerDuty/Slack

---

## **Deployment Options**

### **Option 1: Docker Compose (Recommended for Dev)**
```yaml
services:
  neo4j:
    image: neo4j:5.15
    ports: [7687:7687, 7474:7474]
  
  ollama:
    image: ollama/ollama
    volumes: [./models:/root/.ollama]
  
  api:
    build: .
    ports: [8000:8000]
    depends_on: [neo4j, ollama]
```

### **Option 2: Kubernetes (Production)**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: medical-agent
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: api
        image: medical-agent:v2.0
        resources:
          limits: {cpu: 2, memory: 4Gi}
```

### **Option 3: Cloud (Managed Services)**
- **Neo4j:** Neo4j Aura
- **Ollama:** Self-host on GPU instance (AWS g4dn.xlarge)
- **API:** AWS ECS Fargate / GCP Cloud Run

---

**Last Updated:** December 4, 2025  
**Architecture Version:** 2.0 (Simplified)
