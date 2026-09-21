from enum import Enum
from pydantic import BaseModel, Field


class DecisionEnum(str, Enum):
    ANSWER = "ANSWER"
    ESCALATE = "ESCALATE"
    RETRY = "RETRY"


class ConfidenceResult(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0, description="Composite confidence score between 0 and 1")
    decision: DecisionEnum = Field(description="Operational decision: ANSWER, ESCALATE, or RETRY")
    reasons: list[str] = Field(default_factory=list, description="List of explanatory factors contributing to the score")
    signals: dict[str, float] = Field(default_factory=dict, description="Individual numeric signal scores")
