from pydantic import BaseModel, Field


class AgentContext(BaseModel):
    job_id: str = Field(..., description="Ingestion job id")
    iteration: int = 0
