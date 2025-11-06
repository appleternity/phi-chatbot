"""Abstract session store interface and implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import threading

# TODO: Implement PostgresSessionStore and RedisSessionStore for production use.

@dataclass
class SessionData:
    """Session data container."""

    session_id: str
    user_id: str
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

    @abstractmethod
    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Retrieve all sessions for a user, sorted by updated_at descending."""
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
        self._user_index: Dict[str, set[str]] = {}  # user_id -> set of session_ids
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    async def get_session(self, session_id: str) -> Optional[SessionData]:
        """Retrieve session data by ID."""
        with self._lock:
            session = self._store.get(session_id)
            if session:
                # Check if session expired
                if datetime.utcnow() - session.updated_at > timedelta(seconds=self._ttl_seconds):
                    # Clean up from both store and user_index
                    del self._store[session_id]
                    if session.user_id in self._user_index:
                        self._user_index[session.user_id].discard(session_id)
                        if not self._user_index[session.user_id]:
                            del self._user_index[session.user_id]
                    return None
            return session

    async def save_session(self, session_id: str, data: SessionData) -> None:
        """Save or update session data."""
        with self._lock:
            data.updated_at = datetime.utcnow()
            self._store[session_id] = data
            # Maintain user_index
            if data.user_id not in self._user_index:
                self._user_index[data.user_id] = set()
            self._user_index[data.user_id].add(session_id)

    async def delete_session(self, session_id: str) -> None:
        """Delete session data."""
        with self._lock:
            session = self._store.pop(session_id, None)
            # Clean up user_index
            if session and session.user_id in self._user_index:
                self._user_index[session.user_id].discard(session_id)
                if not self._user_index[session.user_id]:
                    del self._user_index[session.user_id]

    async def get_user_sessions(self, user_id: str) -> List[SessionData]:
        """Retrieve all sessions for a user, sorted by updated_at descending."""
        with self._lock:
            session_ids = self._user_index.get(user_id, set())
            sessions = []
            expired_sids = []

            for sid in session_ids:
                session = self._store.get(sid)
                if session:
                    # Check expiration
                    if datetime.utcnow() - session.updated_at <= timedelta(seconds=self._ttl_seconds):
                        sessions.append(session)
                    else:
                        # Mark for cleanup
                        expired_sids.append(sid)

            # Clean up expired sessions
            for sid in expired_sids:
                del self._store[sid]
                self._user_index[user_id].discard(sid)

            if user_id in self._user_index and not self._user_index[user_id]:
                del self._user_index[user_id]

            # Sort by updated_at descending (most recent first)
            return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def clear_expired_sessions(self) -> int:
        """Clear all expired sessions. Returns count of cleared sessions."""
        with self._lock:
            expired = [
                (sid, session)
                for sid, session in self._store.items()
                if datetime.utcnow() - session.updated_at > timedelta(seconds=self._ttl_seconds)
            ]
            for sid, session in expired:
                del self._store[sid]
                # Clean up user_index
                if session.user_id in self._user_index:
                    self._user_index[session.user_id].discard(sid)
                    if not self._user_index[session.user_id]:
                        del self._user_index[session.user_id]
            return len(expired)
