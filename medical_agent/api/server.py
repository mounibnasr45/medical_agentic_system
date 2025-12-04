from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from medical_agent.agents.crew import create_medical_crew
from medical_agent.graph.seed import seed_graph
from medical_agent.graph.client import get_graphiti_client
from medical_agent.utils.ingestion import ingest_text
import asyncio

app = FastAPI(title="Medical Agent API")

class QueryRequest(BaseModel):
    query: str

@app.get("/")
def read_root():
    return {"message": "Medical Agent API is running."}

@app.post("/ask")
def ask_agent(request: QueryRequest):
    try:
        crew = create_medical_crew(request.query)
        result = crew.kickoff()
        return {"response": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    try:
        await seed_graph()
        return {"message": "Graph seeded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
