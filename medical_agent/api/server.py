from fastapi import FastAPI, HTTPException, UploadFile, File, Header
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from medical_agent.agents.crew import create_medical_crew
from medical_agent.graph.client import get_graphiti_client
from medical_agent.utils.intelligent_router import get_router
from medical_agent.utils.memory_manager import MemoryManager
from medical_agent.utils.mcp_processor import get_mcp_processor
from medical_agent.utils.chain_of_thought import get_cot_processor
import asyncio
import json
from pathlib import Path
import hashlib
import re
from typing import Optional

app = FastAPI(title="Medical Agent API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== OPTIMIZATION: Response Cache ======
# Cache complete crew results to avoid re-running identical queries
RESPONSE_CACHE = {}
CACHE_TTL = 3600  # 1 hour

def get_cache_key(query: str) -> str:
    """
    Generate normalized cache key from query.
    Normalizes word order to catch semantic duplicates.
    Example: 'Aspirin interaction' and 'interaction Aspirin' → same key
    """
    # Normalize: lowercase, sort words, remove extra spaces
    words = sorted(query.lower().strip().split())
    normalized = ' '.join(words)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]  # Short hash

# Mount static files for frontend
static_dir = Path(__file__).parent.parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    use_mcp: Optional[bool] = None  # Auto-detect if None
    stream: Optional[bool] = False  # Enable streaming

@app.get("/")
def read_root():
    return {"message": "Medical Agent API is running. Visit /chat for the web interface."}

@app.get("/chat", response_class=HTMLResponse)
async def chat_ui():
    """Serve the chat UI."""
    html_path = Path(__file__).parent.parent.parent / "static" / "chat.html"
    if html_path.exists():
        return html_path.read_text(encoding='utf-8')
    return "<h1>Chat UI not found. Run setup to create it.</h1>"

