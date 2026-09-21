from typing import Any
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    tool_name: str = Field(description="Name of the tool to invoke")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments to pass to the tool")
    description: str = Field(default="", description="Objective of this step")


class PlanResult(BaseModel):
    goal: str = Field(description="Overall high-level goal of the plan")
    steps: list[PlanStep] = Field(default_factory=list, description="Sequence of tool execution steps")
    requires_rag: bool = Field(default=False, description="Whether general knowledge base retrieval is needed")
    escalate: bool = Field(default=False, description="Whether this request should directly escalate to human agent")
    escalation_reason: str | None = Field(default=None, description="Reason for escalation if escalate is true")
