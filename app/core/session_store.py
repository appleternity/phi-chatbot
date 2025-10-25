"""Abstract session store interface and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict
import threading

# TODO: Implement PostgresSessionStore and RedisSessionStore for production use.

@dataclass
class SessionData:
    """Session data container."""

    session_id: str
    assigned_agent: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


class SessionStore(ABC):
    """Abstract interface for session persistence."""

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve session data by ID."""
        pass

    @abstractmethod
    async def save_session(self, session_id: str, data: SessionData) -> None:
        """Save or update session data."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete session data."""
        pass


class InMemorySessionStore(SessionStore):
    """In-memory session store implementation for POC.

    Note: Data will be lost on application restart.
    For production, use PostgresSessionStore or RedisSessionStore.
    """

    def __init__(self, ttl_seconds: int = 3600) -> None:
        """Initialize in-memory store.

        Args:
            ttl_seconds: Time-to-live for sessions in seconds
        """
        self._store: Dict[str, SessionData] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve session data by ID."""
        with self._lock:
            session = self._store.get(session_id)
            if session:
                # Check if session expired
                if datetime.utcnow() - session.updated_at > timedelta(seconds=self._ttl_seconds):
                    del self._store[session_id]
                    return None
            return session

    async def save_session(self, session_id: str, data: SessionData) -> None:
        """Save or update session data."""
        with self._lock:
            data.updated_at = datetime.utcnow()
            self._store[session_id] = data

    async def delete_session(self, session_id: str) -> None:
        """Delete session data."""
        with self._lock:
            self._store.pop(session_id, None)

    def clear_expired_sessions(self) -> int:
        """Clear all expired sessions. Returns count of cleared sessions."""
        with self._lock:
            expired = [
                sid
                for sid, session in self._store.items()
                if datetime.utcnow() - session.updated_at > timedelta(seconds=self._ttl_seconds)
            ]
            for sid in expired:
                del self._store[sid]
            return len(expired)
