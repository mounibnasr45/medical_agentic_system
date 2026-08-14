"""Session-scoped conversation memory.

Sessions live in process. On a single always-warm instance that is sufficient, and
it keeps the demo free of a database it does not otherwise need.

Two constraints shape this module:

  - Memory is bounded. The deployment has 512MB, so both the number of sessions and
    the messages per session are capped, and the least recently used session is
    evicted rather than allowed to grow without limit.
  - History is a list of messages. An earlier version wrapped this in LangChain's
    ChatMessageHistory and called the summariser through langchain-groq. Neither
    added behaviour over the Groq SDK already in use, and langchain-groq pinned an
    incompatible groq version, so both were removed.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from medical_agent.config import Config

logger = logging.getLogger(__name__)

MAX_SESSIONS = 200
MAX_MESSAGES_PER_SESSION = 40
CONTEXT_MESSAGES = 6
SUMMARY_THRESHOLD = 10


@dataclass
class Message:
    role: Literal["user", "assistant"]
    content: str
    at: str

    def as_dict(self) -> dict:
        return {"role": self.role, "content": self.content, "at": self.at}


class ConversationMemory:
    """Rolling history for one conversation."""

    def __init__(self, session_id: str | None = None) -> None:
        self.session_id = session_id or self._new_id()
        self.messages: list[Message] = []
        self.created_at = datetime.now(UTC).isoformat()
        self._llm = None

    @staticmethod
    def _new_id() -> str:
        seed = f"{datetime.now(UTC).isoformat()}{id(object())}"
        return hashlib.sha256(seed.encode()).hexdigest()[:16]

    def _add(self, role: Literal["user", "assistant"], content: str) -> None:
        self.messages.append(Message(role=role, content=content, at=datetime.now(UTC).isoformat()))
        if len(self.messages) > MAX_MESSAGES_PER_SESSION:
            del self.messages[:-MAX_MESSAGES_PER_SESSION]

    def add_user_message(self, content: str) -> None:
        self._add("user", content)

    def add_ai_message(self, content: str) -> None:
        self._add("assistant", content)

    def history(self, limit: int | None = None) -> list[dict]:
        messages = self.messages[-limit:] if limit else self.messages
        return [m.as_dict() for m in messages]

    def context_for_query(self) -> str:
        """Recent turns, formatted for injection into an agent prompt."""
        if not self.messages:
            return ""
        recent = self.messages[-CONTEXT_MESSAGES:]
        lines = ["## Previous conversation context:"]
        lines += [f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in recent]
        return "\n".join(lines)

    def stats(self) -> dict:
        return {
            "session_id": self.session_id,
            "total_messages": len(self.messages),
            "user_messages": sum(1 for m in self.messages if m.role == "user"),
            "ai_messages": sum(1 for m in self.messages if m.role == "assistant"),
            "has_summary": len(self.messages) >= SUMMARY_THRESHOLD,
        }

    def summary(self) -> str:
        """LLM summary of the conversation. Empty for short conversations."""
        if len(self.messages) < SUMMARY_THRESHOLD:
            return ""

        transcript = "\n".join(
            f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in self.messages
        )
        prompt = (
            "Summarise this medical conversation in 2-3 sentences, covering the main "
            "topics discussed, the medications or conditions mentioned, and any "
            f"warnings given.\n\nConversation:\n{transcript}\n\nSummary:"
        )
        try:
            completion = self._summariser().chat.completions.create(
                model=Config.GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            return completion.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Summarisation failed: %s", exc)
            return ""

    def _summariser(self):
        if self._llm is None:
            from groq import Groq

            self._llm = Groq(api_key=Config.GROQ_API_KEY)
        return self._llm

    def clear(self) -> None:
        self.messages.clear()


class MemoryManager:
    """LRU-bounded registry of conversation sessions."""

    _sessions: OrderedDict[str, ConversationMemory] = OrderedDict()
    _lock = threading.Lock()

    @classmethod
    def get_session(cls, session_id: str | None = None) -> ConversationMemory:
        with cls._lock:
            if session_id and session_id in cls._sessions:
                cls._sessions.move_to_end(session_id)
                return cls._sessions[session_id]

            memory = ConversationMemory(session_id)
            cls._sessions[memory.session_id] = memory
            while len(cls._sessions) > MAX_SESSIONS:
                evicted, _ = cls._sessions.popitem(last=False)
                logger.info("Evicted least recently used session %s", evicted)
            return memory

    @classmethod
    def delete_session(cls, session_id: str) -> bool:
        with cls._lock:
            session = cls._sessions.pop(session_id, None)
            if session is None:
                return False
            session.clear()
            return True

    @classmethod
    def list_sessions(cls) -> list[str]:
        with cls._lock:
            return list(cls._sessions.keys())

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._sessions.clear()
