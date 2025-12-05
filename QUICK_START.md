# 🚀 Quick Start Guide

## 🎯 Start the Application (3 Steps)

### **Step 1: Start Neo4j**
```powershell
# Open Neo4j Desktop and start your database
# OR if using command line:
neo4j start
```

### **Step 2: Start the Server**
```powershell
cd genai_agent_project
python start_app.py
```

This will:
- ✅ Check Neo4j connection
- ✅ Start FastAPI server on `http://localhost:8000`
- ✅ Auto-open chat UI in browser

### **Step 3: Use the Chat Interface**
The browser will automatically open to `http://localhost:8000/chat`

---

## 🛠️ Manual Startup (Alternative)

If `start_app.py` doesn't work:

```powershell
# Start server manually
python -m medical_agent.api.server

# Then open browser to:
# http://localhost:8000/chat
```

---

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/chat` | GET | Chat UI |
| `/ask` | POST | Ask a question (standard) |
| `/ask/stream` | POST | Ask a question (streaming) |
| `/graph-info` | GET | Graph statistics |
| `/add-document` | POST | Upload medical document |

---

## 💬 Example Queries

Try these in the chat interface:

1. **"What are the contraindications for Aspirin?"**
2. **"What are the interactions between Aspirin and Warfarin?"**
3. **"What are alternatives to Aspirin for pain relief?"**
4. **"Find all drugs that interact with Warfarin"** (uses Cypher tool)

---

## 🧪 Testing the API

### **Test with cURL (PowerShell)**

```powershell
# Standard request
curl -X POST http://localhost:8000/ask `
  -H "Content-Type: application/json" `
  -d '{\"query\": \"What are Aspirin contraindications?\"}'

# Streaming request
curl -N -X POST http://localhost:8000/ask/stream `
  -H "Content-Type: application/json" `
  -d '{\"query\": \"What are Aspirin contraindications?\"}'
```

### **Test with Python**

```python
import requests

# Standard request
response = requests.post(
    "http://localhost:8000/ask",
    json={"query": "What are Aspirin contraindications?"}
)
print(response.json())

# Streaming request
response = requests.post(
    "http://localhost:8000/ask/stream",
    json={"query": "What are Aspirin contraindications?"},
    stream=True
)
for line in response.iter_lines():
    if line:
        print(line.decode('utf-8'))
```

---

## 📊 View Logs

All tool usage is logged to `logs/tool_usage.log`:

```powershell
# Watch logs in real-time
Get-Content logs/tool_usage.log -Wait

# View last 20 lines
Get-Content logs/tool_usage.log -Tail 20
```

**Sample log output:**
```
2024-12-05 21:00:00 - Tool: Graph DB Search | Query: Aspirin contraindications
2024-12-05 21:00:02 - Tool: Graph DB Search | Success | Latency: 2.15s
2024-12-05 21:00:05 - Tool: Cypher Query | Generated Cypher: MATCH...
2024-12-05 21:00:07 - Tool: Cypher Query | Success | Records: 5 | Latency: 1.95s
```

---

## 🔧 Troubleshooting

### **Error: "Failed to fetch"**
- ✅ **Fix:** Server not running. Run `python start_app.py`

### **Error: "Neo4j not accessible"**
- ✅ **Fix:** Start Neo4j Desktop and start your database

### **Error: "No module named 'medical_agent'"**
- ✅ **Fix:** You're in the wrong directory
  ```powershell
  cd genai_agent_project
  python start_app.py
  ```

### **Chat UI shows "Chat UI not found"**
- ✅ **Fix:** File missing. The `static/chat.html` should exist
  ```powershell
  # Check if file exists
  Test-Path static/chat.html
  ```

### **Agent taking too long (40+ seconds)**
- ✅ **Expected:** Multi-agent workflow takes time
- ✅ **Use streaming:** Click "Stream" button instead of "Send"

### **"CypherQueryTool" object has no field "driver"**
- ✅ **Fixed:** This error is already resolved in the code

---

## 🎨 Chat UI Features

- 💬 **Real-time chat interface**
- ⚡ **Example queries** for quick start
- 🔄 **Two modes:**
  - **Send** - Standard request (wait for full response)
  - **Stream** - Streaming request (live updates)
- ⌨️ **Keyboard shortcuts:**
  - `Enter` - Send query
- 💬 **Typing indicators**
- 🎯 **Smooth animations**

---

## 📁 Project Structure

```
genai_agent_project/
├── medical_agent/
│   ├── agents/
│   │   └── crew.py           # 3 agents with delegation
│   ├── api/
│   │   └── server.py         # FastAPI server + streaming
│   ├── graph/
│   │   ├── client.py         # Graphiti client
│   │   ├── groq_client.py    # Groq LLM
│   │   └── local_embedder.py # Embeddings
│   ├── tools/
│   │   └── medical_tools.py  # 3 tools (Graph, Web, Cypher)
│   └── config.py             # Configuration
├── static/
│   └── chat.html             # Chat UI
├── logs/
│   └── tool_usage.log        # Tool logs (auto-generated)
├── data/
│   └── drugs.txt             # Medical knowledge
├── start_app.py              # Quick start script ⭐
├── test_improvements.py      # Test all 6 features
└── ingest_drugs.py           # Seed graph with data
```

---

## 🌟 Key Features

### **1. Multi-Agent System**
- 🧑‍🔬 **Clinical Researcher** - Gathers information
- 🛡️ **Safety Validator** - Checks drug interactions
- 📊 **Medical Analyst** - Synthesizes findings

### **2. Three Tools**
- 📊 **Graph Database Search** - Semantic search with Graphiti
- 🔍 **Web Search** - DuckDuckGo for latest info
- ⚡ **Cypher Query Executor** - Complex graph traversals

### **3. Streaming Responses**
- Real-time progress updates
- Live agent status
- Reduced perceived latency

### **4. Comprehensive Logging**
- Every tool call logged
- Latency measurements
- Success/failure tracking

---

## 🎯 Next Steps

1. **Test the application:**
   ```powershell
   python test_improvements.py
   ```

2. **Explore the API docs:**
   - Visit: `http://localhost:8000/docs`
   - FastAPI auto-generated Swagger UI

3. **Review the code:**
   - `ASSIGNMENT_IMPROVEMENTS.md` - Feature documentation
   - `IMPLEMENTATION_SUMMARY.md` - Complete overview
   - `ARCHITECTURE.md` - System design

4. **Customize:**
   - Add more drugs to `data/drugs.txt`
   - Create custom Cypher queries
   - Modify agent backstories in `crew.py`

---

## 📞 Support

If you encounter issues:

1. Check logs: `Get-Content logs/tool_usage.log -Tail 50`
2. Verify Neo4j is running
3. Ensure all dependencies are installed: `pip install -r requirements.txt`
4. Review error messages in the terminal

---

**✅ Ready to go! Run `python start_app.py` to get started!**
