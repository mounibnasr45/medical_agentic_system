from typing import Iterable
from graphiti_core.embedder.client import EmbedderClient
from sentence_transformers import SentenceTransformer

# Global model cache (singleton pattern for performance)
_MODEL_CACHE = None

class LocalEmbedder(EmbedderClient):
    """
    Local embedder using sentence-transformers (runs on CPU, no API key needed).
    Uses the 'all-MiniLM-L6-v2' model which is lightweight and effective.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the local embedder.
        
        Args:
            model_name: Name of the sentence-transformers model to use.
                       Default is 'all-MiniLM-L6-v2' (384 dimensions, fast).
        """
        global _MODEL_CACHE
        if _MODEL_CACHE is None:
            print(f"Loading embedding model: {model_name} (cached for reuse)...")
            _MODEL_CACHE = SentenceTransformer(model_name)
        self.model = _MODEL_CACHE
        
    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        """
        Create embeddings for a single input.
        
        Args:
            input_data: Text string to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        print(f"DEBUG: LocalEmbedder.create called with type: {type(input_data)}")
        if isinstance(input_data, list):
             print(f"DEBUG: Input list length: {len(input_data)}")
             if len(input_data) > 0:
                 print(f"DEBUG: First item type: {type(input_data[0])}")
                 print(f"DEBUG: First item preview: {str(input_data[0])[:50]}")

        if isinstance(input_data, str):
            # Encode the text and convert to list
            embedding = self.model.encode(input_data, convert_to_numpy=True)
            return embedding.tolist()
        elif isinstance(input_data, list):
            # Handle list input (e.g. list of strings)
            # If it's a list of strings, Graphiti might be expecting a single vector 
            # if it's calling 'create' (singular).
            # Let's check if it's a list of strings or list of ints (already embedded?)
            if len(input_data) > 0 and isinstance(input_data[0], str):
                # If Graphiti passes a list of strings to 'create', it might expect 
                # a single embedding for the *combined* text?
                # Or it might be a bug in Graphiti passing a list where a string is expected.
                # Let's try joining them, which is a common fallback.
                print("DEBUG: Joining list of strings into single string")
                combined_text = " ".join(input_data)
                embedding = self.model.encode(combined_text, convert_to_numpy=True)
                return embedding.tolist()
            
            # Fallback for other list types (e.g. existing embeddings?)
            embeddings = self.model.encode(input_data, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            raise NotImplementedError(f"Input type {type(input_data)} not supported. Expected str or list[str].")
    
    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        """
        Create embeddings for multiple inputs in batch.
        
        Args:
            input_data_list: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        embeddings = self.model.encode(input_data_list, convert_to_numpy=True)
        return embeddings.tolist()