@app.post("/ask")
async def ask_agent(request: QueryRequest):
    """
    Unified intelligent medical AI endpoint with all features:
    - Multi-agent collaboration (CrewAI)
    - Multi-Context Processing (MCP) for parallel tool execution
    - Chain of Thought (CoT) reasoning for complex queries
    - Conversation memory management
    - Smart caching and routing
    
    Args:
        query: Medical question
        session_id: Conversation session ID (optional, auto-created)
        use_mcp: Force MCP mode (auto-detect if None)
        stream: Enable SSE streaming (not yet implemented)
    
    Returns:
        Intelligent response with metadata
    """
    try:
        # Get or create memory session
        memory = MemoryManager.get_session(request.session_id)
        
        # Use intelligent LLM-powered routing
        router = get_router()
        analysis = router.analyze_query(request.query)
        
        print(f"🧠 Query Analysis:")
        print(f"   Intent: {analysis.intent}")
        print(f"   Complexity: {analysis.complexity}/5")
        print(f"   Agents: {', '.join(analysis.required_agents)}")
        print(f"   Use CoT: {analysis.use_chain_of_thought}")
        print(f"   Session: {memory.session_id}")
        
        # Reject non-medical queries
        if not analysis.is_medical:
            print(f"⚠️  Non-medical query rejected (confidence: {analysis.confidence:.2f})")
            rejection_msg = analysis.rejection_message or \
                    "I'm a medical AI assistant. Please ask about medications, drug interactions, or medical conditions."
            memory.add_user_message(request.query)
            memory.add_ai_message(rejection_msg)
            return {
                "response": rejection_msg,
                "session_id": memory.session_id,
                "from_cache": False,
                "analysis": {"is_medical": False, "reason": analysis.reasoning}
            }
        
        # Determine processing mode (MCP vs Traditional Crew)
        use_mcp = request.use_mcp
        if use_mcp is None:
            # Auto-detect: Use MCP for complex queries with multiple tools
            use_mcp = (
                analysis.complexity >= 3 and 
                len(analysis.suggested_tools) >= 2 and
                'interaction' in analysis.intent
            )
        
        # Get conversation context
        context = memory.get_context_for_query(request.query)
        
        # Check cache
        cache_mode = "mcp" if use_mcp else "crew"
        cache_key = get_cache_key(f"{cache_mode}:{memory.session_id}:{request.query}")
        
        if cache_key in RESPONSE_CACHE:
            print(f"📦 Cache hit ({cache_mode} mode)")
            cached_response = RESPONSE_CACHE[cache_key]
            memory.add_user_message(request.query)
            memory.add_ai_message(cached_response)
            return {
                "response": cached_response,
                "session_id": memory.session_id,
                "from_cache": True,
                "processing_mode": cache_mode.upper(),
                "analysis": {
                    "intent": analysis.intent,
                    "complexity": analysis.complexity
                }
            }
        
        # Add to memory
        memory.add_user_message(request.query)
        
        # === PROCESSING MODE SELECTION ===
        
        if use_mcp:
            # === MCP MODE: Parallel Tool Execution ===
            print(f"🔄 Using Multi-Context Processing (parallel)")
            
            mcp = get_mcp_processor()
            contexts = None  # Auto-select
            if analysis.complexity >= 4:
                contexts = ['graph_db', 'cypher', 'web']  # All tools for very complex
            
            mcp_result = await mcp.process_query(
                query=request.query,
                contexts=contexts,
                timeout=20
            )
            
            response_text = mcp_result.merged_content
            
            # Apply CoT if needed
            if analysis.use_chain_of_thought and analysis.cot_reasoning_steps:
                print(f"🧠 Applying Chain of Thought reasoning...")
                cot_processor = get_cot_processor()
                cot_result = cot_processor.process_with_cot(
                    query=request.query,
                    reasoning_steps=analysis.cot_reasoning_steps,
                    research_findings=response_text
                )
                cot_formatted = cot_processor.format_cot_for_display(cot_result)
                response_text = f"{cot_formatted}\n\n---\n\n## 📋 Research Details\n\n{response_text}"
            
            # Add to memory and cache
            memory.add_ai_message(response_text)
            RESPONSE_CACHE[cache_key] = response_text
            
            return {
                "response": response_text,
                "session_id": memory.session_id,
                "from_cache": False,
                "processing_mode": "MCP",
                "latency_ms": mcp_result.total_latency_ms,
                "sources_used": mcp_result.sources_used,
                "confidence": mcp_result.confidence_score,
                "analysis": {
                    "intent": analysis.intent,
                    "complexity": analysis.complexity,
                    "use_cot": analysis.use_chain_of_thought
                }
            }
        
        else:
            # === TRADITIONAL CREW MODE: Sequential Multi-Agent ===
            print(f"🤖 Using Traditional Crew (sequential multi-agent)")
            
            # Prepare query with context
            query_with_context = request.query
            if context:
                query_with_context = f"{context}\n\n## Current Query:\n{request.query}"
            
            # Run crew
            crew = create_medical_crew(query_with_context, analysis)
            result = crew.kickoff()
            response_text = result.raw if hasattr(result, 'raw') else str(result)
            
            # Apply CoT if needed
            if analysis.use_chain_of_thought and analysis.cot_reasoning_steps:
                print(f"🧠 Applying Chain of Thought reasoning...")
                cot_processor = get_cot_processor()
                cot_result = cot_processor.process_with_cot(
                    query=request.query,
                    reasoning_steps=analysis.cot_reasoning_steps,
                    research_findings=response_text
                )
                cot_formatted = cot_processor.format_cot_for_display(cot_result)
                response_text = f"{cot_formatted}\n\n---\n\n## 📋 Detailed Research Findings\n\n{response_text}"
            
            # Add to memory and cache
            memory.add_ai_message(response_text)
            RESPONSE_CACHE[cache_key] = response_text
            
            stats = memory.get_memory_stats()
            
            return {
                "response": response_text,
                "session_id": memory.session_id,
                "from_cache": False,
                "processing_mode": "CREW",
                "memory_stats": stats,
                "analysis": {
                    "intent": analysis.intent,
                    "complexity": analysis.complexity,
                    "use_cot": analysis.use_chain_of_thought,
                    "agents_used": analysis.required_agents
                }
            }
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/graph-info")
async def graph_info():
    client = await get_graphiti_client()
    try:
        # Try to get stats using a simpler method or fallback
        # If client.driver is a Neo4j Driver object, we can try to use it directly.
        # However, if 'AsyncSession' error occurs, it might be due to how we access it.
        
        # Let's try a simple connectivity check first
        # await client.driver.verify_connectivity() # This method might not exist on the wrapper
        
        # Try to execute a simple query if execute_query is available (Neo4j 5.x driver)
        if hasattr(client.driver, 'execute_query'):
             await client.driver.execute_query("RETURN 1")
        
        return {
            "status": "connected",
            "message": "Graphiti client connected successfully."
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}
    finally:
        await client.close()


# ====== Memory Management Endpoints ======

@app.get("/sessions")
def list_sessions():
    """List all conversation sessions."""
    try:
        sessions = MemoryManager.list_sessions()
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/history")
def get_session_history(session_id: str, limit: int = 20):
    """Get conversation history for a specific session."""
    try:
        memory = MemoryManager.get_session(session_id)
        history = memory.get_conversation_history(limit=limit)
        stats = memory.get_memory_stats()
        return {
            "session_id": session_id,
            "history": history,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}/summary")
def get_session_summary(session_id: str):
    """Get summary of a conversation session."""
    try:
        summary = MemoryManager.get_session_summary(session_id)
        memory = MemoryManager.get_session(session_id)
        stats = memory.get_memory_stats()
        return {
            "session_id": session_id,
            "summary": summary,
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    """Delete a conversation session."""
    try:
        MemoryManager.delete_session(session_id)
        return {"message": f"Session {session_id} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sessions/new")
def create_new_session():
    """Create a new conversation session."""
    try:
        memory = MemoryManager.get_session()
        return {
            "session_id": memory.session_id,
            "message": "New session created"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
