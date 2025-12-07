import asyncio
import logging
from crewai.tools import BaseTool
from typing import Type, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from medical_agent.graph.client import get_graphiti_client
from graphiti_core.search.search_config_recipes import COMBINED_HYBRID_SEARCH_RRF
from duckduckgo_search import DDGS
import hashlib
from datetime import datetime, timedelta
from neo4j import GraphDatabase
from medical_agent.config import Config
from groq import Groq

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        logger.info(f"Web Search - Query: {query}")
        
        # Check cache first
        cached = _check_cache("WebSearch", query)
        if cached:
            logger.info("Web Search - Cache Hit")
            return f"[Cached] {cached}"
        
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                if not results:
                    logger.warning("Web Search - No results found")
                    return "No web results found."
                result = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
                _set_cache("WebSearch", query, result)
                logger.info(f"Web Search - Success ({len(results)} results)")
                return result
        except Exception as e:
            logger.error(f"Web Search - Error: {e}")
            return f"Web search failed: {e}"

class GraphDBTool(BaseTool):
    name: str = "Graph Database Search"
    description: str = "Search the internal medical knowledge graph for drugs, interactions, and conditions."
    args_schema: Type[BaseModel] = SearchInput

    def _run(self, query: str) -> str:
        logger.info(f"Graph DB Search - Query: {query}")
        
        # Check cache first
        cached = _check_cache("GraphDB", query)
        if cached:
            logger.info("Graph DB Search - Cache Hit")
            return f"[Cached] {cached}"
        
        # Handle async context properly
        try:
            loop = asyncio.get_running_loop()
            # In async context - need to handle differently
            import nest_asyncio
            nest_asyncio.apply()
            result = asyncio.run(self._async_search(query))
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            result = asyncio.run(self._async_search(query))
        
        if result and "error" not in result.lower():
            _set_cache("GraphDB", query, result)
            logger.info("Graph DB Search - Success")
        else:
            logger.warning("Graph DB Search - No results")
        
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

class CypherQueryTool(BaseTool):
    name: str = "Cypher Query Executor"
    description: str = """Execute custom Cypher queries for complex graph traversals.
    Use this for:
    - Multi-hop drug interactions (e.g., drug A -> drug B -> drug C)
    - Finding all drugs contraindicated in a condition
    - Complex relationship patterns
    Examples:
    - 'Find all drugs that interact with Warfarin'
    - 'List contraindications for bleeding disorder patients'
    """
    args_schema: Type[BaseModel] = SearchInput
    _driver: Optional[Any] = None  # Private field for Neo4j driver
    _llm_client: Optional[Any] = None # Private field for LLM client
    
    def __init__(self):
        super().__init__()
        # Initialize driver on first use (lazy loading)
    
    def _get_driver(self):
        """Lazy load Neo4j driver."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                Config.NEO4J_URI,
                auth=(Config.NEO4J_USER, Config.NEO4J_PASSWORD)
            )
        return self._driver

    def _get_llm_client(self):
        """Lazy load Groq client."""
        if self._llm_client is None:
            self._llm_client = Groq(api_key=Config.GROQ_API_KEY)
        return self._llm_client
    
    def _run(self, query: str) -> str:
        logger.info(f"Cypher Query - Query: {query}")
        
        # Convert natural language to Cypher
        cypher_query = self._nl_to_cypher(query)
        logger.info(f"Cypher Query - Generated: {cypher_query}")
        
        try:
            driver = self._get_driver()
            with driver.session() as session:
                result = session.run(cypher_query)
                records = [dict(record) for record in result]
                
                if not records:
                    logger.warning("Cypher Query - No results")
                    return "No matching data found in graph."
                
                # Format results
                formatted = self._format_results(records)
                logger.info(f"Cypher Query - Success ({len(records)} records)")
                return formatted
                
        except Exception as e:
            logger.error(f"Cypher Query - Error: {e}")
            return f"Cypher query error: {e}"
    
    def _nl_to_cypher(self, query: str) -> str:
        """Convert natural language to Cypher query using Groq LLM."""
        try:
            client = self._get_llm_client()
            
            schema_desc = """
            Nodes: 
             - Entity (properties: name, summary)
             - Episodic (properties: content, source)
             - Community (properties: name, summary)

            Relationships:
             - (:Entity)-[:RELATES_TO {fact: "..."}]->(:Entity)
             - (:Episodic)-[:MENTIONS]->(:Entity)
            """
            
            prompt = f"""
            You are an expert Neo4j Cypher query generator.
            
            Database Schema:
            {schema_desc}
            
            Task: Generate a Cypher query for: "{query}"
            
            Rules:
            1. Return ONLY the Cypher query. No markdown, no explanations.
            2. Use case-insensitive matching: toLower(n.name) CONTAINS toLower('term').
            3. Search 'name' and 'summary' properties of Entity nodes.
            4. For "alternatives" or "similar", look for shared properties or relationships in the summary.
            5. Always LIMIT results to 20.
            6. Do not use procedures like apoc.* or db.*.
            7. CRITICAL: If using UNION, you MUST use aliases to ensure identical column names across all parts (e.g. RETURN n.name AS Name, n.summary AS Info).
            8. When looking for relationships (interactions, contraindications), check the 'fact' property on RELATES_TO edges.
            9. ALWAYS use DISTINCT in your RETURN clause to prevent duplicate rows (e.g. RETURN DISTINCT ...).
            10. IMPORTANT: Do NOT put conditions inside the relationship pattern like [:RELATES_TO {{fact: ...}}]. Instead, use the WHERE clause: MATCH ...-[r:RELATES_TO]-... WHERE toLower(r.fact) CONTAINS ...
            """
            
            completion = client.chat.completions.create(
                model=Config.GROQ_MODEL_NAME,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that writes Cypher queries."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            cypher = completion.choices[0].message.content.strip()
            
            # Clean up markdown if present
            if cypher.startswith("```"):
                cypher = cypher.replace("```cypher", "").replace("```", "").strip()
                
            return cypher
            
        except Exception as e:
            logger.error(f"LLM Cypher Generation Error: {e}")
            # Fallback to a safe generic query
            return f"MATCH (n:Entity) WHERE toLower(n.name) CONTAINS toLower('{query}') RETURN DISTINCT n LIMIT 10"

    def _format_results(self, records: list) -> str:
        """Format Cypher query results into a readable string."""
        if not records:
            return "No results found."
            
        # Deduplicate records
        unique_records = []
        seen = set()
        
        for record in records:
            # Create a hashable representation of the record
            # Sort keys to ensure consistent ordering
            # Convert values to string to handle non-hashable types if any
            record_tuple = tuple(sorted((k, str(v)) for k, v in record.items()))
            if record_tuple not in seen:
                seen.add(record_tuple)
                unique_records.append(record)
        
        formatted = []
        for i, record in enumerate(unique_records, 1):
            formatted.append(f"Result {i}:")
            for key, value in record.items():
                formatted.append(f"  - {key}: {value}")
            formatted.append("")
        return "\n".join(formatted)
    
    def __del__(self):
        """Clean up Neo4j driver on deletion."""
        if self._driver is not None:
            try:
                self._driver.close()
            except:
                pass

web_search_tool = WebSearchTool()
graph_db_tool = GraphDBTool()
cypher_query_tool = CypherQueryTool()

