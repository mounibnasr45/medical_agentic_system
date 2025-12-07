"""
Multi-Context Processing (MCP) for parallel information retrieval.

Executes multiple tool queries in parallel and merges results using LLM.
"""
import asyncio
import logging
import time
from typing import List, Optional
from dataclasses import dataclass
from crewai import LLM
from medical_agent.config import Config
from medical_agent.tools.medical_tools import (
    graph_db_tool, 
    cypher_query_tool, 
    web_search_tool
)
import logging

logger = logging.getLogger(__name__)

@dataclass
class ContextResult:
    """Result from a single context source."""
    source: str  # 'graph_db', 'cypher', 'web'
    content: str
    confidence: float  # 0.0 to 1.0
    latency_ms: int
    error: Optional[str] = None

@dataclass
class MCPResult:
    """Merged result from multiple contexts."""
    contexts: List[ContextResult]
    merged_content: str
    total_latency_ms: int
    sources_used: List[str]
    confidence_score: float


class MultiContextProcessor:
    """
    Processes queries across multiple contexts in parallel.
    
    Contexts:
    1. Graph DB - Structured entity relationships
    2. Cypher Query - Complex graph traversals
    3. Web Search - External knowledge
    """
    
    def __init__(self):
        # Lightweight LLM for merging contexts
        self.merger_llm = LLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=Config.GROQ_API_KEY,
            temperature=0.2,
            max_tokens=800
        )
        
    async def process_query(
        self, 
        query: str,
        contexts: List[str] = None,
        timeout: int = 15
    ) -> MCPResult:
        """
        Process query across multiple contexts in parallel.
        
        Args:
            query: User's medical query
            contexts: List of contexts to use ['graph_db', 'cypher', 'web']
                     If None, intelligently selects based on query
            timeout: Max seconds to wait for all contexts
        
        Returns:
            MCPResult with merged information
        """
        if contexts is None:
            contexts = self._select_contexts(query)
        
        print(f"🔄 MCP: Processing with contexts: {contexts}")
        
        # Create async tasks for each context
        tasks = []
        start_time = time.time()
        
        if 'graph_db' in contexts:
            tasks.append(self._query_graph_db(query))
        if 'cypher' in contexts:
            tasks.append(self._query_cypher(query))
        if 'web' in contexts:
            tasks.append(self._query_web(query))
        
        # Execute all in parallel with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            print(f"⏱️  MCP timeout after {timeout}s")
            results = []
        
        total_latency = int((time.time() - start_time) * 1000)
        
        # Filter out errors and create ContextResults
        context_results = [r for r in results if isinstance(r, ContextResult)]
        
        # Merge contexts using LLM
        merged_content = await self._merge_contexts(query, context_results)
        
        # Calculate confidence (average of all contexts)
        avg_confidence = (
            sum(r.confidence for r in context_results) / len(context_results)
            if context_results else 0.0
        )
        
        return MCPResult(
            contexts=context_results,
            merged_content=merged_content,
            total_latency_ms=total_latency,
            sources_used=[r.source for r in context_results],
            confidence_score=avg_confidence
        )
    
    async def _query_graph_db(self, query: str) -> ContextResult:
        """Query Neo4j graph database."""
        start = time.time()
        try:
            # Use async method directly
            result = await graph_db_tool._async_search(query)
            latency = int((time.time() - start) * 1000)
            
            # Determine confidence based on result quality
            confidence = 0.9 if "Fact:" in result else 0.5
            
            return ContextResult(
                source="graph_db",
                content=result,
                confidence=confidence,
                latency_ms=latency
            )
        except Exception as e:
            logger.error(f"Graph DB error: {e}")
            return ContextResult(
                source="graph_db",
                content="",
                confidence=0.0,
                latency_ms=0,
                error=str(e)
            )
    
    async def _query_cypher(self, query: str) -> ContextResult:
        """Execute Cypher query for complex traversals."""
        start = time.time()
        try:
            # Convert natural language to Cypher query intent
            cypher_query = self._generate_cypher_query(query)
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, cypher_query_tool._run, cypher_query)
            latency = int((time.time() - start) * 1000)
            
            confidence = 0.8 if result and "No matching" not in result else 0.3
            
            return ContextResult(
                source="cypher",
                content=result,
                confidence=confidence,
                latency_ms=latency
            )
        except Exception as e:
            logger.error(f"Cypher error: {e}")
            return ContextResult(
                source="cypher",
                content="",
                confidence=0.0,
                latency_ms=0,
                error=str(e)
            )
    
    async def _query_web(self, query: str) -> ContextResult:
        """Search external web sources."""
        start = time.time()
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, web_search_tool._run, query)
            latency = int((time.time() - start) * 1000)
            
            confidence = 0.7  # Web sources are less reliable
            
            return ContextResult(
                source="web",
                content=result,
                confidence=confidence,
                latency_ms=latency
            )
        except Exception as e:
            logger.error(f"Web search error: {e}")
            return ContextResult(
                source="web",
                content="",
                confidence=0.0,
                latency_ms=0,
                error=str(e)
            )
    
    def _select_contexts(self, query: str) -> List[str]:
        """Intelligently select which contexts to use based on query."""
        contexts = ['graph_db']  # Always use graph
        
        # Add Cypher for complex queries
        if any(word in query.lower() for word in ['interact', 'all', 'contraindicate', 'together', 'and']):
            contexts.append('cypher')
        
        # Add web for latest info or rare drugs
        if any(word in query.lower() for word in ['latest', 'new', 'recent', 'study', 'research']):
            contexts.append('web')
        
        return contexts
    
    def _generate_cypher_query(self, query: str) -> str:
        """Convert natural language to Cypher query intent."""
        # Simplified - use query as-is for now
        if "interact" in query.lower():
            return "Find all drug interactions"
        elif "contraindicate" in query.lower():
            return "Find all contraindications"
        else:
            return query
    
    async def _merge_contexts(
        self, 
        query: str, 
        contexts: List[ContextResult]
    ) -> str:
        """Use LLM to merge information from multiple contexts."""
        if not contexts:
            return "No information found from any source."
        
        # Build context summary
        context_summary = "\n\n".join([
            f"**Source: {ctx.source.upper()}** (Confidence: {ctx.confidence:.0%}, Latency: {ctx.latency_ms}ms)\n{ctx.content}"
            for ctx in contexts if ctx.content
        ])
        
        if not context_summary:
            return "No useful information retrieved."
        
        # Merge using LLM
        merge_prompt = f"""You are a medical information synthesizer.

User Query: "{query}"

Information from multiple sources (retrieved in parallel):
{context_summary}

Task: Synthesize the above information into a coherent, accurate answer.
- Cross-validate facts across sources
- Note if sources disagree
- Prioritize high-confidence sources
- Cite sources in your answer
- Keep response concise and medically accurate

Synthesized Answer:"""

        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: self.merger_llm.call([{"role": "user", "content": merge_prompt}])
            )
            return response
        except Exception as e:
            logger.error(f"LLM merge error: {e}")
            # Fallback: just concatenate
            return f"Multiple sources retrieved:\n\n{context_summary}"


# Global instance
_mcp_instance = None

def get_mcp_processor() -> MultiContextProcessor:
    """Get or create global MCP processor."""
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = MultiContextProcessor()
    return _mcp_instance
