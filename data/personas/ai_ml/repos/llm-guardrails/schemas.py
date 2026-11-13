# synthetic: true
"""Pydantic schemas for LLM agent actions."""
from pydantic import BaseModel, Field


class AgentAction(BaseModel):
    tool_name: str
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)
