"""Pydantic models for API requests and responses."""

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Session ID (None = create new)")
    message: str = Field(..., min_length=1, description="User message")


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    session_id: str = Field(..., description="Session identifier")
    message: str = Field(..., description="Agent response")
    agent: str = Field(..., description="Agent that handled the message")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "healthy"
    version: str = "0.1.0"
