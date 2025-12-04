import json
import re
import asyncio
from typing import List, Dict, Any
from groq import AsyncGroq
from graphiti_core.prompts.models import Message
from graphiti_core.llm_client import LLMClient, LLMConfig

class GroqClient(LLMClient):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        config = LLMConfig(api_key=api_key, model=model)
        super().__init__(config)
        self.client = AsyncGroq(api_key=api_key)
        self.model = model

    async def _generate_response(
        self, 
        messages: List[Message], 
        response_model: Any = None,
        max_tokens: int = 8192,
        model_size: Any = None
    ) -> Dict[str, Any]:
        """Abstract method implementation required by LLMClient base class."""
        # Convert Graphiti messages to Groq format
        groq_messages = [
            {"role": msg.role, "content": msg.content} 
            for msg in messages
        ]
        
        kwargs = {
            "model": self.model,
            "messages": groq_messages,
            "temperature": 0.1,
            "max_tokens": max_tokens
        }

        # If a response model is expected, enforce JSON mode if supported
        if response_model:
            kwargs["response_format"] = {"type": "json_object"}

        max_retries = 15
        base_delay = 5.0

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                
                content = response.choices[0].message.content
                
                # If response_model is provided, we must parse the JSON content
                if response_model:
                    try:
                        # Clean markdown code blocks if present (e.g. ```json ... ```)
                        cleaned_content = content.strip()
                        # Regex to extract content between ```json and ``` or just ``` and ```
                        json_match = re.search(r"```(?:json)?\s*(.*)\s*```", cleaned_content, re.DOTALL)
                        if json_match:
                            cleaned_content = json_match.group(1)
                        
                        parsed_json = json.loads(cleaned_content)
                        
                        # DEBUG: Log keys to see if edges are being returned
                        if isinstance(parsed_json, dict):
                            keys = list(parsed_json.keys())
                            # print(f"DEBUG: Groq response keys: {keys}")
                            if 'edges' in keys and not parsed_json['edges']:
                                print("DEBUG: Warning - Model returned empty 'edges' list.")
                        
                        return parsed_json
                    except Exception as e:
                        print(f"Error parsing JSON from Groq response: {e}")
                        print(f"Raw content: {content}")
                        # Fallback: try to return as is, though it might fail validation
                        pass

                return {
                    "content": content,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            except Exception as e:
                error_str = str(e)
                # Check for rate limit error (429)
                if "429" in error_str or "Rate limit" in error_str:
                    wait_time = base_delay * (1.5 ** attempt) # Exponential backoff
                    
                    # Try to parse specific wait time from error message
                    # Message example: "Please try again in 2.5s."
                    try:
                        match = re.search(r"try again in (\d+(\.\d+)?)s", error_str)
                        if match:
                            wait_time = float(match.group(1)) + 2.0 # Add 2s buffer
                    except:
                        pass
                    
                    # Cap wait time to avoid waiting too long (e.g. 60s)
                    wait_time = min(wait_time, 60.0)

                    if attempt < max_retries - 1:
                        print(f"Rate limit hit. Retrying in {wait_time:.2f}s... (Attempt {attempt+1}/{max_retries})")
                        await asyncio.sleep(wait_time)
                        continue
                
                print(f"Error calling Groq API: {e}")
                if attempt == max_retries - 1:
                    raise