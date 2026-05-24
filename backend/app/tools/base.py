from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    success: bool
    message: str | None = None
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    candidate_update: dict[str, Any] | None = None
    signals: dict[str, Any] = Field(default_factory=dict)
