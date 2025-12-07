"""
Chain of Thought (CoT) Reasoning Module

Implements explicit step-by-step reasoning for complex medical queries.
Uses LLM to break down complex problems into logical steps.
"""

from typing import List, Dict, Any
from crewai import LLM
from medical_agent.config import Config


class ChainOfThoughtProcessor:
    """
    Implements Chain of Thought reasoning for complex medical queries.
    
    CoT improves accuracy on multi-step reasoning tasks by:
    1. Breaking down complex questions into steps
    2. Solving each step explicitly
    3. Combining results for final answer
    """
    
    def __init__(self):
        """Initialize CoT processor with powerful LLM."""
        self.llm = LLM(
            model="groq/llama-3.3-70b-versatile",
            api_key=Config.GROQ_API_KEY,
            temperature=0.2,  # Slightly higher for creative reasoning
            max_tokens=2000  # Allow longer reasoning chains
        )
    
    def process_with_cot(
        self, 
        query: str, 
        reasoning_steps: List[str],
        research_findings: str = ""
    ) -> Dict[str, Any]:
        """
        Apply Chain of Thought reasoning to a query.
        
        Args:
            query: User's medical query
            reasoning_steps: List of reasoning steps from router
            research_findings: Data gathered by research agent
            
        Returns:
            Dict with 'reasoning_chain' and 'final_answer'
        """
        
        prompt = f"""You are a medical AI assistant using Chain of Thought reasoning.

**USER QUERY:** "{query}"

**REASONING STEPS TO FOLLOW:**
{self._format_steps(reasoning_steps)}

**AVAILABLE RESEARCH DATA:**
{research_findings if research_findings else "No research data provided yet."}

**INSTRUCTIONS:**
Think through this problem step-by-step following the reasoning steps above.
For each step:
1. State what you're analyzing
2. Show your reasoning
3. State your conclusion for that step

Format your response as:

**Step 1: [Step name]**
Reasoning: [Your detailed reasoning]
Conclusion: [What you concluded]

**Step 2: [Step name]**
Reasoning: [Your detailed reasoning]
Conclusion: [What you concluded]

[Continue for all steps...]

**FINAL ANSWER:**
[Synthesized answer based on all steps]

**CONFIDENCE LEVEL:** [High/Medium/Low]
**REASONING QUALITY:** [Strong/Adequate/Weak] - explain why

Begin your step-by-step reasoning:"""

        try:
            response = self.llm.call([{"role": "user", "content": prompt}])
            
            # Parse response into structured format
            return self._parse_cot_response(response, reasoning_steps)
            
        except Exception as e:
            print(f"⚠️  CoT reasoning failed: {e}")
            return {
                "reasoning_chain": [],
                "final_answer": research_findings,
                "confidence": "low",
                "reasoning_quality": "weak",
                "error": str(e)
            }
    
    def _format_steps(self, steps: List[str]) -> str:
        """Format reasoning steps as numbered list."""
        return "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
    
    def _parse_cot_response(self, response: str, expected_steps: List[str]) -> Dict[str, Any]:
        """Parse LLM's CoT response into structured format."""
        
        # Extract reasoning chain
        reasoning_chain = []
        current_step = None
        current_reasoning = []
        current_conclusion = None
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            
            # Detect step headers
            if line.startswith('**Step') and ':**' in line:
                # Save previous step if exists
                if current_step is not None:
                    reasoning_chain.append({
                        "step": current_step,
                        "reasoning": "\n".join(current_reasoning).strip(),
                        "conclusion": current_conclusion or ""
                    })
                
                # Start new step
                current_step = line.split(':**')[1].strip() if ':**' in line else line
                current_reasoning = []
                current_conclusion = None
                
            elif line.startswith('Reasoning:'):
                current_reasoning.append(line.replace('Reasoning:', '').strip())
            elif line.startswith('Conclusion:'):
                current_conclusion = line.replace('Conclusion:', '').strip()
            elif current_step is not None and line and not line.startswith('**'):
                current_reasoning.append(line)
        
        # Save last step
        if current_step is not None:
            reasoning_chain.append({
                "step": current_step,
                "reasoning": "\n".join(current_reasoning).strip(),
                "conclusion": current_conclusion or ""
            })
        
        # Extract final answer
        final_answer = ""
        if "**FINAL ANSWER:**" in response:
            parts = response.split("**FINAL ANSWER:**")
            if len(parts) > 1:
                answer_section = parts[1]
                # Take until next ** marker or end
                if "**" in answer_section:
                    final_answer = answer_section.split("**")[0].strip()
                else:
                    final_answer = answer_section.strip()
        
        # Extract confidence and quality
        confidence = "medium"
        reasoning_quality = "adequate"
        
        if "**CONFIDENCE LEVEL:**" in response:
            conf_line = [l for l in lines if "CONFIDENCE LEVEL" in l]
            if conf_line:
                if "high" in conf_line[0].lower():
                    confidence = "high"
                elif "low" in conf_line[0].lower():
                    confidence = "low"
        
        if "**REASONING QUALITY:**" in response:
            qual_line = [l for l in lines if "REASONING QUALITY" in l]
            if qual_line:
                if "strong" in qual_line[0].lower():
                    reasoning_quality = "strong"
                elif "weak" in qual_line[0].lower():
                    reasoning_quality = "weak"
        
        return {
            "reasoning_chain": reasoning_chain,
            "final_answer": final_answer,
            "confidence": confidence,
            "reasoning_quality": reasoning_quality,
            "full_response": response
        }
    
    def format_cot_for_display(self, cot_result: Dict[str, Any]) -> str:
        """Format CoT results for user-friendly display."""
        
        output = ["## 🧠 Chain of Thought Reasoning\n"]
        
        # Show each reasoning step
        for i, step in enumerate(cot_result.get("reasoning_chain", []), 1):
            output.append(f"**Step {i}: {step['step']}**")
            if step.get('reasoning'):
                output.append(f"*Reasoning:* {step['reasoning']}")
            if step.get('conclusion'):
                output.append(f"*Conclusion:* {step['conclusion']}")
            output.append("")  # Blank line
        
        # Show final answer
        output.append("---")
        output.append("## ✅ Final Answer\n")
        output.append(cot_result.get("final_answer", "No answer generated"))
        output.append("")
        
        # Show confidence
        confidence = cot_result.get("confidence", "medium")
        quality = cot_result.get("reasoning_quality", "adequate")
        
        output.append(f"**Confidence:** {confidence.upper()} | **Reasoning Quality:** {quality.upper()}")
        
        return "\n".join(output)


# Global CoT processor instance
_cot_processor = None

def get_cot_processor() -> ChainOfThoughtProcessor:
    """Get or create global CoT processor instance."""
    global _cot_processor
    if _cot_processor is None:
        _cot_processor = ChainOfThoughtProcessor()
    return _cot_processor
