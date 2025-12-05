from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from medical_agent.agents.crew import create_medical_crew
from medical_agent.graph.client import get_graphiti_client
from medical_agent.utils.ingestion import ingest_text
from medical_agent.utils.intelligent_router import get_router
import asyncio
import json
from pathlib import Path
import hashlib
import re

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
    """Generate cache key from query."""
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

# Mount static files for frontend
static_dir = Path(__file__).parent.parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

class QueryRequest(BaseModel):
    query: str

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
def ask_agent(request: QueryRequest):
    try:
        # Check cache first
        cache_key = get_cache_key(request.query)
        if cache_key in RESPONSE_CACHE:
            print(f"📦 Cache hit for query: {request.query[:50]}...")
            return {"response": RESPONSE_CACHE[cache_key]}
        
        # Use intelligent LLM-powered routing
        router = get_router()
        analysis = router.analyze_query(request.query)
        
        print(f"🧠 Query Analysis:")
        print(f"   Intent: {analysis.intent}")
        print(f"   Complexity: {analysis.complexity}/5")
        print(f"   Agents: {', '.join(analysis.required_agents)}")
        print(f"   Reasoning: {analysis.reasoning}")
        
        # Reject non-medical queries based on LLM analysis
        if not analysis.is_medical:
            print(f"⚠️  Non-medical query rejected (confidence: {analysis.confidence:.2f})")
            return {"response": analysis.rejection_message or 
                    "I'm a medical AI assistant. Please ask about medications, drug interactions, or medical conditions."}
        
        # Run crew with intelligent configuration
        crew = create_medical_crew(request.query, analysis)
        result = crew.kickoff()
        response_text = result.raw if hasattr(result, 'raw') else str(result)
        
        # Cache result
        RESPONSE_CACHE[cache_key] = response_text
        
        return {"response": response_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ask/stream")
async def ask_agent_stream(request: QueryRequest):
    """Stream agent responses in real-time using Server-Sent Events (SSE)."""
    import sys
    from io import StringIO
    import re
    
    async def event_generator():
        try:
            # Send initial message
            yield f"data: {json.dumps({'type': 'start', 'message': 'Agent started processing...'})}\n\n"
            
            # Create crew
            crew = create_medical_crew(request.query)
            
            # Capture stdout to stream agent thoughts in real-time
            original_stdout = sys.stdout
            captured_output = StringIO()
            sys.stdout = captured_output
            
            # Run crew in background thread
            def run_crew():
                return crew.kickoff()
            
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_crew)
                
                # Stream output line by line
                last_position = 0
                while not future.done():
                    await asyncio.sleep(0.2)  # Check every 200ms
                    
                    current_output = captured_output.getvalue()
                    if len(current_output) > last_position:
                        new_content = current_output[last_position:]
                        last_position = len(current_output)
                        
                        # Parse and stream meaningful updates
                        for line in new_content.split('\n'):
                            # Filter for important agent activity
                            if any(keyword in line for keyword in [
                                'Agent:', 'Task:', 'Thought:', 'Action:', 'Tool:', 
                                'Using Tool:', 'Observation:', 'Final Answer:', 
                                'Agent Started', 'Agent Tool Execution', 'Delegate'
                            ]):
                                # Clean ANSI codes and formatting
                                clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)
                                clean_line = re.sub(r'[│├└╭╮╯╰─]', '', clean_line).strip()
                                
                                if clean_line and len(clean_line) > 3:
                                    yield f"data: {json.dumps({'type': 'thinking', 'message': clean_line})}\n\n"
                
                # Get final result
                result = future.result()
            
            # Restore stdout
            sys.stdout = original_stdout
            
            # Send final result
            yield f"data: {json.dumps({'type': 'result', 'message': str(result)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            sys.stdout = original_stdout  # Ensure stdout is restored
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Removed /validate-formulation and /find-alternatives - use /ask instead:
# Example: POST /ask {"query": "What are the interactions between Aspirin and Warfarin?"}
# Example: POST /ask {"query": "What are alternatives to Aspirin?"}

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

@app.post("/add-document")
async def add_document(file: UploadFile = File(...)):
    try:
        content = await file.read()
        text = content.decode("utf-8")
        result = await ingest_text(text, source_name=file.filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/seed")
async def trigger_seed():
    """Seed the graph with initial data. Use ingest_drugs.py instead."""
    return {
        "message": "Please use 'python ingest_drugs.py' to seed the graph.",
        "status": "not_implemented"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
