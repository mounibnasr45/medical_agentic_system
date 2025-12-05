"""
Intelligent LLM-powered query routing and optimization.

This module uses LLM reasoning to:
1. Classify query medical relevance and intent
2. Determine optimal agent configuration
3. Set dynamic iteration limits based on complexity
4. Enable semantic caching for similar queries
"""

import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from crewai import LLM
from medical_agent.config import Config
import numpy as np

@dataclass
class QueryAnalysis:
    """Result of intelligent query analysis."""
    is_medical: bool
    confidence: float
    intent: str  # 'drug_info', 'interaction', 'contraindication', 'general_medical', 'non_medical'
    complexity: int  # 1-5 scale
    required_agents: List[str]  # ['researcher', 'validator', 'analyst']
    max_iterations: Dict[str, int]  # Agent-specific iteration limits
    reasoning: str  # LLM's reasoning for decisions
    suggested_tools: List[str]  # Recommended tools for this query
    rejection_message: Optional[str]  # If query should be rejected


class IntelligentRouter:
    """LLM-powered intelligent query routing system."""
    
    def __init__(self):
        """Initialize router with lightweight LLM for fast analysis."""
        # Use Groq for fast routing decisions (70B model for smart reasoning)
        self.routing_llm = LLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=Config.GROQ_API_KEY,
            temperature=0.0,  # Deterministic routing decisions
            max_tokens=500  # Keep routing fast
        )
        
        # Semantic cache for embeddings (if available)
        self.semantic_cache = {}
        self.cache_threshold = 0.92  # Cosine similarity threshold
        
    def analyze_query(self, query: str) -> QueryAnalysis:
        """
        Use LLM to intelligently analyze query and determine optimal routing.
        
        This is the AI senior's approach - let the LLM reason about the query
        instead of using brittle keyword matching.
        """
        
        prompt = f"""You are an expert medical AI system architect. Analyze this user query and determine the optimal agent configuration.

USER QUERY: "{query}"

Analyze the query and respond with ONLY valid JSON (no markdown, no explanation):

{{
  "is_medical": true/false,
  "confidence": 0.0-1.0,
  "intent": "drug_info|interaction|contraindication|side_effects|dosage|general_medical|non_medical",
  "complexity": 1-5,
  "required_agents": ["researcher", "validator", "analyst"],
  "max_iterations": {{"researcher": 1-4, "validator": 1-3, "analyst": 1-2}},
  "reasoning": "Brief explanation of your decisions",
  "suggested_tools": ["graph_db", "cypher", "web_search"],
  "rejection_message": "Message if non-medical, else null"
}}

ANALYSIS GUIDELINES:

**Medical Relevance (is_medical):**
- TRUE: Questions about drugs, medications, medical conditions, symptoms, treatments
- FALSE: Greetings, random text, off-topic questions, tests

**Intent Classification:**
- drug_info: General drug information (what is X, how does X work)
- interaction: Drug-drug or drug-condition interactions
- contraindication: When NOT to use a drug
- side_effects: Adverse effects, safety concerns
- dosage: Dosing information, administration
- general_medical: Broad medical questions (disease management, symptoms)
- non_medical: Not related to medicine

**Complexity (1-5 scale):**
- 1: Simple definition ("what is aspirin")
- 2: Single-drug information request
- 3: Drug interactions or contraindications (2 entities)
- 4: Multi-drug analysis or complex conditions
- 5: Comprehensive treatment plans, multiple interacting factors

**Required Agents:**
- Complexity 1-2: ["researcher"] only
- Complexity 3 + (interaction OR contraindication): ["researcher", "validator"]
- Complexity 4-5 OR comprehensive request: ["researcher", "validator", "analyst"]

**Max Iterations (allow tool diversity):**
- researcher: complexity 1-2 → 3 iterations (try 2-3 different tools), complexity 3 → 4 iterations, complexity 4-5 → 5 iterations
- validator: complexity 1-2 → 2 iterations, complexity 3+ → 3 iterations
- analyst: always 1 iteration (synthesis, no tools)

**CRITICAL: Each iteration should try a DIFFERENT tool unless previous tool gave useful partial results**

**Suggested Tools (in priority order):**
- graph_db: For known drugs/conditions in knowledge graph
- cypher: For complex multi-hop queries (interactions, contraindications)
- web_search: For latest info or rare drugs not in graph

**Rejection Message:**
- If non-medical: Polite message explaining you handle medical queries only
- If medical: null

Respond with ONLY the JSON object, nothing else."""

        try:
            # Get LLM analysis
            response = self.routing_llm.call([{"role": "user", "content": prompt}])
            
            # Parse response (remove markdown if present)
            response_text = response.strip()
            if response_text.startswith("```"):
                # Extract JSON from markdown code block
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            analysis_dict = json.loads(response_text)
            
            # Convert to dataclass
            return QueryAnalysis(
                is_medical=analysis_dict["is_medical"],
                confidence=analysis_dict["confidence"],
                intent=analysis_dict["intent"],
                complexity=analysis_dict["complexity"],
                required_agents=analysis_dict["required_agents"],
                max_iterations=analysis_dict["max_iterations"],
                reasoning=analysis_dict["reasoning"],
                suggested_tools=analysis_dict["suggested_tools"],
                rejection_message=analysis_dict.get("rejection_message")
            )
            
        except Exception as e:
            # Fallback to safe defaults if LLM fails
            print(f"⚠️  Router LLM failed: {e}, using safe defaults")
            return self._fallback_analysis(query)
    
    def _fallback_analysis(self, query: str) -> QueryAnalysis:
        """Safe fallback if LLM routing fails."""
        # Conservative approach - assume it's medical and needs all agents
        return QueryAnalysis(
            is_medical=True,
            confidence=0.5,
            intent="general_medical",
            complexity=3,
            required_agents=["researcher", "validator", "analyst"],
            max_iterations={"researcher": 3, "validator": 2, "analyst": 1},
            reasoning="Fallback routing due to LLM error - using conservative defaults",
            suggested_tools=["graph_db", "cypher", "web_search"],
            rejection_message=None
        )
    
    def check_semantic_cache(self, query: str, embedding: Optional[np.ndarray] = None) -> Optional[str]:
        """
        Check if semantically similar query exists in cache.
        
        This is smarter than exact match - catches rephrased questions.
        Example: "aspirin side effects" and "what are adverse effects of aspirin" 
        would be cache hits despite different wording.
        """
        if not embedding or not self.semantic_cache:
            return None
        
        # Find most similar cached query
        max_similarity = 0
        best_match = None
        
        for cached_query, (cached_embedding, cached_response) in self.semantic_cache.items():
            similarity = self._cosine_similarity(embedding, cached_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
                best_match = cached_response
        
        if max_similarity >= self.cache_threshold:
            print(f"📦 Semantic cache hit! Similarity: {max_similarity:.3f}")
            return best_match
        
        return None
    
    def add_to_semantic_cache(self, query: str, embedding: np.ndarray, response: str):
        """Add query-response pair to semantic cache."""
        self.semantic_cache[query] = (embedding, response)
        
        # Limit cache size (keep 100 most recent)
        if len(self.semantic_cache) > 100:
            # Remove oldest entry
            oldest_key = list(self.semantic_cache.keys())[0]
            del self.semantic_cache[oldest_key]
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))


# Global router instance (singleton)
_router_instance = None

def get_router() -> IntelligentRouter:
    """Get or create global router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = IntelligentRouter()
    return _router_instance
