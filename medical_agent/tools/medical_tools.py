import asyncio
from crewai.tools import BaseTool
from typing import Type, Dict, Any
from pydantic import BaseModel, Field, field_validator
from medical_agent.graph.client import get_graphiti_client
from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
from duckduckgo_search import DDGS
import hashlib
from datetime import datetime, timedelta

# Simple in-memory cache with TTL
_TOOL_CACHE: Dict[str, tuple[str, datetime]] = {}
_CACHE_TTL = timedelta(hours=1)  # Cache results for 1 hour

def _get_cache_key(tool_name: str, query: str) -> str:
    """Generate cache key from tool name and query."""
    normalized = query.lower().strip()
    return hashlib.md5(f"{tool_name}:{normalized}".encode()).hexdigest()

def _check_cache(tool_name: str, query: str) -> str | None:
    """Check if result is in cache and not expired."""
    key = _get_cache_key(tool_name, query)
    if key in _TOOL_CACHE:
        result, timestamp = _TOOL_CACHE[key]
        if datetime.now() - timestamp < _CACHE_TTL:
            return result
        else:
            del _TOOL_CACHE[key]  # Expired
    return None

def _set_cache(tool_name: str, query: str, result: str):
    """Store result in cache with timestamp."""
    key = _get_cache_key(tool_name, query)
    _TOOL_CACHE[key] = (result, datetime.now())

class SearchInput(BaseModel):
    """Input for search tools with automatic dict-to-string conversion."""
    query: str = Field(description="The search query string")
    
    @field_validator('query', mode='before')
    @classmethod
    def convert_dict_to_string(cls, v: Any) -> str:
        """Handle LLM sending schema dict instead of string value.
        
        LLM sometimes sends: {"description": "contraindications for Aspirin", "type": "str"}
        Instead of just: "contraindications for Aspirin"
        """
        if isinstance(v, dict):
            # Extract actual query from schema dict
            return v.get('description', str(v))
        return str(v)

class WebSearchTool(BaseTool):
    name: str = "Web Search"
    description: str = "Search the web for medical information not found in the graph."
    args_schema: Type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        # Check cache first
        cached = _check_cache("WebSearch", query)
        if cached:
            return f"[Cached] {cached}"
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if not results:
                    return "No web results found."
                result = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
                _set_cache("WebSearch", query, result)
                return result
        except Exception as e:
            return f"Web search failed: {e}"

class GraphDBTool(BaseTool):
    name: str = "Graph Database Search"
    description: str = "Search the internal medical knowledge graph for drugs, interactions, and conditions."
    args_schema: Type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        # Check cache first
        cached = _check_cache("GraphDB", query)
        if cached:
            return f"[Cached] {cached}"
        
        result = asyncio.run(self._async_search(query))
        if result and "error" not in result.lower():
            _set_cache("GraphDB", query, result)
        return result

    async def _async_search(self, query: str) -> str:
        client = await get_graphiti_client()
        try:
            results = await client.search_(query, config=COMBINED_HYBRID_SEARCH_RRF)
            if not results: 
                return "No info in graph."
            
            info = []
            if results.edges:
                for edge in results.edges[:3]:
                    info.append(f"Fact: {edge.fact}")
            
            if len(info) < 3 and results.nodes:
                for node in results.nodes[:2]:
                    summary = getattr(node, 'summary', getattr(node, 'description', getattr(node, 'body', '')))
                    if summary:
                        info.append(f"Entity: {node.name} - {summary[:150]}...")
            
            return "\n".join(info) if info else "No relevant graph data."
        except Exception as e:
            return f"Graph search error: {e}"
        finally:
            await client.close()

web_search_tool = WebSearchTool()
graph_db_tool = GraphDBTool()

