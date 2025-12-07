"""
Memory Manager for Medical Chatbot using LangChain
Provides conversation history and context using in-memory storage
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import hashlib

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage
from langchain_groq import ChatGroq
from medical_agent.config import Config


class MedicalConversationMemory:
    """
    Conversation memory for medical chatbot using LangChain.
    Features:
    - Session-based conversation history (in-memory)
    - Context-aware memory retrieval
    - Automatic summarization for long conversations
    """
    
    def __init__(self, session_id: str = None, max_messages: int = 20):
        self.session_id = session_id or self._generate_session_id()
        self.max_messages = max_messages
        
        # Initialize simple in-memory chat history
        self.chat_history = ChatMessageHistory()
        
        # Initialize LLM for summarization
        self.llm = ChatGroq(
            api_key=Config.GROQ_API_KEY,
            model_name="llama-3.3-70b-versatile",
            temperature=0.0
        )
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:16]
    
    def add_user_message(self, message: str):
        """Add user message to memory."""
        self.chat_history.add_user_message(message)
    
    def add_ai_message(self, message: str):
        """Add AI response to memory."""
        self.chat_history.add_message(AIMessage(content=message))
    
    def get_conversation_history(self, limit: int = None) -> List[Dict[str, str]]:
        """Get formatted conversation history."""
        messages = self.chat_history.messages
        if limit:
            messages = messages[-limit:]
        
        history = []
        for msg in messages:
            if msg.type == "human":
                history.append({"role": "user", "content": msg.content})
            elif msg.type == "ai":
                history.append({"role": "assistant", "content": msg.content})
        
        return history
    
    def get_context_for_query(self, current_query: str) -> str:
        """
        Get relevant context from conversation history for current query.
        Returns formatted context string for agent.
        """
        history = self.get_conversation_history(limit=self.max_messages)
        
        if not history:
            return ""
        
        # Format context
        context_parts = ["## Previous Conversation Context:"]
        for msg in history[-5:]:  # Last 5 messages for immediate context
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        
        return "\n".join(context_parts)
    
    def get_summary(self) -> str:
        """Get conversation summary for long conversations."""
        messages = self.memory.chat_memory.messages
        if len(messages) < 10:
            return ""
        
        # Create summary using LLM
        conversation_text = "\n".join([
            f"{'User' if msg.type == 'human' else 'Assistant'}: {msg.content}"
            for msg in messages
        ])
        
        summary_prompt = f"""Summarize this medical conversation in 2-3 sentences, focusing on:
- Main medical topics discussed
- Key medications or conditions mentioned
- Important warnings or recommendations given

Conversation:
{conversation_text}

Summary:"""
        
        response = self.llm.invoke([HumanMessage(content=summary_prompt)])
        return response.content
    
    def clear(self):
        """Clear conversation memory."""
        self.chat_history.clear()
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        messages = self.chat_history.messages
        return {
            "session_id": self.session_id,
            "total_messages": len(messages),
            "user_messages": sum(1 for m in messages if m.type == "human"),
            "ai_messages": sum(1 for m in messages if m.type == "ai"),
            "has_summary": len(messages) >= 10
        }


class MemoryManager:
    """
    Global memory manager for handling multiple conversation sessions.
    All sessions are stored in-memory only (no disk persistence).
    """
    
    _sessions: Dict[str, MedicalConversationMemory] = {}
    
    @classmethod
    def get_session(cls, session_id: str = None) -> MedicalConversationMemory:
        """Get or create a conversation session."""
        if session_id is None:
            # Create new session with unique ID
            new_memory = MedicalConversationMemory()
            session_id = new_memory.session_id
            cls._sessions[session_id] = new_memory
            return new_memory
        
        if session_id not in cls._sessions:
            cls._sessions[session_id] = MedicalConversationMemory(session_id)
        
        return cls._sessions[session_id]
    
    @classmethod
    def delete_session(cls, session_id: str):
        """Delete a conversation session."""
        if session_id in cls._sessions:
            cls._sessions[session_id].clear()
            del cls._sessions[session_id]
    
    @classmethod
    def list_sessions(cls) -> List[str]:
        """List all active session IDs."""
        return list(cls._sessions.keys())
    
    @classmethod
    def get_session_summary(cls, session_id: str) -> Optional[str]:
        """Get summary for a specific session."""
        if session_id not in cls._sessions:
            return None
        return cls._sessions[session_id].get_summary()
